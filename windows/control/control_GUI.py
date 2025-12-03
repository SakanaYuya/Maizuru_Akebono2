# coding: utf-8
# コントローラー入力表示GUI

import tkinter as tk
from tkinter import ttk
import pygame
from PIL import Image, ImageTk
import os

# --- control.py からマッピング情報をコピー ---
AXIS_MAPPING = {
    0: {"name": "左スティック X"}, 1: {"name": "左スティック Y"},
    2: {"name": "右スティック X"}, 3: {"name": "右スティック Y"},
    4: {"name": "LT"}, 5: {"name": "RT"},
}
BUTTON_MAPPING = {
    0: "A", 1: "B", 2: "X", 3: "Y", 4: "LB", 5: "RB",
    6: "BACK", 7: "START", 8: "左スティック押込", 9: "右スティック押込",
}
HAT_MAPPING = {
    (0, 0): "中央", (-1, 0): "左", (1, 0): "右", (0, 1): "上", (0, -1): "下",
}
# --- ここまで ---

# --------------------------------------------------------------------
# --- GUI上の各入力要素の座標とサイズ (★★ここを調整してください★★) ---
# --------------------------------------------------------------------
# 各インジケーターの位置やサイズを画像に合わせて調整します。
#
# ■ 円の場合 (shape="oval" または shape指定なし)
#   "pos": (中心のx座標, 中心のy座標)
#   "radius": 円の半径
#
# ■ 四角形の場合 (shape="rect")
#   "pos": (左上のx座標, 左上のy座標, 右下のx座標, 右下のy座標)
#
# ※座標の原点(0, 0)は、ウィンドウ左上です。
# --------------------------------------------------------------------
INPUT_COORDINATES = {
    # --- スティック ---
    # 左スティックの土台部分
    "LS": {"pos": (142, 166), "radius": 35},
    # 左スティックの可動部分
    "LS_STICK": {"pos": (142, 166), "radius": 15},
    # 右スティックの土台部分
    "RS": {"pos": (352, 275), "radius": 35},
    # 右スティックの可動部分
    "RS_STICK": {"pos": (352, 275), "radius": 15},

    # --- A, B, X, Y ボタン ---
    "A": {"pos": (455, 275), "radius": 20},
    "B": {"pos": (500, 230), "radius": 20},
    "X": {"pos": (410, 230), "radius": 20},
    "Y": {"pos": (455, 185), "radius": 20},

    # --- 十字キー (Hat) ---
    "HAT_UP":    {"shape": "rect", "pos": (205, 252, 232, 279)},
    "HAT_DOWN":  {"shape": "rect", "pos": (205, 305, 232, 332)},
    "HAT_LEFT":  {"shape": "rect", "pos": (178, 279, 205, 306)},
    "HAT_RIGHT": {"shape": "rect", "pos": (232, 279, 259, 306)},

    # --- ショルダーボタン (LB, RB) ---
    "LB": {"shape": "rect", "pos": (90, 80, 200, 115)},
    "RB": {"shape": "rect", "pos": (400, 80, 510, 115)},

    # --- トリガー (LT, RT) ---
    "LT": {"shape": "rect", "pos": (90, 15, 200, 70)},
    "RT": {"shape": "rect", "pos": (400, 15, 510, 70)},

    # --- START, BACK ボタン ---
    "START": {"pos": (350, 200), "radius": 10},
    "BACK":  {"pos": (250, 200), "radius": 10},

    # --- スティック押し込み ---
    "LS_STICK_PRESS": {"pos": (142, 166), "radius": 15},
    "RS_STICK_PRESS": {"pos": (352, 275), "radius": 15},
}

class ControllerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("コントローラー入力表示")
        self.joystick = None
        self.indicators = {}
        self.scale_factor = 0.7  # ★画像の縮小率 (70%)

        # --- 画像の読み込みとリサイズ ---
        image_path = os.path.join(os.path.dirname(__file__), "assets", "resize_controller.png")
        try:
            original_image = Image.open(image_path)
            # 画像をリサイズ
            new_width = int(original_image.width * self.scale_factor)
            new_height = int(original_image.height * self.scale_factor)
            self.controller_image = original_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        except FileNotFoundError:
            print(f"エラー: 画像ファイルが見つかりません: {image_path}")
            self.root.quit()
            return

        self.controller_photo = ImageTk.PhotoImage(self.controller_image)
        
        # --- 座標のスケーリング ---
        self.scale_coordinates()

        # ウィンドウサイズを画像に合わせる
        self.root.geometry(f"{self.controller_image.width}x{self.controller_image.height+150}")

        # --- Pygameの初期化 ---
        pygame.init()
        self.init_joystick()

        # --- GUIコンポーネントの作成 ---
        self.create_widgets()

        # --- メインループ処理 ---
        self.update_gui()

    def scale_coordinates(self):
        """INPUT_COORDINATESの値をscale_factorに基づいて縮小する"""
        global INPUT_COORDINATES
        scaled_coords = {}
        for name, data in INPUT_COORDINATES.items():
            scaled_data = data.copy()
            if "pos" in data:
                if data.get("shape") == "rect":
                    # (x1, y1, x2, y2)
                    scaled_data["pos"] = tuple(int(p * self.scale_factor) for p in data["pos"])
                else:
                    # (x, y)
                    scaled_data["pos"] = tuple(int(p * self.scale_factor) for p in data["pos"])
            if "radius" in data:
                scaled_data["radius"] = int(data["radius"] * self.scale_factor)
            scaled_coords[name] = scaled_data
        INPUT_COORDINATES = scaled_coords

    def init_joystick(self):
        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            if hasattr(self, 'log_text'):
                self.log(f"コントローラー接続: {self.joystick.get_name()}")
        else:
            self.joystick = None

    def create_widgets(self):
        # --- メインキャンバス ---
        self.canvas = tk.Canvas(self.root, width=self.controller_image.width, height=self.controller_image.height)
        self.canvas.pack()
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.controller_photo)

        # --- インジケーターを作成 ---
        self.create_indicators()

        # --- ログ表示 ---
        log_frame = ttk.LabelFrame(self.root, text="Log", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.log_text = tk.Text(log_frame, height=8, state='disabled', bg="black", fg="lightgreen", font=("Consolas", 9))
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_indicators(self):
        """入力箇所に半透明の図形を配置する"""
        for name, data in INPUT_COORDINATES.items():
            shape_type = data.get("shape", "oval")
            if shape_type == "oval":
                x, y = data["pos"]
                r = data["radius"]
                self.indicators[name] = self.canvas.create_oval(x-r, y-r, x+r, y+r, fill="", outline="", state="hidden")
            elif shape_type == "rect":
                x1, y1, x2, y2 = data["pos"]
                self.indicators[name] = self.canvas.create_rectangle(x1, y1, x2, y2, fill="", outline="", state="hidden")

    def log(self, message):
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

    def set_indicator_state(self, name, active, value=1.0):
        """インジケーターの色や位置を更新"""
        if name not in self.indicators:
            return
            
        item_id = self.indicators[name]
        if active:
            # Tkinterは#RRGGBBAA形式をサポートしないため、stippleで半透明を表現
            color = f'#ff0000'
            self.canvas.itemconfig(item_id, fill=color, state="normal")
            # stipple オプションで半透明を表現
            self.canvas.itemconfig(item_id, stipple="gray50")
        else:
            self.canvas.itemconfig(item_id, state="hidden")

    def move_stick_indicator(self, name, x_val, y_val):
        """スティックのインジケーターを移動"""
        if name not in self.indicators: return
        
        base_pos_name = name.replace("_STICK", "")
        # スティック押し込み(LS_STICK_PRESS)もLSをベースにする
        if "_PRESS" in base_pos_name:
            base_pos_name = base_pos_name.replace("_PRESS", "")

        base_pos = INPUT_COORDINATES[base_pos_name]
        stick_data = INPUT_COORDINATES[name]
        
        max_dist = base_pos["radius"] - stick_data["radius"]
        center_x, center_y = INPUT_COORDINATES[name]["pos"]
        radius = stick_data["radius"]
        
        new_x = center_x + x_val * max_dist
        new_y = center_y + y_val * max_dist
        
        self.canvas.coords(self.indicators[name], new_x - radius, new_y - radius, new_x + radius, new_y + radius)
        
        is_moved = abs(x_val) > 0.1 or abs(y_val) > 0.1
        self.set_indicator_state(name, is_moved)

    def update_gui(self):
        # Pygameイベント処理
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.root.quit()
                return
            # ログへの出力はイベントドリブンで
            if event.type in [pygame.JOYAXISMOTION, pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP, pygame.JOYHATMOTION]:
                 if self.joystick: self.log_event(event)

        # コントローラー状態のポーリングとGUI更新
        if not self.joystick:
            if pygame.joystick.get_count() > 0: self.init_joystick()
            self.root.after(100, self.update_gui)
            return

        # Buttons
        for i in range(self.joystick.get_numbuttons()):
            if i in BUTTON_MAPPING:
                self.set_indicator_state(BUTTON_MAPPING[i], self.joystick.get_button(i))
        self.set_indicator_state("LS_STICK_PRESS", self.joystick.get_button(8))
        self.set_indicator_state("RS_STICK_PRESS", self.joystick.get_button(9))

        # Sticks
        lx, ly = (self.joystick.get_axis(i) for i in range(2))
        self.move_stick_indicator("LS_STICK", lx, ly)
        rx, ry = (self.joystick.get_axis(i) for i in range(2, 4))
        self.move_stick_indicator("RS_STICK", rx, ry)

        # Triggers
        if self.joystick.get_numaxes() > 5:
            lt = (self.joystick.get_axis(4) + 1) / 2 # -1~1 -> 0~1
            self.set_indicator_state("LT", lt > 0.1, lt)
            rt = (self.joystick.get_axis(5) + 1) / 2
            self.set_indicator_state("RT", rt > 0.1, rt)

        # Hat
        if self.joystick.get_numhats() > 0:
            hat_x, hat_y = self.joystick.get_hat(0)
            self.set_indicator_state("HAT_UP", hat_y == 1)
            self.set_indicator_state("HAT_DOWN", hat_y == -1)
            self.set_indicator_state("HAT_LEFT", hat_x == -1)
            self.set_indicator_state("HAT_RIGHT", hat_x == 1)

        self.root.after(16, self.update_gui) # 約60FPS

    def log_event(self, event):
        if event.type == pygame.JOYAXISMOTION:
            name = AXIS_MAPPING.get(event.axis, {}).get("name", f"Axis {event.axis}")
            self.log(f"{name}: {event.value:.3f}")
        elif event.type == pygame.JOYBUTTONDOWN:
            name = BUTTON_MAPPING.get(event.button, f"Button {event.button}")
            self.log(f"{name} Down")
        elif event.type == pygame.JOYBUTTONUP:
            name = BUTTON_MAPPING.get(event.button, f"Button {event.button}")
            self.log(f"{name} Up")
        elif event.type == pygame.JOYHATMOTION:
            val = HAT_MAPPING.get(event.value, str(event.value))
            self.log(f"Hat: {val}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ControllerGUI(root)
    root.mainloop()
    pygame.quit()
