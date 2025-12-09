#rasp1_9_motor_servo_integrated
import cv2
import socket
import threading
import time
import json
import pigpio
import RPi.GPIO as GPIO

# --- 通信設定 ---
PC_IP = "192.168.50.10"
VIDEO_PORT = 5005
MY_IP = "0.0.0.0"
CONTROL_PORT = 5006

# --- モーター制御設定 ---
# 左足(履帯) - ハードウェアPWM0
PIN_PWM_LEFT = 12   # 左モーターPWM (GPIO12 = PWM0)
PIN_DIR_LEFT = 20   # 左モーター方向

# 右足(履帯) - ハードウェアPWM1
PIN_PWM_RIGHT = 13  # 右モーターPWM (GPIO13 = PWM1)
PIN_DIR_RIGHT = 21  # 右モーター方向

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

# --- モーター制御クラス ---
class MotorController:
    """DC モーター制御 (PWM + DIR)"""
    def __init__(self, pwm_pin, dir_pin, name="Motor"):
        self.pwm_pin = pwm_pin
        self.dir_pin = dir_pin
        self.name = name
        
        GPIO.setup(self.pwm_pin, GPIO.OUT)
        GPIO.setup(self.dir_pin, GPIO.OUT)
        
        self.pwm = GPIO.PWM(self.pwm_pin, PWM_FREQ)
        self.pwm.start(0)
        GPIO.output(self.dir_pin, GPIO.LOW)
        
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
        if abs(speed) < DEADZONE:
            speed = 0.0
        
        # 方向判定
        if speed > 0:
            direction = GPIO.HIGH
            duty = abs(speed) * 100.0
        elif speed < 0:
            direction = GPIO.LOW
            duty = abs(speed) * 100.0
        else:
            direction = self.current_dir  # 停止時は方向維持
            duty = 0.0
        
        # 方向が変わる場合は一旦停止
        if direction != self.current_dir and self.current_speed != 0:
            self.pwm.ChangeDutyCycle(0)
            time.sleep(0.05)  # 慣性を考慮した短い停止
        
        # 方向設定
        GPIO.output(self.dir_pin, direction)
        self.current_dir = direction
        
        # PWM出力
        self.pwm.ChangeDutyCycle(duty)
        self.current_speed = speed
        
    def stop(self):
        """完全停止"""
        self.pwm.ChangeDutyCycle(0)
        self.current_speed = 0.0
        
    def cleanup(self):
        """終了処理"""
        self.pwm.stop()

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
    # 1. GPIO初期化
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    
    # 2. モーター初期化
    try:
        motor_left = MotorController(PIN_PWM_LEFT, PIN_DIR_LEFT, "左モーター")
        motor_right = MotorController(PIN_PWM_RIGHT, PIN_DIR_RIGHT, "右モーター")
        print("[*] モーター初期化完了")
    except Exception as e:
        print(f"[!] モーター初期化エラー: {e}")
        return
    
    # 3. サーボ初期化
    try:
        pca = PCA9685(pi)
        
        servo0 = Servo(pca, channel=0, min_angle=60, max_angle=120)
        servo1 = Servo(pca, channel=1, min_angle=0, max_angle=180)
        servo2 = Servo(pca, channel=2, min_angle=60, max_angle=130)
        servo3 = Servo(pca, channel=3, min_angle=0, max_angle=180)

        servo0.set_angle(90)
        servo1.set_angle(90)
        servo2.set_angle(90)
        servo3.set_angle(90)
        
        current_deg_0 = 90
        current_deg_1 = 90
        
        print("[*] PCA9685初期化完了: サーボ0,1,2,3 準備OK")
        
    except Exception as e:
        print(f"[!] PCA9685初期化エラー: {e}")
        pca = None

    # 4. 通信待機
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

                        # =================================================
                        # ★ モーター制御 (戦車型制御)
                        # =================================================
                        
                        # 左スティック Y軸 → 左モーター (前後)
                        # スティックの Y軸は上が負、下が正なので反転
                        ls_y = -ctl.get("LS_Y", 0.0)
                        motor_left.set_speed(ls_y)
                        
                        # 右スティック Y軸 → 右モーター (前後)
                        rs_y = -ctl.get("RS_Y", 0.0)
                        motor_right.set_speed(rs_y)
                        
                        # デバッグ出力
                        if abs(ls_y) > DEADZONE or abs(rs_y) > DEADZONE:
                            print(f"MOTOR: L={ls_y:+.2f}, R={rs_y:+.2f}")

                        # =================================================
                        # ★ サーボ制御 (十字キー)
                        # =================================================
                        
                        if pca:
                            # サーボ0: 十字キー上下
                            hat_y = ctl.get("HAT_Y", 0)
                            if hat_y != 0:
                                step = 5
                                if hat_y == 1: current_deg_0 += step
                                elif hat_y == -1: current_deg_0 -= step
                                
                                current_deg_0 = max(60, min(120, current_deg_0))
                                servo0.set_angle(current_deg_0)
                                print(f"SERVO0: {current_deg_0}°")

                            # サーボ1: 十字キー左右
                            hat_x = ctl.get("HAT_X", 0)
                            if hat_x != 0:
                                step = 10
                                if hat_x == 1: current_deg_1 += step
                                elif hat_x == -1: current_deg_1 -= step
                                
                                current_deg_1 = max(0, min(180, current_deg_1))
                                servo1.set_angle(current_deg_1)
                                print(f"SERVO1: {current_deg_1}°")

                        # =================================================
                        # ★ その他の入力ログ
                        # =================================================
                        
                        if ctl.get("BUTTON_A"): print("LOG: ボタンA")
                        if ctl.get("BUTTON_B"): print("LOG: ボタンB")
                        if ctl.get("LS_PRESS"): 
                            print("LOG: 左スティック押し込み - 緊急停止")
                            motor_left.stop()
                            motor_right.stop()
                        if ctl.get("RS_PRESS"): 
                            print("LOG: 右スティック押し込み - 緊急停止")
                            motor_left.stop()
                            motor_right.stop()

                        lt = ctl.get("TRIGGER_LT", 0.0)
                        if lt > 0.5: print(f"LOG: LT {lt:.2f}")
                        
                        if kbd.get("W"): print("LOG: Key W")
                        if kbd.get("S"): print("LOG: Key S")

                except Exception as e:
                    print(f"エラー: {e}")
                    break
        
        # 接続切断時は全モーター停止
        print("[!] 切断されました - モーター停止")
        motor_left.stop()
        motor_right.stop()

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
        print("\n[*] キーボード割り込み検出")
    finally:
        print("[*] 終了処理中...")
        GPIO.cleanup()
        pi.stop()
        print("[*] 終了完了")