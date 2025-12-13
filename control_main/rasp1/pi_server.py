# rasp1_RAS_ver13
# V12.1 + アーム展開角度制限 (30度残しで展開、収納は全閉)
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

# --- リミットスイッチ設定 ---
PIN_SW_DEPLOY = 5   # 展開完了 (Lowで停止)
PIN_SW_STORE  = 6   # 収納完了 (Lowで停止)

# --- モーター制御設定 ---
PIN_PWM_LEFT = 12
PIN_DIR_LEFT = 20
PIN_PWM_RIGHT = 13
PIN_DIR_RIGHT = 21

PIN_PWM_LEFT_AUX = 18   # 展開機構
PIN_DIR_LEFT_AUX = 22

PIN_PWM_RIGHT_AUX = 19  # ウィンチ
PIN_DIR_RIGHT_AUX = 23

# 追加モーター (回転機構)
PIN_PWM_EXTRA = 24
PIN_DIR_EXTRA = 25

PWM_FREQ = 20000
DEADZONE = 0.15
TRIGGER_MIN_SPEED = 0.3

# --- サーボ設定 (C=12, D=13) ---
SERVO_CH_ARM_L = 12     # 左アーム (ch C)
SERVO_CH_ARM_R = 13     # 右アーム (ch D)

# サーボ動作速度設定
ARM_MOVE_DELAY = 0.015 
ARM_MOVE_STEP  = 2

# ★ V13追加: 展開時の制限角度 (度)
# 30度残す = 0～180の範囲のうち、0～150までしか動かない
DEPLOY_ANGLE_OFFSET = 45

# --- ログ用コールバック関数 ---
def sw_log_callback(gpio, level, tick):
    state_str = "High (OPEN)" if level == 1 else "Low (HIT)"
    name = "DEPLOY(5)" if gpio == PIN_SW_DEPLOY else "STORE(6)"
    print(f"[Log] SW {name} changed to: {state_str}")

# --- クラス定義 ---
class PCA9685:
    MODE1 = 0x00
    PRESCALE = 0xFE
    LED0_ON_L = 0x06
    LED0_ON_H = 0x07
    LED0_OFF_L = 0x08
    LED0_OFF_H = 0x09
    def __init__(self, pi, address=0x40, freq=50):
        self.pi = pi
        self.address = address
        try:
            self.handle = self.pi.i2c_open(1, self.address)
            self.pi.i2c_write_byte_data(self.handle, self.MODE1, 0x00)
            time.sleep(0.01)
            self.pi.i2c_write_byte_data(self.handle, self.MODE1, 0xA1)
            time.sleep(0.01)
            self.set_frequency(freq)
            self.pi.i2c_write_byte_data(self.handle, self.LED0_ON_L, 0x00)
            self.pi.i2c_write_byte_data(self.handle, self.LED0_ON_H, 0x00)
            self.pi.i2c_write_byte_data(self.handle, self.LED0_OFF_L, 0x33)
            self.pi.i2c_write_byte_data(self.handle, self.LED0_OFF_H, 0x01)
        except Exception as e:
            print(f"[!] PCA9685 Error: {e}")
            raise e
    def write_reg(self, reg, value):
        self.pi.i2c_write_byte_data(self.handle, reg, value)
    def read_reg(self, reg):
        return self.pi.i2c_read_byte_data(self.handle, reg)
    def set_frequency(self, freq):
        prescale = int(round(25000000.0 / (4096.0 * freq)) - 1)
        old_mode = self.read_reg(self.MODE1)
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

class Servo:
    def __init__(self, pca, channel, min_pulse=500, max_pulse=2400, min_angle=0, max_angle=180):
        self.pca = pca
        self.channel = channel
        self.min_pulse = min_pulse 
        self.max_pulse = max_pulse 
        self.min_angle = min_angle
        self.max_angle = max_angle
    def angle_to_pulse(self, angle):
        if angle < self.min_angle: angle = self.min_angle
        if angle > self.max_angle: angle = self.max_angle
        pulse_us = self.min_pulse + (angle / 180.0) * (self.max_pulse - self.min_pulse)
        count = int((pulse_us / 20000.0) * 4096)
        return count
    def set_angle(self, angle):
        count = self.angle_to_pulse(angle)
        self.pca.set_pwm(self.channel, 0, count)

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

# --- 映像送信処理 ---
def send_video():
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    while True:
        ret, frame = cap.read()
        if not ret: continue
        _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
        if len(buffer) < 65000:
            try:
                udp_sock.sendto(buffer, (PC_IP, VIDEO_PORT))
            except Exception: pass 
        time.sleep(0.03)

# =========================================================
# ★ V13: 自動サーボ移動関数 (角度範囲調整版)
# =========================================================
def move_arms_smooth(servo_l, servo_r, deploy, conn):
    action_name = "アーム展開" if deploy else "アーム収納"
    print(f"LOG: {action_name} 開始")
    
    # ★ V13 ロジック変更
    # 0 = 全開(水平など), 180 = 格納
    # DEPLOY_ANGLE_OFFSET = 30 (30度手前で止める)
    
    if deploy:
        # 展開時: 0 から (180 - OFFSET) までループさせるイメージ
        # 実際の角度計算:
        # L: 180 -> 30 (180-OFFSET)
        # R: 0 -> 150 (OFFSET)
        # ループカウンタ i は「移動量」として 0 から (180-30)=150 まで回す
        start_i = 0
        end_i = 180 - DEPLOY_ANGLE_OFFSET  # 例: 150
    else:
        # 収納時: 展開位置(30/150) から 格納位置(180/0) まで戻す
        # ループカウンタ i は 30(OFFSET) から 180 まで回すことで
        # いきなり動かず、スムーズに続きから格納できる
        start_i = DEPLOY_ANGLE_OFFSET      # 例: 30
        end_i = 180

    conn.settimeout(0.01)
    
    try:
        for i in range(start_i, end_i + 1, ARM_MOVE_STEP):
            # 緊急停止チェック
            try:
                data = conn.recv(1024)
                if data:
                    js_str = data.decode('utf-8').strip()
                    if '}{' in js_str: js_str = '{' + js_str.split('}{')[-1]
                    try:
                        js = json.loads(js_str)
                        ctl = js.get("controller", {})
                        if ctl.get("LS_PRESS") or ctl.get("RS_PRESS"):
                            print("LOG: ! アーム動作中断 (緊急停止) !")
                            return False
                    except: pass
            except socket.timeout: pass
            except: pass

            # 角度計算 (共通ロジックで i の範囲だけ変える)
            if deploy:
                # 展開: i=0 -> 150
                # L: 180 -> 30
                # R: 0 -> 150
                angle_l = 180 - i
                angle_r = 0 + i
            else:
                # 収納: i=30 -> 180
                # L: 0 + i  (30 -> 180) ※Lは0基準で増やすと収納方向
                # R: 180 - i (150 -> 0) ※Rは180基準で減らすと収納方向
                angle_l = 0 + i
                angle_r = 180 - i
            
            servo_l.set_angle(angle_l)
            servo_r.set_angle(angle_r)
            time.sleep(ARM_MOVE_DELAY)
            
    finally:
        conn.settimeout(None)
    
    print(f"LOG: {action_name} 完了")
    return True

# =========================================================
# 自動シーケンス関数 (モーター移動)
# =========================================================
def run_motor_sequence(pi, motor, target_pin, speed, conn, seq_name):
    print(f"LOG: モーター移動開始 [{seq_name}] -> 目標GPIO {target_pin}")
    conn.settimeout(0.02) 
    success = True
    try:
        while True:
            if pi.read(target_pin) == 0: 
                print(f"LOG: 目標到達 ({seq_name}) - 停止")
                break
            try:
                data = conn.recv(1024)
                if data:
                    js_str = data.decode('utf-8').strip()
                    if '}{' in js_str: js_str = '{' + js_str.split('}{')[-1]
                    try:
                        js = json.loads(js_str)
                        ctl = js.get("controller", {})
                        if ctl.get("LS_PRESS") or ctl.get("RS_PRESS"):
                            print("LOG: ! 緊急停止 (操作入力) !")
                            success = False
                            break
                    except: pass
            except socket.timeout: pass
            except Exception:
                success = False
                break
            
            motor.set_speed(speed)
            time.sleep(0.005)
    finally:
        motor.stop()
        conn.settimeout(None)
    return success

# --- 操作受信 & 制御処理 ---
def receive_control(pi):
    pi.set_mode(PIN_SW_DEPLOY, pigpio.INPUT)
    pi.set_pull_up_down(PIN_SW_DEPLOY, pigpio.PUD_UP)
    pi.set_mode(PIN_SW_STORE, pigpio.INPUT)
    pi.set_pull_up_down(PIN_SW_STORE, pigpio.PUD_UP)

    cb_deploy = pi.callback(PIN_SW_DEPLOY, pigpio.EITHER_EDGE, sw_log_callback)
    cb_store = pi.callback(PIN_SW_STORE, pigpio.EITHER_EDGE, sw_log_callback)
    print("[*] SW Log Callbacks Registered")

    # サーボ初期化
    try:
        pca = PCA9685(pi)
        servo0 = Servo(pca, channel=4, min_angle=60, max_angle=120)
        servo1 = Servo(pca, channel=5, min_angle=0, max_angle=180)
        servo2 = Servo(pca, channel=6, min_angle=60, max_angle=130)
        
        servo_arm_l = Servo(pca, channel=SERVO_CH_ARM_L, min_angle=0, max_angle=180)
        servo_arm_r = Servo(pca, channel=SERVO_CH_ARM_R, min_angle=3, max_angle=180)
        
        servo0.set_angle(90)
        servo1.set_angle(0)
        servo2.set_angle(90)
        
        # 初期位置: 収納 (L:180, R:0) - 変わらず
        servo_arm_l.set_angle(180)
        servo_arm_r.set_angle(3) # Min limit
        
        current_deg_0 = 90
        current_deg_1 = 0
        current_deg_2 = 90
        print(f"[*] Servo Init OK: Arms on CH {SERVO_CH_ARM_L}(C), {SERVO_CH_ARM_R}(D)")
    except Exception as e: 
        print(f"[!] Servo Init Error: {e}")
        pca = None
    
    try:
        motor_left = MotorController(pi, PIN_PWM_LEFT, PIN_DIR_LEFT, "左")
        motor_right = MotorController(pi, PIN_PWM_RIGHT, PIN_DIR_RIGHT, "右")
        motor_left_aux = MotorController(pi, PIN_PWM_LEFT_AUX, PIN_DIR_LEFT_AUX, "展開")
        motor_right_aux = MotorController(pi, PIN_PWM_RIGHT_AUX, PIN_DIR_RIGHT_AUX, "ウィンチ")
        
        motor_extra = MotorController(pi, PIN_PWM_EXTRA, PIN_DIR_EXTRA, "追加モーター")
        print("[*] Extra Motor Init OK (GPIO 24/25)")
        
    except Exception: return

    tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_server.bind((MY_IP, CONTROL_PORT))
    tcp_server.listen(1)
    print(f"[*] V13 Ready: TCP {CONTROL_PORT}")
    
    while True:
        conn, addr = tcp_server.accept()
        print(f"[*] Connected: {addr}")
        
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

                        # 自動シーケンス
                        lt_val = ctl.get("TRIGGER_LT", -1.0)
                        lt_norm = (lt_val + 1.0) / 2.0
                        
                        if lt_norm > 0.5:
                            # 展開: 移動 -> アーム展開(150まで) -> 追加モーターON
                            if run_motor_sequence(pi, motor_left_aux, PIN_SW_DEPLOY, 1.0, conn, "展開移動"):
                                if pca: 
                                    if move_arms_smooth(servo_arm_l, servo_arm_r, deploy=True, conn=conn):
                                        print("LOG: 展開完了 -> 追加モーター回転開始")
                                        motor_extra.set_speed(-1.0) # DIR=0

                            last_received_data = None
                            continue

                        if ctl.get("BUTTON_LB", False):
                            # 収納: 追加モーターOFF -> アーム収納(30から180まで) -> 移動
                            print("LOG: 収納開始 -> 追加モーター停止")
                            motor_extra.stop()

                            if pca: 
                                if move_arms_smooth(servo_arm_l, servo_arm_r, deploy=False, conn=conn):
                                    time.sleep(0.5) 
                                    run_motor_sequence(pi, motor_left_aux, PIN_SW_STORE, -1.0, conn, "収納移動")
                            
                            last_received_data = None
                            continue

                        # 手動制御
                        motor_left.set_speed(-ctl.get("LS_Y", 0.0))
                        motor_right.set_speed(-ctl.get("RS_Y", 0.0))

                        if lt_norm > 0.1 and lt_norm <= 0.5:
                            speed = TRIGGER_MIN_SPEED + lt_norm * (1.0 - TRIGGER_MIN_SPEED)
                            motor_left_aux.set_speed(speed)
                        else:
                            motor_left_aux.stop()

                        rb_pressed = ctl.get("BUTTON_RB", False)
                        rt_val = ctl.get("TRIGGER_RT", -1.0)
                        rt_norm = (rt_val + 1.0) / 2.0
                        
                        if rb_pressed:
                            motor_right_aux.set_speed(1.0)
                        elif rt_norm > 0.1:
                            speed = TRIGGER_MIN_SPEED + rt_norm * (1.0 - TRIGGER_MIN_SPEED)
                            motor_right_aux.set_speed(-speed)
                        else:
                            motor_right_aux.stop()
                        
                        if pca:
                            hat_y = ctl.get("HAT_Y", 0)
                            if hat_y != 0:
                                current_deg_0 = max(60, min(120, current_deg_0 + (5 * hat_y)))
                                servo0.set_angle(current_deg_0)

                            hat_x = ctl.get("HAT_X", 0)
                            if hat_x != 0:
                                current_deg_1 = max(0, min(180, current_deg_1 - (10 * hat_x)))
                                servo1.set_angle(current_deg_1)

                            if ctl.get("BUTTON_Y"): current_deg_2 += 5
                            if ctl.get("BUTTON_A"): current_deg_2 -= 5
                            if ctl.get("BUTTON_X"): current_deg_2 -= 5
                            if ctl.get("BUTTON_B"): current_deg_2 += 5
                            if ctl.get("BUTTON_Y") or ctl.get("BUTTON_A") or ctl.get("BUTTON_X") or ctl.get("BUTTON_B"):
                                current_deg_2 = max(60, min(130, current_deg_2))
                                servo2.set_angle(current_deg_2)

                        if ctl.get("LS_PRESS") or ctl.get("RS_PRESS"):
                            motor_left.stop()
                            motor_right.stop()
                            motor_left_aux.stop()
                            motor_right_aux.stop()
                            motor_extra.stop()

                except Exception as e:
                    print(f"Error: {e}")
                    break
        
        motor_left.stop()
        motor_right.stop()
        motor_left_aux.stop()
        motor_right_aux.stop()
        motor_extra.stop()
        cb_deploy.cancel()
        cb_store.cancel()

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