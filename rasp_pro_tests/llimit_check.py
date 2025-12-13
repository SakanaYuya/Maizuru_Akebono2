# rasp1_RAS_ver10.7
# マルチスレッド化: 受信待機中でも停止ロジックが止まらない完全並行処理版
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
PIN_SW_DEPLOY = 5   # 展開完了 (Hitで停止)
PIN_SW_STORE  = 6   # 収納完了 (Hitで停止)

# --- モーター制御設定 ---
PIN_PWM_LEFT = 12
PIN_DIR_LEFT = 20
PIN_PWM_RIGHT = 13
PIN_DIR_RIGHT = 21

PIN_PWM_LEFT_AUX = 18   # 展開機構
PIN_DIR_LEFT_AUX = 22

PIN_PWM_RIGHT_AUX = 19  # ウィンチ
PIN_DIR_RIGHT_AUX = 23

PWM_FREQ = 20000
DEADZONE = 0.15
TRIGGER_MIN_SPEED = 0.3

# --- グローバル変数 (スレッド間共有) ---
# 受信した最新のコントローラー情報をここに置く
shared_ctl_data = {}
shared_ctl_lock = threading.Lock() # データの衝突を防ぐ鍵

# プログラム終了フラグ
is_running = True

# --- SWログ用コールバック ---
def sw_log_callback(gpio, level, tick):
    state_str = "High (OPEN)" if level == 1 else "Low (HIT)"
    name = "DEPLOY(5)" if gpio == PIN_SW_DEPLOY else "STORE(6)"
    print(f"[Log] SW {name} changed to: {state_str}")

# --- クラス定義 (変更なし) ---
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

# --- 映像送信スレッド ---
def send_video():
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    while is_running:
        ret, frame = cap.read()
        if not ret: continue
        _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
        if len(buffer) < 65000:
            try:
                udp_sock.sendto(buffer, (PC_IP, VIDEO_PORT))
            except Exception: pass 
        time.sleep(0.03)

# =========================================================
# ★ 制御専用スレッド (Control Loop)
# 通信待ちの影響を受けずに、高速にスイッチ監視とモーター制御を行う
# =========================================================
def control_loop(pi):
    global is_running
    
    # 1. GPIO設定
    pi.set_mode(PIN_SW_DEPLOY, pigpio.INPUT)
    pi.set_pull_up_down(PIN_SW_DEPLOY, pigpio.PUD_UP)
    pi.set_mode(PIN_SW_STORE, pigpio.INPUT)
    pi.set_pull_up_down(PIN_SW_STORE, pigpio.PUD_UP)

    # コールバック登録
    cb_deploy = pi.callback(PIN_SW_DEPLOY, pigpio.EITHER_EDGE, sw_log_callback)
    cb_store = pi.callback(PIN_SW_STORE, pigpio.EITHER_EDGE, sw_log_callback)
    print("[*] Control Loop Started - Monitoring GPIO 5 & 6")

    # 2. デバイス初期化
    try:
        pca = PCA9685(pi)
        servo0 = Servo(pca, channel=4, min_angle=60, max_angle=120)
        servo1 = Servo(pca, channel=5, min_angle=0, max_angle=180)
        servo2 = Servo(pca, channel=6, min_angle=60, max_angle=130)
        servo3 = Servo(pca, channel=7, min_angle=0, max_angle=180)
        
        current_deg_0 = 90
        current_deg_1 = 0
        current_deg_2 = 90
        servo0.set_angle(90)
        servo1.set_angle(0)
        servo2.set_angle(90)
        servo3.set_angle(90)
    except Exception: pca = None

    try:
        motor_left = MotorController(pi, PIN_PWM_LEFT, PIN_DIR_LEFT, "Left")
        motor_right = MotorController(pi, PIN_PWM_RIGHT, PIN_DIR_RIGHT, "Right")
        motor_left_aux = MotorController(pi, PIN_PWM_LEFT_AUX, PIN_DIR_LEFT_AUX, "Deploy")
        motor_right_aux = MotorController(pi, PIN_PWM_RIGHT_AUX, PIN_DIR_RIGHT_AUX, "Winch")
    except Exception: return

    # 状態変数
    aux_auto_state = 0  # 0:停止, 1:展開, -1:収納

    while is_running:
        # --- A. 指令データのコピー ---
        # メインスレッドが書き込んでいる shared_ctl_data を安全に読み取る
        with shared_ctl_lock:
            ctl = shared_ctl_data.copy()
        
        # データがまだ空なら待機
        if not ctl:
            time.sleep(0.01)
            continue

        try:
            # --- B. センサー状態取得 ---
            sw_deploy_hit = (pi.read(PIN_SW_DEPLOY) == 0) # GPIO 5
            sw_store_hit = (pi.read(PIN_SW_STORE) == 0)   # GPIO 6

            # --- C. 緊急停止 ---
            if ctl.get("LS_PRESS") or ctl.get("RS_PRESS"):
                aux_auto_state = 0
                motor_left_aux.stop()

            # --- D. 新規指令受付 ---
            lb_pressed = ctl.get("BUTTON_LB", False)
            lt_value = ctl.get("TRIGGER_LT", -1.0)
            lt_normalized = (lt_value + 1.0) / 2.0

            if aux_auto_state == 0:
                if lb_pressed:
                    if not sw_deploy_hit:
                        aux_auto_state = 1
                        print("LOG: 展開開始 (-> GPIO5)")
                    else: pass

                elif lt_normalized > 0.1:
                    if not sw_store_hit:
                        aux_auto_state = -1
                        print("LOG: 収納開始 (-> GPIO6)")
                    else: pass

            # --- E. ★常時安全チェック (通信待ちなしで実行される) ---
            target_speed = 0.0

            if aux_auto_state == 1: # 展開中
                if sw_deploy_hit:
                    aux_auto_state = 0
                    target_speed = 0.0
                    print("LOG: ★ 展開完了停止 (GPIO5 HIT)")
                else:
                    target_speed = -1.0

            elif aux_auto_state == -1: # 収納中
                if sw_store_hit:
                    aux_auto_state = 0
                    target_speed = 0.0
                    print("LOG: ★ 収納完了停止 (GPIO6 HIT)")
                else:
                    target_speed = 0.6
            
            motor_left_aux.set_speed(target_speed)

            # --- F. その他のモーター・サーボ ---
            
            # ウィンチ
            rb_pressed = ctl.get("BUTTON_RB", False)
            rt_value = ctl.get("TRIGGER_RT", -1.0)
            rt_normalized = (rt_value + 1.0) / 2.0
            
            if rb_pressed:
                motor_right_aux.set_speed(1.0)
            elif rt_normalized > 0.1:
                speed = TRIGGER_MIN_SPEED + rt_normalized * (1.0 - TRIGGER_MIN_SPEED)
                motor_right_aux.set_speed(-speed)
            else:
                motor_right_aux.stop()

            # 足回り
            motor_left.set_speed(-ctl.get("LS_Y", 0.0))
            motor_right.set_speed(-ctl.get("RS_Y", 0.0))

            # サーボ
            if pca:
                hat_y = ctl.get("HAT_Y", 0)
                if hat_y != 0:
                    current_deg_0 = max(60, min(120, current_deg_0 + (5 * hat_y)))
                    servo0.set_angle(current_deg_0)

                hat_x = ctl.get("HAT_X", 0)
                if hat_x != 0:
                    current_deg_1 = max(0, min(180, current_deg_1 - (10 * hat_x)))
                    servo1.set_angle(current_deg_1)

                btn_y, btn_a = ctl.get("BUTTON_Y"), ctl.get("BUTTON_A")
                btn_x, btn_b = ctl.get("BUTTON_X"), ctl.get("BUTTON_B")
                
                if btn_y: current_deg_2 += 5
                if btn_a: current_deg_2 -= 5
                if btn_x: current_deg_2 -= 5
                if btn_b: current_deg_2 += 5
                
                if btn_y or btn_a or btn_x or btn_b:
                    current_deg_2 = max(60, min(130, current_deg_2))
                    servo2.set_angle(current_deg_2)
        
        except Exception as e:
            print(f"Control Loop Error: {e}")
        
        # 重要: CPUを占有しすぎないよう、しかし高速にループする
        time.sleep(0.01)

    # 終了時の停止処理
    motor_left.stop()
    motor_right.stop()
    motor_left_aux.stop()
    motor_right_aux.stop()
    cb_deploy.cancel()
    cb_store.cancel()

# --- メインスレッド: 通信受信専用 ---
def main_server():
    global shared_ctl_data, is_running
    
    tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_server.bind((MY_IP, CONTROL_PORT))
    tcp_server.listen(1)
    print(f"[*] V10.7 Server Ready: TCP {CONTROL_PORT}")

    while True:
        try:
            conn, addr = tcp_server.accept()
            print(f"[*] Connected: {addr}")
            
            with conn:
                while True:
                    # ここでブロック(停止)しても、別スレッドのcontrol_loopは止まらない！
                    data = conn.recv(1024)
                    if not data: break
                    
                    try:
                        received_json_str = data.decode('utf-8').strip()
                        # 複数パケット対策
                        if '}{' in received_json_str:
                            received_json_str = received_json_str.split('}{')[-1]
                            received_json_str = '{' + received_json_str

                        if received_json_str:
                            current_data = json.loads(received_json_str)
                            ctl = current_data.get("controller", {})
                            
                            # グローバル変数を更新
                            with shared_ctl_lock:
                                shared_ctl_data = ctl
                    except:
                        pass
        except Exception as e:
            print(f"Server Error: {e}")
            pass
        
        # 再接続待ちの間、モーター制御側は動き続ける（必要ならここでis_runningをFalseにしてもよいが、再接続を待つ）

if __name__ == "__main__":
    pi = pigpio.pi()
    if not pi.connected: exit()

    try:
        # 1. 映像送信スレッド開始
        video_thread = threading.Thread(target=send_video)
        video_thread.daemon = True
        video_thread.start()

        # 2. 制御ロジックスレッド開始 (これがあらゆるブロッキングから解放される)
        control_thread = threading.Thread(target=control_loop, args=(pi,))
        control_thread.daemon = True
        control_thread.start()

        # 3. メインスレッドで通信受信
        main_server()

    except KeyboardInterrupt:
        print("\n[*] Stopping...")
        is_running = False
        time.sleep(0.5)
    finally:
        pi.stop()