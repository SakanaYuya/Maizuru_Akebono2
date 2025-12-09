#rasp1_8_pca9685_full
import cv2
import socket
import threading
import time
import json
import pigpio
import math

# --- 通信設定 ---
PC_IP = "192.168.50.10"
VIDEO_PORT = 5005
MY_IP = "0.0.0.0"
CONTROL_PORT = 5006

# --- サーボ制御クラス定義 (変更なし) ---
class PCA9685:
    """pigpioを使用したPCA9685制御クラス"""
    MODE1 = 0x00
    PRESCALE = 0xFE
    LED0_ON_L = 0x06

    def __init__(self, pi, address=0x40, freq=50):
        self.pi = pi
        self.address = address
        self.handle = self.pi.i2c_open(1, self.address)
        self.set_frequency(freq)

    def write_reg(self, reg, value):
        self.pi.i2c_write_byte_data(self.handle, reg, value)
    
    def set_frequency(self, freq):
        prescale = int(round(25000000.0 / (4096.0 * freq)) - 1)
        mode_sleep = 0x10 | 0x20 
        self.write_reg(self.MODE1, mode_sleep)
        self.write_reg(self.PRESCALE, prescale)
        mode_wake = 0x80 | 0x20 | 0x01
        self.write_reg(self.MODE1, mode_wake)
        time.sleep(0.005)
        old_mode = self.pi.i2c_read_byte_data(self.handle, self.MODE1)
        new_mode = (old_mode & 0x7F) | 0x10 
        self.write_reg(self.MODE1, new_mode)
        self.write_reg(self.PRESCALE, prescale)
        self.write_reg(self.MODE1, old_mode)
        time.sleep(0.005)
        self.write_reg(self.MODE1, old_mode | 0x80)

    def set_pwm(self, channel, on, off):
        base_reg = self.LED0_ON_L + 4 * channel
        self.pi.i2c_write_i2c_block_data(self.handle, base_reg, [
            on & 0xFF, on >> 8, off & 0xFF, off >> 8
        ])

    def close(self):
        self.pi.i2c_close(self.handle)

class Servo:
    """角度指定で制御するためのラッパークラス"""
    def __init__(self, pca, channel, min_pulse=500, max_pulse=2400, min_angle=0, max_angle=180):
        self.pca = pca
        self.channel = channel
        self.min_pulse = min_pulse 
        self.max_pulse = max_pulse 
        self.min_angle = min_angle
        self.max_angle = max_angle
        self.current_angle = 0

    def angle_to_pulse(self, angle):
        if angle < self.min_angle: angle = self.min_angle
        if angle > self.max_angle: angle = self.max_angle
        pulse_us = self.min_pulse + (angle / 180.0) * (self.max_pulse - self.min_pulse)
        count = int((pulse_us / 20000.0) * 4096)
        return count

    def set_angle(self, angle):
        count = self.angle_to_pulse(angle)
        self.pca.set_pwm(self.channel, 0, count)
        self.current_angle = angle

# --- 映像送信処理 (変更なし) ---
def send_video():
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"[*] 映像送信開始 -> {PC_IP}:{VIDEO_PORT}")
    
    while True:
        ret, frame = cap.read()
        if not ret: continue
        _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
        if len(buffer) < 65000:
            try:
                udp_sock.sendto(buffer, (PC_IP, VIDEO_PORT))
            except Exception: pass 
        time.sleep(0.03)

# --- 操作受信 & サーボ制御処理 (マージ版) ---
def receive_control(pi):
    # 1. サーボの初期化・宣言
    try:
        pca = PCA9685(pi)
        
        # --- サーボ定義エリア ---
        # サーボ0: 基準90, 範囲60~120
        servo0 = Servo(pca, channel=0, min_angle=60, max_angle=120)
        
        # サーボ1: 基準90, 範囲0~180
        servo1 = Servo(pca, channel=1, min_angle=0, max_angle=180)
        
        # サーボ2: 基準90, 範囲60~130
        servo2 = Servo(pca, channel=2, min_angle=60, max_angle=130)
        
        # サーボ3: 指定なしのため汎用設定 (基準90, 範囲0~180)
        servo3 = Servo(pca, channel=3, min_angle=0, max_angle=180)

        # 全て基準位置(90度)へ移動
        servo0.set_angle(90)
        servo1.set_angle(90)
        servo2.set_angle(90)
        servo3.set_angle(90)
        
        # インチング動作(十字キー)用に現在の角度を変数で持つ
        current_deg_0 = 90
        current_deg_1 = 90
        
        print("[*] PCA9685初期化完了: サーボ0,1,2,3 準備OK")
        
    except Exception as e:
        print(f"[!] PCA9685初期化エラー: {e}")
        return

    # 2. 通信待機
    tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_server.bind((MY_IP, CONTROL_PORT))
    tcp_server.listen(1)
    
    print(f"[*] 操作待機中: TCP {CONTROL_PORT}")
    
    while True:
        conn, addr = tcp_server.accept()
        print(f"[*] PC接続: {addr}")
        
        with conn:
            last_received_data = None
            
            while True:
                try:
                    data = conn.recv(1024)
                    if not data: break
                    
                    received_json_str = data.decode('utf-8').strip()
                    if not received_json_str: continue
                    
                    try:
                        current_data = json.loads(received_json_str)
                    except json.JSONDecodeError: continue
                    
                    # データ更新時のみ処理
                    if current_data != last_received_data:
                        last_received_data = current_data
                        
                        ctl = current_data.get("controller", {})
                        kbd = current_data.get("keyboard", {})

                        # -------------------------------------------------
                        # ★ 1. サーボ制御エリア
                        # -------------------------------------------------
                        
                        # [サーボ0] 十字キー上下で操作 (インチング動作)
                        hat_y = ctl.get("HAT_Y", 0)
                        if hat_y != 0:
                            step = 5
                            if hat_y == 1: current_deg_0 += step   # 上
                            elif hat_y == -1: current_deg_0 -= step # 下
                            
                            # 範囲制限はServoクラス内でも行われるが、変数の発散を防ぐためここでもClamp推奨
                            if current_deg_0 > 120: current_deg_0 = 120
                            if current_deg_0 < 60: current_deg_0 = 60
                            
                            servo0.set_angle(current_deg_0)
                            print(f"ACT: サーボ0 -> {current_deg_0}度")

                        # [サーボ1] 十字キー右左で操作
                        hat_x = ctl.get("HAT_X", 0)
                        if hat_x != 0:
                            step = 10
                            if hat_x == 1: current_deg_1 += step    # 右入力でプラス
                            elif hat_x == -1: current_deg_1 -= step # 左入力でマイナス
                            
                            # 範囲制限 0~180
                            if current_deg_1 > 180: current_deg_1 = 180
                            if current_deg_1 < 0: current_deg_1 = 0
                            
                            servo1.set_angle(current_deg_1)
                            print(f"ACT: サーボ1(左右) -> {current_deg_1}度")

                        # -------------------------------------------------
                           # ★ 2. その他の入力ログ (元の機能を継続)
                        # -------------------------------------------------
                        
                        # スティック
                        ls_y = ctl.get("LS_Y", 0.0)
                        if abs(ls_y) > 0.5: print(f"LOG: 左スティック Y={ls_y:.2f}")

                        rs_y = ctl.get("RS_Y", 0.0)
                        if abs(rs_y) > 0.5: print(f"LOG: 右スティック Y={rs_y:.2f}")

                        # ボタン
                        if ctl.get("BUTTON_A"): print("LOG: ボタンA")
                        if ctl.get("BUTTON_B"): print("LOG: ボタンB")
                        if ctl.get("LS_PRESS"): print("LOG: 左スティック押し込み")
                        if ctl.get("RS_PRESS"): print("LOG: 右スティック押し込み")

                        # トリガー
                        lt = ctl.get("TRIGGER_LT", 0.0)
                        if lt > 0.5: print(f"LOG: LT入力 {lt:.2f}")
                        
                        # キーボード
                        if kbd.get("W"): print("LOG: Key W")
                        if kbd.get("S"): print("LOG: Key S")

                except Exception as e:
                    print(f"エラー: {e}")
                    break
        print("[!] 切断されました")

if __name__ == "__main__":
    pi = pigpio.pi()
    if not pi.connected:
        print("[!] pigpioデーモンに接続できません。'sudo pigpiod' を確認してください。")
        exit()

    try:
        video_thread = threading.Thread(target=send_video)
        video_thread.daemon = True
        video_thread.start()
        
        receive_control(pi)
        
    except KeyboardInterrupt:
        pass
    finally:
        print("終了処理")
        pi.stop()