#rasp1_9_motor_servo_integrated_pigpio_only_v2
import cv2
import socket
import threading
import time
import json
import pigpio

# --- 通信設定 ---
PC_IP = "192.168.50.10"
VIDEO_PORT = 5005
MY_IP = "0.0.0.0"
CONTROL_PORT = 5006

# --- 足回り（履帯）設定 ---
PIN_PWM_LEFT = 12   # 左足 PWM
PIN_DIR_LEFT = 20   # 左足 DIR
PIN_PWM_RIGHT = 13  # 右足 PWM
PIN_DIR_RIGHT = 21  # 右足 DIR

# --- ウィンチ設定 (新規追加) ---
# 右ウィンチ (RB/RT制御)
PIN_PWM_WINCH_R = 18  # 指定: PWM 18
PIN_DIR_WINCH_R = 23  # 任意: GPIO 23

# 左ウィンチ (LB/LT制御)
PIN_PWM_WINCH_L = 16  # 指定: PWM 16
PIN_DIR_WINCH_L = 24  # 任意: GPIO 24

PWM_FREQ = 20000    # PWM周波数 20kHz
DEADZONE = 0.15     # スティックのデッドゾーン

# --- サーボ制御クラス定義 ---
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

# --- モーター制御クラス (pigpio版) ---
class MotorController:
    """DC モーター制御 (PWM + DIR) - pigpio使用"""
    def __init__(self, pi, pwm_pin, dir_pin, name="Motor"):
        self.pi = pi
        self.pwm_pin = pwm_pin
        self.dir_pin = dir_pin
        self.name = name
        
        # ピンをOUTPUTに設定
        self.pi.set_mode(self.pwm_pin, pigpio.OUTPUT)
        self.pi.set_mode(self.dir_pin, pigpio.OUTPUT)
        
        # PWM周波数を設定 (20kHz)
        self.pi.set_PWM_frequency(self.pwm_pin, PWM_FREQ)
        self.pi.set_PWM_range(self.pwm_pin, 1000)  # 0-1000のデューティサイクル
        
        # 初期状態
        self.pi.set_PWM_dutycycle(self.pwm_pin, 0)
        self.pi.write(self.dir_pin, 0)
        
        self.current_speed = 0.0
        self.current_dir = 0
        
    def set_speed(self, speed):
        """
        速度設定
        speed: -1.0 ~ 1.0
          正: 前進 (DIR=HIGH)
          負: 後退 (DIR=LOW)
          0: 停止
        """
        # デッドゾーン処理
        if abs(speed) < 0.05: # ウィンチ用に少し緩めの閾値
            speed = 0.0
        
        # 方向判定
        if speed > 0:
            direction = 1
            duty = int(abs(speed) * 1000)  # 0-1000
        elif speed < 0:
            direction = 0
            duty = int(abs(speed) * 1000)
        else:
            direction = self.current_dir
            duty = 0
        
        # リミッター (念のため)
        if duty > 1000: duty = 1000
        
        # 方向が変わる場合は一旦停止（モーター保護）
        if direction != self.current_dir and self.current_speed != 0:
            self.pi.set_PWM_dutycycle(self.pwm_pin, 0)
            time.sleep(0.05)
        
        # 方向設定
        self.pi.write(self.dir_pin, direction)
        self.current_dir = direction
        
        # PWM出力
        self.pi.set_PWM_dutycycle(self.pwm_pin, duty)
        self.current_speed = speed
        
    def stop(self):
        """完全停止"""
        self.pi.set_PWM_dutycycle(self.pwm_pin, 0)
        self.current_speed = 0.0
        
    def cleanup(self):
        """終了処理"""
        self.pi.set_PWM_dutycycle(self.pwm_pin, 0)

# --- 映像送信処理 ---
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

# --- 操作受信 & 制御処理 ---
def receive_control(pi):
    # 1. サーボ初期化
    try:
        pca = PCA9685(pi)
        servo0 = Servo(pca, channel=0, min_angle=60, max_angle=120)
        servo1 = Servo(pca, channel=1, min_angle=0, max_angle=180)
        servo2 = Servo(pca, channel=2, min_angle=60, max_angle=130)
        servo3 = Servo(pca, channel=3, min_angle=0, max_angle=180) # 未使用
        
        servo0.set_angle(90)
        servo1.set_angle(90)
        servo2.set_angle(90)
        
        current_deg_0 = 90
        current_deg_1 = 90
        current_deg_2 = 90
        print("[*] PCA9685初期化完了")
    except Exception as e:
        print(f"[!] PCA9685初期化エラー: {e}")
        pca = None
    
    # 2. モーター初期化 (足回り + ウィンチ)
    try:
        # 足回り
        motor_left = MotorController(pi, PIN_PWM_LEFT, PIN_DIR_LEFT, "左足")
        motor_right = MotorController(pi, PIN_PWM_RIGHT, PIN_DIR_RIGHT, "右足")
        
        # ウィンチ
        winch_left = MotorController(pi, PIN_PWM_WINCH_L, PIN_DIR_WINCH_L, "左ウィンチ(LB/LT)")
        winch_right = MotorController(pi, PIN_PWM_WINCH_R, PIN_DIR_WINCH_R, "右ウィンチ(RB/RT)")
        
        print("[*] モーター＆ウィンチ初期化完了")
    except Exception as e:
        print(f"[!] モーター初期化エラー: {e}")
        return

    # 3. 通信待機
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
                    
                    if current_data != last_received_data:
                        last_received_data = current_data
                        
                        ctl = current_data.get("controller", {})
                        
                        # =================================================
                        # ★ 足回り制御 (戦車)
                        # =================================================
                        ls_y = -ctl.get("LS_Y", 0.0)
                        motor_left.set_speed(ls_y)
                        
                        rs_y = -ctl.get("RS_Y", 0.0)
                        motor_right.set_speed(rs_y)
                        
                        # =================================================
                        # ★ ウィンチ制御 (New!)
                        # =================================================
                        
                        # トリガーの値は -1.0(解放) ～ 1.0(最大) で来る想定
                        # 0.0 ～ 1.0 に正規化する
                        raw_lt = ctl.get("TRIGGER_LT", -1.0)
                        raw_rt = ctl.get("TRIGGER_RT", -1.0)
                        
                        lt_val = (raw_lt + 1.0) / 2.0  # 0.0 ~ 1.0
                        rt_val = (raw_rt + 1.0) / 2.0  # 0.0 ~ 1.0
                        
                        # ボタンは True/False
                        lb_pressed = ctl.get("BUTTON_LB", False)
                        rb_pressed = ctl.get("BUTTON_RB", False)
                        
                        # --- 左ウィンチ (LB:正転 / LT:逆転) ---
                        speed_wl = 0.0
                        if lb_pressed:
                            speed_wl += 1.0  # ボタンは最大出力
                        if lt_val > 0.05:    # トリガーはデッドゾーン考慮
                            speed_wl -= lt_val # 逆方向へアナログ出力
                            
                        winch_left.set_speed(speed_wl)
                        
                        # --- 右ウィンチ (RB:正転 / RT:逆転) ---
                        speed_wr = 0.0
                        if rb_pressed:
                            speed_wr += 1.0
                        if rt_val > 0.05:
                            speed_wr -= rt_val
                        
                        winch_right.set_speed(speed_wr)

                        # デバッグ表示 (値があるときだけ)
                        if abs(speed_wl) > 0.1 or abs(speed_wr) > 0.1:
                             print(f"WINCH: L={speed_wl:.2f}, R={speed_wr:.2f}")

                        # =================================================
                        # ★ サーボ制御
                        # =================================================
                        if pca:
                            # Servo0: HAT_Y
                            hat_y = ctl.get("HAT_Y", 0)
                            if hat_y != 0:
                                if hat_y == 1: current_deg_0 += 5
                                elif hat_y == -1: current_deg_0 -= 5
                                current_deg_0 = max(60, min(120, current_deg_0))
                                servo0.set_angle(current_deg_0)

                            # Servo1: HAT_X
                            hat_x = ctl.get("HAT_X", 0)
                            if hat_x != 0:
                                if hat_x == 1: current_deg_1 -= 10
                                elif hat_x == -1: current_deg_1 += 10
                                current_deg_1 = max(0, min(180, current_deg_1))
                                servo1.set_angle(current_deg_1)

                            # Servo2: Buttons
                            if ctl.get("BUTTON_Y") or ctl.get("BUTTON_B"): current_deg_2 += 5
                            if ctl.get("BUTTON_A") or ctl.get("BUTTON_X"): current_deg_2 -= 5
                            current_deg_2 = max(60, min(130, current_deg_2))
                            if servo2.current_angle != current_deg_2:
                                servo2.set_angle(current_deg_2)

                        # =================================================
                        # ★ 緊急停止 (スティック押し込み)
                        # =================================================
                        if ctl.get("LS_PRESS") or ctl.get("RS_PRESS"): 
                            print("LOG: 緊急停止")
                            motor_left.stop()
                            motor_right.stop()
                            winch_left.stop()
                            winch_right.stop()

                except Exception as e:
                    print(f"エラー: {e}")
                    break
        
        # 切断時停止
        print("[!] 切断 - 全モーター停止")
        motor_left.stop()
        motor_right.stop()
        winch_left.stop()
        winch_right.stop()

if __name__ == "__main__":
    pi = pigpio.pi()
    if not pi.connected:
        print("[!] pigpioデーモンに接続できません。")
        exit()

    try:
        video_thread = threading.Thread(target=send_video)
        video_thread.daemon = True
        video_thread.start()
        
        receive_control(pi)
        
    except KeyboardInterrupt:
        print("\n[*] キーボード割り込み")
    finally:
        print("[*] 終了処理...")
        pi.stop()
        print("[*] 完了")