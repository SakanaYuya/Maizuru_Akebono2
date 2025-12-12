# #rasp1_RAS_ver10.1
#ラズパイの最新版コードの評価ファイル

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

# ==========================================
# ★ ピン設定 (GPIO BCM番号)
# ==========================================

# 1. 足回り
PIN_PWM_LEFT = 12
PIN_DIR_LEFT = 20
PIN_PWM_RIGHT = 13
PIN_DIR_RIGHT = 21

# 2. 回収機構展開 (Deploy)
PIN_PWM_DEPLOY = 18
PIN_DIR_DEPLOY = 22

# 3. ウィンチ
PIN_PWM_RIGHT_AUX = 19
PIN_DIR_RIGHT_AUX = 23

# 4. 回収ブレード (現状は操作なし、定義のみ)
PIN_PWM_BLADE = 24
PIN_DIR_BLADE = 25

# 5. リミットスイッチ (プルアップ設定)
PIN_LIMIT_1 = 5         # SW展開用
PIN_LIMIT_2 = 6         # SW収納用

# 6. LED
PIN_PWM_LED = 26

# ==========================================

PWM_FREQ = 20000
LED_FREQ = 1000
DEADZONE = 0.15
TRIGGER_MIN_SPEED = 0.3

# --- クラス定義 ---
class LedController:
    def __init__(self, pi, pin):
        self.pi = pi
        self.pin = pin
        self.pi.set_mode(self.pin, pigpio.OUTPUT)
        self.pi.set_PWM_frequency(self.pin, LED_FREQ)
        self.pi.set_PWM_range(self.pin, 255)
        self.set_brightness(0)
    def set_brightness(self, value):
        if value < 0: value = 0
        if value > 1.0: value = 1.0
        duty = int(value * 255)
        self.pi.set_PWM_dutycycle(self.pin, duty)
    def off(self):
        self.pi.set_PWM_dutycycle(self.pin, 0)

class PCA9685:
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
        old_mode = self.pi.i2c_read_byte_data(self.handle, self.MODE1)
        mode_sleep = (old_mode & 0x7F) | 0x10
        self.write_reg(self.MODE1, mode_sleep)
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

class MotorController:
    def __init__(self, pi, pwm_pin, dir_pin, name="Motor"):
        self.pi = pi
        self.pwm_pin = pwm_pin
        self.dir_pin = dir_pin
        self.name = name
        self.pi.set_mode(self.pwm_pin, pigpio.OUTPUT)
        self.pi.set_mode(self.dir_pin, pigpio.OUTPUT)
        self.pi.set_PWM_frequency(self.pwm_pin, PWM_FREQ)
        self.pi.set_PWM_range(self.pwm_pin, 1000)
        self.pi.set_PWM_dutycycle(self.pwm_pin, 0)
        self.pi.write(self.dir_pin, 0)
        self.current_speed = 0.0
        self.current_dir = 0
    def set_speed(self, speed):
        if abs(speed) < DEADZONE: speed = 0.0
        if speed > 0:
            direction = 1
            duty = int(abs(speed) * 1000)
        elif speed < 0:
            direction = 0
            duty = int(abs(speed) * 1000)
        else:
            direction = self.current_dir
            duty = 0
        if direction != self.current_dir and self.current_speed != 0:
            self.pi.set_PWM_dutycycle(self.pwm_pin, 0)
            time.sleep(0.05)
        self.pi.write(self.dir_pin, direction)
        self.current_dir = direction
        self.pi.set_PWM_dutycycle(self.pwm_pin, duty)
        self.current_speed = speed
    def stop(self):
        self.pi.set_PWM_dutycycle(self.pwm_pin, 0)
        self.current_speed = 0.0

# --- 映像送信 ---
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

# --- メイン制御 ---
def receive_control(pi):
    # 初期化
    try:
        pca = PCA9685(pi)
        servo0 = Servo(pca, channel=4, min_angle=60, max_angle=120)
        servo1 = Servo(pca, channel=5, min_angle=0, max_angle=180)
        servo2 = Servo(pca, channel=6, min_angle=60, max_angle=130)
        servo3 = Servo(pca, channel=7, min_angle=0, max_angle=180)
        servo0.set_angle(90); servo1.set_angle(90); servo2.set_angle(90)
        current_deg_0 = 90; current_deg_1 = 90; current_deg_2 = 90
        print("[*] サーボ初期化OK")
    except Exception as e:
        print(f"[!] サーボ初期化NG: {e}")
        import traceback
        traceback.print_exc() # 詳細なエラー箇所を表示
        pca = None

    try:
        motor_left = MotorController(pi, PIN_PWM_LEFT, PIN_DIR_LEFT, "左足")
        motor_right = MotorController(pi, PIN_PWM_RIGHT, PIN_DIR_RIGHT, "右足")
        motor_deploy = MotorController(pi, PIN_PWM_DEPLOY, PIN_DIR_DEPLOY, "展開")
        motor_right_aux = MotorController(pi, PIN_PWM_RIGHT_AUX, PIN_DIR_RIGHT_AUX, "ウィンチ")

        # 定義のみ維持
        motor_blade = MotorController(pi, PIN_PWM_BLADE, PIN_DIR_BLADE, "ブレード")

        led_main = LedController(pi, PIN_PWM_LED)

        # ★ リミットスイッチ: プルアップ設定
        pi.set_mode(PIN_LIMIT_1, pigpio.INPUT)
        pi.set_mode(PIN_LIMIT_2, pigpio.INPUT)
        pi.set_pull_up_down(PIN_LIMIT_1, pigpio.PUD_UP) # PULL_UP
        pi.set_pull_up_down(PIN_LIMIT_2, pigpio.PUD_UP) # PULL_UP

        print("[*] モーター/LED/SW(Pull-Up) 初期化OK")
    except Exception as e:
        print(f"[!] HW初期化エラー: {e}")
        return

    tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_server.bind((MY_IP, CONTROL_PORT))
    tcp_server.listen(1)
    print(f"[*] 待機中: {CONTROL_PORT}")

    start_time = time.time()

    # 状態監視用の前回の値
    last_sw1 = pi.read(PIN_LIMIT_1)
    last_sw2 = pi.read(PIN_LIMIT_2)

    while True:
        conn, addr = tcp_server.accept()
        print(f"[*] 接続: {addr}")

        with conn:
            last_received_data = None
            while True:
                try:
                    # LEDデモ
                    elapsed = time.time() - start_time
                    led_main.set_brightness((math.sin(elapsed * 3) + 1) / 2)

                    # ----------------------------------------------------
                    # ★ リミットスイッチのログ出力修正部分 (プルアップ対応)
                    # ----------------------------------------------------
                    curr_sw1 = pi.read(PIN_LIMIT_1) # Pull-Up: 0=ON (GND短絡時), 1=OFF
                    curr_sw2 = pi.read(PIN_LIMIT_2)

                    if curr_sw1 != last_sw1:
                        if curr_sw1 == 0: # 0でONとみなす
                            print("LOG: SW展開動作 (ON 検知)")
                        else:
                            print("LOG: SW展開動作 (OFF 開放)")
                        last_sw1 = curr_sw1

                    if curr_sw2 != last_sw2:
                        if curr_sw2 == 0: # 0でONとみなす
                            print("LOG: SW収納動作 (ON 検知)")
                        else:
                            print("LOG: SW収納動作 (OFF 開放)")
                        last_sw2 = curr_sw2
                    # ----------------------------------------------------

                    conn.settimeout(0.1)
                    try:
                        data = conn.recv(1024)
                    except socket.timeout:
                        continue
                    if not data: break

                    received_json_str = data.decode('utf-8').strip()
                    if not received_json_str: continue
                    try:
                        current_data = json.loads(received_json_str)
                    except json.JSONDecodeError: continue

                    if current_data != last_received_data:
                        last_received_data = current_data
                        ctl = current_data.get("controller", {})

                        # --- 動作ログ付き制御 ---

                        # 足回り
                        ls_y = -ctl.get("LS_Y", 0.0)
                        rs_y = -ctl.get("RS_Y", 0.0)
                        motor_left.set_speed(ls_y)
                        motor_right.set_speed(rs_y)

                        # デバッグ出力を追加
                        if abs(ls_y) > DEADZONE or abs(rs_y) > DEADZONE:
                             print(f"LOG: 足回り L={ls_y:+.2f}, R={rs_y:+.2f}")

                        # 展開機構 (Deploy)
                        lb_pressed = ctl.get("BUTTON_LB", False)
                        lt_val = (ctl.get("TRIGGER_LT", 0.0) + 1.0) / 2.0

                        current_deploy_speed = 0.0
                        if lb_pressed:
                            current_deploy_speed = -1.0
                            print("LOG: Deploy <BACK> (LB)")
                        elif lt_val > 0.1:
                            current_deploy_speed = TRIGGER_MIN_SPEED + lt_val * (1.0 - TRIGGER_MIN_SPEED)
                            print(f"LOG: Deploy <FWD> (LT) {current_deploy_speed:.2f}")

                        if current_deploy_speed != 0:
                            motor_deploy.set_speed(current_deploy_speed)
                        else:
                            motor_deploy.stop()

                        # 回収ブレード (停止)
                        motor_blade.stop()

                        # 右ウィンチ
                        rb = ctl.get("BUTTON_RB", False)
                        rt_val = (ctl.get("TRIGGER_RT", 0.0) + 1.0) / 2.0

                        current_rw_speed = 0.0
                        if rb:
                            current_rw_speed = 1.0
                            print("LOG: R-Winch <FWD> (RB)")
                        elif rt_val > 0.1:
                            spd = TRIGGER_MIN_SPEED + rt_val * (1.0 - TRIGGER_MIN_SPEED)
                            current_rw_speed = -spd
                            print(f"LOG: R-Winch <BACK> (RT) {current_rw_speed:.2f}")

                        if current_rw_speed != 0:
                            motor_right_aux.set_speed(current_rw_speed)
                        else:
                            motor_right_aux.stop()

                        # サーボ
                        if pca:
                            hat_y = ctl.get("HAT_Y", 0)
                            if hat_y:
                                current_deg_0 = max(60, min(120, current_deg_0 + 5*hat_y))
                                servo0.set_angle(current_deg_0)
                                print(f"LOG: Servo0 {current_deg_0}")
                            hat_x = ctl.get("HAT_X", 0)
                            if hat_x:
                                current_deg_1 = max(0, min(180, current_deg_1 - 10*hat_x))
                                servo1.set_angle(current_deg_1)
                            if ctl.get("BUTTON_Y") or ctl.get("BUTTON_B"): current_deg_2 += 5
                            if ctl.get("BUTTON_A") or ctl.get("BUTTON_X"): current_deg_2 -= 5
                            current_deg_2 = max(60, min(130, current_deg_2))
                            if servo2.current_angle != current_deg_2:
                                servo2.set_angle(current_deg_2)
                                print(f"LOG: Servo2 {current_deg_2}")

                        # 緊急停止
                        if ctl.get("LS_PRESS") or ctl.get("RS_PRESS"):
                            motor_left.stop(); motor_right.stop()
                            motor_deploy.stop(); motor_right_aux.stop()
                            motor_blade.stop(); led_main.off()
                            print("LOG: *** EMERGENCY STOP ***")

                except Exception as e:
                    print(f"Loop Error: {e}")
                    break

        print("[!] 切断")
        motor_left.stop(); motor_right.stop()
        motor_deploy.stop(); motor_right_aux.stop()
        motor_blade.stop(); led_main.off()

if __name__ == "__main__":
    pi = pigpio.pi()
    if not pi.connected: exit()
    try:
        video_thread = threading.Thread(target=send_video)
        video_thread.daemon = True
        video_thread.start()
        receive_control(pi)
    except KeyboardInterrupt: pass
    finally: pi.stop()