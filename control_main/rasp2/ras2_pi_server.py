#rasp2_gpio_servo_v9
#Auto_Video_Flip_Added
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

# ==========================================
# ★ GPIOピン設定 (BCM番号)
# ==========================================

# --- 左モーター (Left Motor) ---
PIN_PWM_LEFT = 12   
PIN_DIR_LEFT = 20   

# --- 右モーター (Right Motor) ---
PIN_PWM_RIGHT = 13  
PIN_DIR_RIGHT = 21  

# --- サーボ (Servo) ---
PIN_SERVO_TILT = 18 # Top (0-180度 自由)
PIN_SERVO_PAN  = 19 # Under (35-180度 制限あり)

# ==========================================

# --- 速度・動作設定 ---
SPEED_SCALE = 0.7   # モーター速度

# サーボ移動速度
SERVO_SPEED_TILT = 10  # PIN 18
SERVO_SPEED_PAN  = 2   # PIN 19

PWM_FREQ = 20000
DEADZONE = 0.15
SERVO_MIN_PULSE = 500
SERVO_MAX_PULSE = 2500

# ★ スレッド間で角度情報を共有するための辞書
SHARED_STATE = {
    "tilt": 90  # 初期値
}

class DirectServo:
    def __init__(self, pi, pin, init_angle=0):
        self.pi = pi
        self.pin = pin
        self.current_angle = init_angle
        self.pi.set_mode(self.pin, pigpio.OUTPUT)
        self.set_angle_instant(init_angle)

    def set_angle_instant(self, angle):
        if angle < 0: angle = 0
        if angle > 180: angle = 180
        
        pulse_width = SERVO_MIN_PULSE + (angle / 180.0) * (SERVO_MAX_PULSE - SERVO_MIN_PULSE)
        self.pi.set_servo_pulsewidth(self.pin, pulse_width)
        self.current_angle = angle

    def move_to_slowly(self, target_angle, delay=0.01, step=1):
        if target_angle < 0: target_angle = 0
        if target_angle > 180: target_angle = 180
        start = int(self.current_angle)
        end = int(target_angle)
        step_val = step if start < end else -step
        if start != end:
            for angle in range(start, end, step_val):
                self.set_angle_instant(angle)
                time.sleep(delay)
        self.set_angle_instant(end)

    def stop(self):
        self.pi.set_servo_pulsewidth(self.pin, 0)

class MotorController:
    def __init__(self, pi, pwm_pin, dir_pin):
        self.pi = pi
        self.pwm_pin = pwm_pin
        self.dir_pin = dir_pin
        self.pi.set_mode(self.pwm_pin, pigpio.OUTPUT)
        self.pi.set_mode(self.dir_pin, pigpio.OUTPUT)
        self.pi.set_PWM_frequency(self.pwm_pin, PWM_FREQ)
        self.pi.set_PWM_range(self.pwm_pin, 1000) 
        self.stop()
        self.current_speed = 0.0
        self.current_dir = 0
        
    def set_speed(self, speed):
        if abs(speed) < DEADZONE: speed = 0.0
        if speed > 1.0: speed = 1.0
        if speed < -1.0: speed = -1.0

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

def send_video():
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"[*] 映像送信開始 -> {PC_IP}:{VIDEO_PORT}")
    
    while True:
        ret, frame = cap.read()
        if not ret: 
            time.sleep(0.1)
            continue
        
        # ==========================================
        # ★ V9追加: サーボ角度連動 自動回転ロジック
        # ==========================================
        # 現在のTilt角度を参照
        current_tilt_for_video = SHARED_STATE["tilt"]
        
        # 100度以上なら180度回転 (上下反転)
        if current_tilt_for_video >= 100:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        
        # JPEGエンコード
        _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
        if len(buffer) < 65000:
            try:
                udp_sock.sendto(buffer, (PC_IP, VIDEO_PORT))
            except Exception: pass 
        time.sleep(0.03)

def receive_control(pi):
    init_pan_angle = 90
    init_tilt_angle = 90

    # 共有状態の初期化
    SHARED_STATE["tilt"] = init_tilt_angle

    try:
        servo_tilt = DirectServo(pi, PIN_SERVO_TILT, init_angle=init_tilt_angle)
        servo_pan = DirectServo(pi, PIN_SERVO_PAN, init_angle=init_pan_angle)
        print(f"[*] サーボ初期化: Pan={init_pan_angle}, Tilt={init_tilt_angle}")
    except Exception as e:
        print(f"[!] サーボエラー: {e}")
        return

    try:
        motor_left = MotorController(pi, PIN_PWM_LEFT, PIN_DIR_LEFT)
        motor_right = MotorController(pi, PIN_PWM_RIGHT, PIN_DIR_RIGHT)
        print("[*] モーター初期化完了")
    except Exception as e:
        print(f"[!] モーターエラー: {e}")
        return

    tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp_server.bind((MY_IP, CONTROL_PORT))
    tcp_server.listen(1)
    
    current_tilt = init_tilt_angle
    current_pan = init_pan_angle

    print(f"[*] 接続待機中: {CONTROL_PORT}")

    while True:
        conn, addr = tcp_server.accept()
        print(f"[*] 接続: {addr}")
        
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

                        # 足回り
                        raw_ls_y = ctl.get("LS_Y", 0.0)
                        raw_rs_y = ctl.get("RS_Y", 0.0)
                        val_ls = raw_ls_y * SPEED_SCALE
                        val_rs = raw_rs_y * SPEED_SCALE
                        
                        motor_left.set_speed(val_rs) 
                        motor_right.set_speed(-val_ls)

                        # --- サーボ制御 ---

                        # Tilt (PIN 18)
                        hat_y = ctl.get("HAT_Y", 0)
                        if hat_y != 0:
                            if hat_y == 1: current_tilt += SERVO_SPEED_TILT
                            elif hat_y == -1: current_tilt -= SERVO_SPEED_TILT
                            
                            current_tilt = max(0, min(180, current_tilt))
                            servo_tilt.set_angle_instant(current_tilt)
                            print(f"Tilt: {current_tilt}")
                            
                            # ★ V9追加: 映像スレッドへ通知するために状態更新
                            SHARED_STATE["tilt"] = current_tilt

                        # Pan (PIN 19)
                        hat_x = ctl.get("HAT_X", 0)
                        if hat_x != 0:
                            if hat_x == 1: current_pan -= SERVO_SPEED_PAN
                            elif hat_x == -1: current_pan += SERVO_SPEED_PAN
                            
                            current_pan = max(35, min(180, current_pan))
                            servo_pan.set_angle_instant(current_pan)
                            print(f"Pan : {current_pan}")

                except Exception as e:
                    print(f"Loop Error: {e}")
                    break
        
        print("[!] 切断 - 停止")
        motor_left.stop()
        motor_right.stop()
        servo_pan.move_to_slowly(init_pan_angle) 
        servo_tilt.move_to_slowly(init_tilt_angle)
        # 状態リセット
        SHARED_STATE["tilt"] = init_tilt_angle

if __name__ == "__main__":
    pi = pigpio.pi()
    if not pi.connected:
        print("[!] pigpio未接続")
        exit()
    try:
        video_thread = threading.Thread(target=send_video)
        video_thread.daemon = True
        video_thread.start()
        receive_control(pi)
    except KeyboardInterrupt: pass
    finally:
        pi.stop()
        print("[*] 終了")