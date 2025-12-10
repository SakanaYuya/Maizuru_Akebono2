#V6 - Safe Stop Edition
import cv2
import socket
import numpy as np
import threading
import pygame
import time
import tkinter as tk
import json
from tkinter import ttk
import math

# --- 設定 ---
# 自分のIP (受信待機用)
MY_IP = "0.0.0.0" 
VIDEO_PORT = 5005

# ラズパイのIP (送信先)
RPI_IP = "192.168.50.20"
CONTROL_PORT = 5006

# --- 映像表示設定 ---
# 映像回転角度: 0, 90, 180, 270 のいずれかを指定
VIDEO_ROTATION = 270  # ★ここで回転角度を変更できます

# --- control.py / control_GUI.py からマッピング情報をコピー ---
AXIS_MAPPING = {
    0: {"name": "左スティック X"}, 1: {"name": "左スティック Y"},
    2: {"name": "右スティック X"}, 3: {"name": "右スティック Y"},
    4: {"name": "LT"}, 5: {"name": "RT"},
}
BUTTON_MAPPING = {
    0: "A", 1: "B", 2: "X", 3: "Y", 4: "LB", 5: "RB",
    6: "BACK", 7: "START", 8: "LS_PRESS", 9: "RS_PRESS",
}
HAT_MAPPING = {
    (0, 0): "中央", (-1, 0): "左", (1, 0): "右", (0, 1): "上", (0, -1): "下",
}
# --- ここまで ---

# グローバル終了フラグ
is_running = True

# --- UDP受信 (映像) ---
def receive_video():
    global is_running
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.settimeout(1.0)  # タイムアウト設定で終了検知
    udp_sock.bind((MY_IP, VIDEO_PORT))
    print(f"[*] 映像待機中: UDP {VIDEO_PORT}")
    print(f"[*] 映像回転角度: {VIDEO_ROTATION}度")

    while is_running:
        try:
            data, addr = udp_sock.recvfrom(65535)
            nparr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is not None:
                # 映像回転処理
                if VIDEO_ROTATION == 90:
                    frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
                elif VIDEO_ROTATION == 180:
                    frame = cv2.rotate(frame, cv2.ROTATE_180)
                elif VIDEO_ROTATION == 270:
                    frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
                # VIDEO_ROTATION == 0 の場合は回転なし
                
                cv2.imshow("Raspberry Pi Camera (Low Latency)", frame)
                
            if cv2.waitKey(1) & 0xFF == ord('q'):
                is_running = False
                break
        except socket.timeout:
            continue
        except Exception as e:
            if is_running:  # 終了処理中でなければエラー表示
                print(f"Video Error: {e}")

    udp_sock.close()
    cv2.destroyAllWindows()
    print("[*] 映像受信スレッド終了")

class ControllerClientGUI:
    def __init__(self, root):
        global is_running
        self.root = root
        self.root.title("コントローラーUI & Raspberry Pi クライアント")
        self.root.geometry("600x450")  # 高さを少し増やす
        self.root.configure(bg='gray10')
        self.joystick = None
        self.indicators = {}
        self.stick_coords = {}
        self.trigger_coords = {}
        self.last_sent_data = json.dumps({})
        self.is_running = True

        # --- Pygameの初期化 ---
        pygame.init()
        pygame.joystick.init()
        self.init_joystick()

        # --- TCP接続 ---
        self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            print(f"[*] 接続試行中... {RPI_IP}:{CONTROL_PORT}")
            self.tcp_sock.connect((RPI_IP, CONTROL_PORT))
            print("[*] 接続成功!コントローラーで操作してください")
        except Exception as e:
            print(f"[!] ラズパイへの接続に失敗しました: {e}")
            print("[!] ラズパイ側を先に起動してください。")
            self.tcp_sock = None

        # --- GUIコンポーネントの作成 ---
        self.create_widgets()

        # --- メインループ処理 ---
        self.update_gui()

    def init_joystick(self):
        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            print(f"コントローラー接続: {self.joystick.get_name()}")
        else:
            self.joystick = None
            print("コントローラーが見つかりません。キーボード(WASD)での操作も可能です。")

    def create_widgets(self):
        # ステータス表示エリア
        self.status_frame = tk.Frame(self.root, bg='gray10')
        self.status_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        
        self.status_label = tk.Label(
            self.status_frame, 
            text="接続中" if self.tcp_sock else "未接続", 
            fg="lime" if self.tcp_sock else "red",
            bg='gray10',
            font=("Consolas", 10, "bold")
        )
        self.status_label.pack(side=tk.LEFT)
        
        # 停止ボタン
        self.stop_button = tk.Button(
            self.status_frame,
            text="安全停止 (Q)",
            command=self.safe_shutdown,
            bg='red',
            fg='white',
            font=("Consolas", 10, "bold"),
            padx=10,
            pady=5
        )
        self.stop_button.pack(side=tk.RIGHT)
        
        # メインキャンバス
        self.canvas = tk.Canvas(self.root, bg='gray10', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.draw_stick_area("LS", "左スティック", 200,150)
        self.draw_stick_area("RS", "右スティック", 400, 150)
        self.draw_trigger_area("LT", "LT", 90, 100)
        self.draw_trigger_area("RT", "RT", 480,100)
        self.draw_dpad_area("DPAD", "十字キー", 160, 290)
        self.draw_button_area("BUTTONS", "ボタン", 440, 290)
        
        # ヘルプテキスト
        help_text = "Qキーまたは停止ボタンで安全終了"
        self.canvas.create_text(
            300, 380, 
            text=help_text, 
            fill="yellow", 
            font=("Consolas", 9)
        )

    def draw_stick_area(self, name, label, cx, cy):
        radius = 50 
        stick_radius = 10
        self.canvas.create_text(cx, cy - radius - 15, text=label, fill="white", font=("Consolas", 12))
        self.canvas.create_oval(cx-radius, cy-radius, cx+radius, cy+radius, outline="gray40", width=2)
        self.canvas.create_line(cx-radius, cy, cx+radius, cy, fill="gray40", width=1)
        self.canvas.create_line(cx, cy-radius, cx, cy+radius, fill="gray40", width=1)
        self.indicators[name] = self.canvas.create_oval(
            cx-stick_radius, cy-stick_radius, cx+stick_radius, cy+stick_radius,
            fill="#ff4444", outline="red", width=2
        )
        self.indicators[name + "_PRESS"] = self.canvas.create_oval(
            cx-3, cy-3, cx+3, cy+3, fill="gray40", outline=""
        )
        self.stick_coords[name] = {"cx": cx, "cy": cy, "max_dist": radius, "stick_r": stick_radius}

    def draw_trigger_area(self, name, label, x, y):
        bar_width, bar_height = 20, 80 
        self.canvas.create_text(x + bar_width / 2, y - 15, text=label, fill="white", font=("Consolas", 12))
        bg_rect_id = self.canvas.create_rectangle(x, y, x + bar_width, y + bar_height, outline="gray40", width=2)
        self.indicators[name] = self.canvas.create_rectangle(x, y + bar_height, x + bar_width, y + bar_height, fill="#4488ff", outline="")
        self.trigger_coords[name] = {"bg_rect_id": bg_rect_id, "x": x, "y": y, "width": bar_width, "height": bar_height}

    def draw_dpad_area(self, name, label, cx, cy):
        size = 20
        gap = 10
        self.canvas.create_text(cx, cy - size - gap - 10, text=label, fill="white", font=("Consolas", 12))
        self.indicators["HAT_UP"] = self.canvas.create_rectangle(cx-size/2, cy-size-gap, cx+size/2, cy-gap, fill="gray20", outline="gray40")
        self.indicators["HAT_DOWN"] = self.canvas.create_rectangle(cx-size/2, cy+gap, cx+size/2, cy+size+gap, fill="gray20", outline="gray40")
        self.indicators["HAT_LEFT"] = self.canvas.create_rectangle(cx-size-gap, cy-size/2, cx-gap, cy+size/2, fill="gray20", outline="gray40")
        self.indicators["HAT_RIGHT"] = self.canvas.create_rectangle(cx+gap, cy-size/2, cx+size+gap, cy+size/2, fill="gray20", outline="gray40")

    def draw_button_area(self, name, label, cx, cy):
        r = 12
        offset_xy = 25
        offset_ab = 25

        self.indicators["Y"] = self.canvas.create_oval(cx-r, cy-r-offset_xy, cx+r, cy+r-offset_xy, fill="gray20", outline="gray40")
        self.canvas.create_text(cx, cy-offset_xy, text="Y", fill="white")
        self.indicators["X"] = self.canvas.create_oval(cx-r-offset_ab, cy-r, cx+r-offset_ab, cy+r, fill="gray20", outline="gray40")
        self.canvas.create_text(cx-offset_ab, cy, text="X", fill="white")
        self.indicators["B"] = self.canvas.create_oval(cx-r+offset_ab, cy-r, cx+r+offset_ab, cy+r, fill="gray20", outline="gray40")
        self.canvas.create_text(cx+offset_ab, cy, text="B", fill="white")
        self.indicators["A"] = self.canvas.create_oval(cx-r, cy-r+offset_xy, cx+r, cy+r+offset_xy, fill="gray20", outline="gray40")
        self.canvas.create_text(cx, cy+offset_xy, text="A", fill="white")
        
        lb_x, lb_y, lb_width, lb_height = 150, 40, 100, 20 
        self.indicators["LB"] = self.canvas.create_rectangle(lb_x, lb_y, lb_x + lb_width, lb_y + lb_height, fill="gray20", outline="gray40")
        self.canvas.create_text(lb_x + lb_width / 2, lb_y + lb_height / 2, text="LB", fill="white")
        rb_x, rb_y, rb_width, rb_height = 350, 40, 100, 20 
        self.indicators["RB"] = self.canvas.create_rectangle(rb_x, rb_y, rb_x + rb_width, rb_y + rb_height, fill="gray20", outline="gray40")
        self.canvas.create_text(rb_x + rb_width / 2, rb_y + rb_height / 2, text="RB", fill="white")
        
        back_x, back_y, back_width, back_height = 230, 300, 60, 20
        self.indicators["BACK"] = self.canvas.create_rectangle(back_x, back_y, back_x + back_width, back_y + back_height, fill="gray20", outline="gray40")
        self.canvas.create_text(back_x + back_width / 2, back_y + back_height / 2, text="BACK", fill="white")
        start_x, start_y, start_width, start_height = 310, 300, 60, 20
        self.indicators["START"] = self.canvas.create_rectangle(start_x, start_y, start_x + start_width, start_y + start_height, fill="gray20", outline="gray40")
        self.canvas.create_text(start_x + start_width / 2, start_y + start_height / 2, text="START", fill="white")


    def set_indicator_state(self, name, active):
        if name not in self.indicators: return
        color = "#44ff44" if active else "gray20"
        self.canvas.itemconfig(self.indicators[name], fill=color)

    def set_stick_press_state(self, name, active):
        if name not in self.indicators: return
        color = "#44ff44" if active else "gray40"
        self.canvas.itemconfig(self.indicators[name], fill=color)

    def move_stick_indicator(self, name, x_val, y_val):
        if name not in self.indicators: return
        
        coords = self.stick_coords[name]
        new_x = coords["cx"] + x_val * coords["max_dist"]
        new_y = coords["cy"] + y_val * coords["max_dist"]
        r = coords["stick_r"]
        
        self.canvas.coords(self.indicators[name], new_x - r, new_y - r, new_x + r, new_y + r)

    def update_trigger_indicator(self, name, value):
        if name not in self.indicators: return
        if name not in self.trigger_coords: return
        
        coords = self.trigger_coords[name]
        norm_value = (value + 1) / 2
        
        bg_x1 = coords["x"]
        bg_y1 = coords["y"]
        bg_x2 = coords["x"] + coords["width"]
        bg_y2 = coords["y"] + coords["height"]
        height = coords["height"]
        
        new_y1 = bg_y2 - (height * norm_value)
        self.canvas.coords(self.indicators[name], bg_x1, new_y1, bg_x2, bg_y2)

    def safe_shutdown(self):
        """安全な終了処理"""
        global is_running
        print("[*] 安全停止処理を開始...")
        
        self.is_running = False
        is_running = False
        
        # ステータス更新
        self.status_label.config(text="停止中...", fg="orange")
        
        # 全入力をゼロにして送信
        stop_data = {
            "controller": {
                "LS_X": 0.0, "LS_Y": 0.0,
                "RS_X": 0.0, "RS_Y": 0.0,
                "LS_PRESS": False, "RS_PRESS": False,
                "TRIGGER_LT": 0.0, "TRIGGER_RT": 0.0,
                "HAT_X": 0, "HAT_Y": 0
            },
            "keyboard": {
                "W": False, "A": False, "S": False, "D": False
            }
        }
        
        if self.tcp_sock:
            try:
                json_stop = json.dumps(stop_data)
                self.tcp_sock.sendall((json_stop + "\n").encode('utf-8'))
                print("[*] 停止信号を送信しました")
                time.sleep(0.1)
            except Exception as e:
                print(f"[!] 停止信号送信エラー: {e}")
        
        # ウィンドウを閉じる
        self.root.quit()

    def update_gui(self):
        if not self.is_running:
            return
            
        controller_data = {}
        keyboard_data = {}

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.safe_shutdown()
                return
            
            if event.type == pygame.JOYDEVICEADDED:
                if self.joystick is None: 
                    self.joystick = pygame.joystick.Joystick(event.device_index)
                    self.joystick.init()
                    print(f"コントローラー再接続: {self.joystick.get_name()}")
            elif event.type == pygame.JOYDEVICEREMOVED:
                if self.joystick and self.joystick.get_instance_id() == event.instance_id:
                    print("コントローラー切断されました。")
                    self.joystick = None

        # キーボードでの終了チェック (Qキー)
        keys = pygame.key.get_pressed()
        if keys[pygame.K_q]:
            self.safe_shutdown()
            return

        # コントローラーが接続されていなければ再試行
        if not self.joystick:
            if pygame.joystick.get_count() > 0:
                self.init_joystick()
            self.root.after(16, self.update_gui)
            return

        # --- 状態のポーリングとGUI更新 & コマンドの決定ロジック ---
        # Sticks
        lx, ly = (self.joystick.get_axis(i) for i in range(2))
        self.move_stick_indicator("LS", lx, ly)
        controller_data["LS_X"] = lx
        controller_data["LS_Y"] = ly

        rx, ry = (self.joystick.get_axis(i) for i in range(2, 4))
        self.move_stick_indicator("RS", rx, ry)
        controller_data["RS_X"] = rx
        controller_data["RS_Y"] = ry

        # Stick Presses
        ls_press = self.joystick.get_button(8)
        rs_press = self.joystick.get_button(9)
        self.set_stick_press_state("LS_PRESS", ls_press)
        self.set_stick_press_state("RS_PRESS", rs_press)
        controller_data["LS_PRESS"] = bool(ls_press)
        controller_data["RS_PRESS"] = bool(rs_press)

        # Buttons
        for i in range(self.joystick.get_numbuttons()):
            button_name = BUTTON_MAPPING.get(i)
            if button_name:
                is_pressed = self.joystick.get_button(i)
                self.set_indicator_state(button_name, is_pressed)
                controller_data[f"BUTTON_{button_name}"] = bool(is_pressed)

        # Triggers
        lt_val, rt_val = 0.0, 0.0
        if self.joystick.get_numaxes() > 5:
            lt_val = self.joystick.get_axis(4)
            rt_val = self.joystick.get_axis(5)
            self.update_trigger_indicator("LT", lt_val)
            self.update_trigger_indicator("RT", rt_val)
            controller_data["TRIGGER_LT"] = lt_val
            controller_data["TRIGGER_RT"] = rt_val

        # Hat (十字キー)
        if self.joystick.get_numhats() > 0:
            hat_x, hat_y = self.joystick.get_hat(0)
            self.set_indicator_state("HAT_UP", hat_y == 1)
            self.set_indicator_state("HAT_DOWN", hat_y == -1)
            self.set_indicator_state("HAT_LEFT", hat_x == -1)
            self.set_indicator_state("HAT_RIGHT", hat_x == 1)
            controller_data["HAT_X"] = hat_x
            controller_data["HAT_Y"] = hat_y
        
        # キーボード入力
        keyboard_data["W"] = bool(keys[pygame.K_w])
        keyboard_data["A"] = bool(keys[pygame.K_a])
        keyboard_data["S"] = bool(keys[pygame.K_s])
        keyboard_data["D"] = bool(keys[pygame.K_d])
        
        # 全ての入力データを結合し、JSON形式で送信
        combined_data = {
            "controller": controller_data,
            "keyboard": keyboard_data
        }
        json_to_send = json.dumps(combined_data)

        # 前回の送信データと異なる場合のみ送信
        if self.tcp_sock and json_to_send != self.last_sent_data:
            try:
                self.tcp_sock.sendall((json_to_send + "\n").encode('utf-8'))
                self.last_sent_data = json_to_send
            except Exception as e:
                print(f"送信エラー: {e}")
                if self.tcp_sock:
                    self.tcp_sock.close()
                self.tcp_sock = None
                self.status_label.config(text="切断", fg="red")
        
        self.root.after(16, self.update_gui)

    def on_closing(self):
        """ウィンドウ×ボタン押下時"""
        self.safe_shutdown()

if __name__ == "__main__":
    # 映像受信は別スレッドで動かす
    video_thread = threading.Thread(target=receive_video)
    video_thread.daemon = True
    video_thread.start()

    # メインスレッドでGUIと操作送信を行う
    root = tk.Tk()
    app = ControllerClientGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\n[*] キーボード割り込み検出")
    finally:
        print("[*] クリーンアップ中...")
        is_running = False
        pygame.quit()
        print("[*] 終了完了")