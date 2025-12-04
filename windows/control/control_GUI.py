# coding: utf-8
# コントローラー入力表示GUI (シンプル版)

import tkinter as tk
from tkinter import ttk
import pygame
import math

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

class ControllerSimpleGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("シンプルコントローラーUI")
        self.root.geometry("600x400")
        self.root.configure(bg='gray10')
        self.joystick = None
        self.indicators = {}
        self.stick_coords = {}
        self.trigger_coords = {}

        # --- Pygameの初期化 ---
        pygame.init()
        self.init_joystick()

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
            print("コントローラーが見つかりません。")

    def create_widgets(self):
        self.canvas = tk.Canvas(self.root, bg='gray10', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # --- UI要素の描画 ---
        # 各UI要素の座標は、ここで調整してください。
        # draw_stick_area(name, label, 中心X座標, 中心Y座標)
        self.draw_stick_area("LS", "左スティック", 200,150)
        self.draw_stick_area("RS", "右スティック", 400, 150)
        
        # draw_trigger_area(name, label, 左上X座標, 左上Y座標)
        self.draw_trigger_area("LT", "LT", 90, 100)
        self.draw_trigger_area("RT", "RT", 480,100) # 右側に配置

        # draw_dpad_area(name, label, 中心X座標, 中心Y座標)
        # 十字キーの中心Y座標とABXYボタン群の中心Y座標を合わせています。
        self.draw_dpad_area("DPAD", "十字キー", 160, 290)
        
        # draw_button_area(name, label, 中心X座標, 中心Y座標)
        # ABXYボタン、LB/RB、START/BACKボタンの描画
        self.draw_button_area("BUTTONS", "ボタン", 440, 290) # ABXYの中心座標を調整


    def draw_stick_area(self, name, label, cx, cy):
        """スティックの領域を描画
        cx, cy: スティックの中心座標
        """
        # スティック外枠の半径
        radius = 50 
        # スティック可動部の半径
        stick_radius = 10

        # ラベルの位置調整
        self.canvas.create_text(cx, cy - radius - 15, text=label, fill="white", font=("Consolas", 12))
        # 外枠と十字線
        self.canvas.create_oval(cx-radius, cy-radius, cx+radius, cy+radius, outline="gray40", width=2)
        self.canvas.create_line(cx-radius, cy, cx+radius, cy, fill="gray40", width=1)
        self.canvas.create_line(cx, cy-radius, cx, cy+radius, fill="gray40", width=1)
        # 可動するインジケーター
        self.indicators[name] = self.canvas.create_oval(
            cx-stick_radius, cy-stick_radius, cx+stick_radius, cy+stick_radius,
            fill="#ff4444", outline="red", width=2
        )
        # 押し込みインジケーター (中央の点)
        self.indicators[name + "_PRESS"] = self.canvas.create_oval(
            cx-3, cy-3, cx+3, cy+3, fill="gray40", outline=""
        )
        self.stick_coords[name] = {"cx": cx, "cy": cy, "max_dist": radius, "stick_r": stick_radius}

    def draw_trigger_area(self, name, label, x, y):
        """トリガーの領域を描画
        x, y: トリガーの左上X座標, 左上Y座標
        """
        # トリガーバーの幅と高さ (縦向き)
        bar_width, bar_height = 20, 80 
        # ラベルの位置調整
        self.canvas.create_text(x + bar_width / 2, y - 15, text=label, fill="white", font=("Consolas", 12))
        # 背景
        bg_rect_id = self.canvas.create_rectangle(x, y, x + bar_width, y + bar_height, outline="gray40", width=2)
        # 強度バー (最初は0)
        self.indicators[name] = self.canvas.create_rectangle(x, y + bar_height, x + bar_width, y + bar_height, fill="#4488ff", outline="")
        self.trigger_coords[name] = {"bg_rect_id": bg_rect_id, "x": x, "y": y, "width": bar_width, "height": bar_height}

    def draw_dpad_area(self, name, label, cx, cy):
        """十字キーの領域を描画
        cx, cy: 十字キー全体の中心座標
        """
        # 各方向キーのサイズ
        size = 20
        # 各方向キー間の隙間
        gap = 10

        self.canvas.create_text(cx, cy - size - gap - 10, text=label, fill="white", font=("Consolas", 12))
        self.indicators["HAT_UP"] = self.canvas.create_rectangle(cx-size/2, cy-size-gap, cx+size/2, cy-gap, fill="gray20", outline="gray40")
        self.indicators["HAT_DOWN"] = self.canvas.create_rectangle(cx-size/2, cy+gap, cx+size/2, cy+size+gap, fill="gray20", outline="gray40")
        self.indicators["HAT_LEFT"] = self.canvas.create_rectangle(cx-size-gap, cy-size/2, cx-gap, cy+size/2, fill="gray20", outline="gray40")
        self.indicators["HAT_RIGHT"] = self.canvas.create_rectangle(cx+gap, cy-size/2, cx+size+gap, cy+size/2, fill="gray20", outline="gray40")

    def draw_button_area(self, name, label, cx, cy):
        """ABXY, ショルダーボタン、START/BACKボタンの領域を描画
        cx, cy: ABXYボタン群の中心座標
        """
        # ABXYボタンの半径
        r = 12
        # ABXYボタン間の間隔を調整するオフセット
        offset_xy = 25
        offset_ab = 25

        # --- ABXY ボタン ---
        # Yボタン
        self.indicators["Y"] = self.canvas.create_oval(cx-r, cy-r-offset_xy, cx+r, cy+r-offset_xy, fill="gray20", outline="gray40")
        self.canvas.create_text(cx, cy-offset_xy, text="Y", fill="white")
        # Xボタン
        self.indicators["X"] = self.canvas.create_oval(cx-r-offset_ab, cy-r, cx+r-offset_ab, cy+r, fill="gray20", outline="gray40")
        self.canvas.create_text(cx-offset_ab, cy, text="X", fill="white")
        # Bボタン
        self.indicators["B"] = self.canvas.create_oval(cx-r+offset_ab, cy-r, cx+r+offset_ab, cy+r, fill="gray20", outline="gray40")
        self.canvas.create_text(cx+offset_ab, cy, text="B", fill="white")
        # Aボタン
        self.indicators["A"] = self.canvas.create_oval(cx-r, cy-r+offset_xy, cx+r, cy+r+offset_xy, fill="gray20", outline="gray40")
        self.canvas.create_text(cx, cy+offset_xy, text="A", fill="white")
        
        # --- LB, RB ボタン ---
        # LBボタンの座標とサイズ
        lb_x, lb_y, lb_width, lb_height = 150, 40, 100, 20 
        self.indicators["LB"] = self.canvas.create_rectangle(lb_x, lb_y, lb_x + lb_width, lb_y + lb_height, fill="gray20", outline="gray40")
        self.canvas.create_text(lb_x + lb_width / 2, lb_y + lb_height / 2, text="LB", fill="white")
        # RBボタンの座標とサイズ
        rb_x, rb_y, rb_width, rb_height = 350, 40, 100, 20 
        self.indicators["RB"] = self.canvas.create_rectangle(rb_x, rb_y, rb_x + rb_width, rb_y + rb_height, fill="gray20", outline="gray40")
        self.canvas.create_text(rb_x + rb_width / 2, rb_y + rb_height / 2, text="RB", fill="white")
        
        # --- START, BACK ボタン ---
        # BACKボタンの座標とサイズ
        back_x, back_y, back_width, back_height = 230, 300, 60, 20
        self.indicators["BACK"] = self.canvas.create_rectangle(back_x, back_y, back_x + back_width, back_y + back_height, fill="gray20", outline="gray40")
        self.canvas.create_text(back_x + back_width / 2, back_y + back_height / 2, text="BACK", fill="white")
        # STARTボタンの座標とサイズ
        start_x, start_y, start_width, start_height = 310, 300, 60, 20
        self.indicators["START"] = self.canvas.create_rectangle(start_x, start_y, start_x + start_width, start_y + start_height, fill="gray20", outline="gray40")
        self.canvas.create_text(start_x + start_width / 2, start_y + start_height / 2, text="START", fill="white")


    def set_indicator_state(self, name, active):
        """インジケーターの色を更新"""
        if name not in self.indicators: return
        color = "#44ff44" if active else "gray20"
        self.canvas.itemconfig(self.indicators[name], fill=color)

    def set_stick_press_state(self, name, active):
        """スティック押し込みインジケーターの色を更新"""
        if name not in self.indicators: return
        color = "#44ff44" if active else "gray40"
        self.canvas.itemconfig(self.indicators[name], fill=color)

    def move_stick_indicator(self, name, x_val, y_val):
        """スティックのインジケーターを移動"""
        if name not in self.indicators: return
        
        coords = self.stick_coords[name]
        new_x = coords["cx"] + x_val * coords["max_dist"]
        new_y = coords["cy"] + y_val * coords["max_dist"]
        r = coords["stick_r"]
        
        self.canvas.coords(self.indicators[name], new_x - r, new_y - r, new_x + r, new_y + r)

    def update_trigger_indicator(self, name, value):
        """トリガーのインジケーターを更新 (-1 to 1 -> 0 to 1)
        縦向きのバーとして更新する
        """
        if name not in self.indicators: return
        if name not in self.trigger_coords: return
        
        coords = self.trigger_coords[name]
        norm_value = (value + 1) / 2 # -1~1 -> 0~1
        
        bg_x1 = coords["x"]
        bg_y1 = coords["y"]
        bg_x2 = coords["x"] + coords["width"]
        bg_y2 = coords["y"] + coords["height"]
        height = coords["height"]
        
        # バーが下から上に伸びるようにY座標を計算
        new_y1 = bg_y2 - (height * norm_value)
        self.canvas.coords(self.indicators[name], bg_x1, new_y1, bg_x2, bg_y2)

    def update_gui(self):
        # Pygameイベント処理
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.root.quit()
                return

        # コントローラーが接続されていなければ再試行
        if not self.joystick:
            if pygame.joystick.get_count() > 0:
                self.init_joystick()
            self.root.after(100, self.update_gui)
            return

        # --- 状態のポーリングとGUI更新 ---
        # Sticks
        lx, ly = (self.joystick.get_axis(i) for i in range(2))
        self.move_stick_indicator("LS", lx, ly)
        rx, ry = (self.joystick.get_axis(i) for i in range(2, 4))
        self.move_stick_indicator("RS", rx, ry)

        # Stick Presses
        self.set_stick_press_state("LS_PRESS", self.joystick.get_button(8))
        self.set_stick_press_state("RS_PRESS", self.joystick.get_button(9))

        # Buttons
        for i in range(self.joystick.get_numbuttons()):
            if i in BUTTON_MAPPING and BUTTON_MAPPING[i] not in ["LS_PRESS", "RS_PRESS"]:
                self.set_indicator_state(BUTTON_MAPPING[i], self.joystick.get_button(i))

        # Triggers
        if self.joystick.get_numaxes() > 5:
            lt_val = self.joystick.get_axis(4)
            rt_val = self.joystick.get_axis(5)
            self.update_trigger_indicator("LT", lt_val)
            self.update_trigger_indicator("RT", rt_val)

        # Hat (十字キー)
        if self.joystick.get_numhats() > 0:
            hat_x, hat_y = self.joystick.get_hat(0)
            self.set_indicator_state("HAT_UP", hat_y == 1)
            self.set_indicator_state("HAT_DOWN", hat_y == -1)
            self.set_indicator_state("HAT_LEFT", hat_x == -1)
            self.set_indicator_state("HAT_RIGHT", hat_x == 1)

        self.root.after(16, self.update_gui) # 約60FPS

if __name__ == "__main__":
    root = tk.Tk()
    app = ControllerSimpleGUI(root)
    root.mainloop()
    pygame.quit()
