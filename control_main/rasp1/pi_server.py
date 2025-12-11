#rasp1_RAS_ver9.3
# Deep Sleep対策・強力WakeUp実装版
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

# --- モーター制御設定 ---
# 左足(履帯) - ハードウェアPWM0
PIN_PWM_LEFT = 12   # 左モーターPWM (GPIO12 = PWM0)
PIN_DIR_LEFT = 20   # 左モーター方向

# 右足(履帯) - ハードウェアPWM1
PIN_PWM_RIGHT = 13  # 右モーターPWM (GPIO13 = PWM1)
PIN_DIR_RIGHT = 21  # 右モーター方向

# モーター (LB/LT, RB/RT用)
# GPIO 18, 19 を使用 (PWM可能ピン)
PIN_PWM_LEFT_AUX = 18   # 回収モーターPWM
PIN_DIR_LEFT_AUX = 22   # 回収モーター方向

PIN_PWM_RIGHT_AUX = 19  # ウィンチモーターPWM
PIN_DIR_RIGHT_AUX = 23  # ウィンチモーター方向

PWM_FREQ = 20000    # PWM周波数 20kHz
DEADZONE = 0.15     # スティックのデッドゾーン
TRIGGER_MIN_SPEED = 0.3  # トリガーの最小速度 (30%)

# --- サーボ制御クラス定義 (Wake-Up機能統合版) ---
class PCA9685:
    """pigpioを使用したPCA9685制御クラス (Deep Sleep解除機能付き)"""
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
            
            # ==========================================
            # ★ Deep Sleep 解除 & 強制Wake-Up シーケンス
            # ==========================================
            print("[PCA9685] ICのリセットと起床シーケンス実行...")
            
            # 1. MODE1レジスタを 0x00 に書き込み (Sleepビットを解除 = 起床)
            # これにより内部発振器が強制的に動き出します
            self.pi.i2c_write_byte_data(self.handle, self.MODE1, 0x00)
            time.sleep(0.01) # 起床待ち

            # 2. 再度設定 (Auto-Increment有効化など)
            self.pi.i2c_write_byte_data(self.handle, self.MODE1, 0xA1) 
            time.sleep(0.01)

            # 3. 周波数設定 (set_frequencyメソッド内でスリープ→復帰を行う)
            self.set_frequency(freq)

            # ==========================================
            # ★ 動作確認用: CH0 強制駆動 (90度)
            # ==========================================
            print("[PCA9685] 起動確認: CH0を90度に固定します")
            # ONタイミング = 0
            self.pi.i2c_write_byte_data(self.handle, self.LED0_ON_L, 0x00)
            self.pi.i2c_write_byte_data(self.handle, self.LED0_ON_H, 0x00)
            # OFFタイミング = 307 (約1.5ms幅 = 90度)
            self.pi.i2c_write_byte_data(self.handle, self.LED0_OFF_L, 0x33) # 0x33 = 51
            self.pi.i2c_write_byte_data(self.handle, self.LED0_OFF_H, 0x01) # 0x0100 = 256 -> Total 307

        except Exception as e:
            print(f"[!] PCA9685接続エラー: {e}")
            raise e

    def write_reg(self, reg, value):
        self.pi.i2c_write_byte_data(self.handle, reg, value)
    
    def read_reg(self, reg):
        return self.pi.i2c_read_byte_data(self.handle, reg)
    
    def set_frequency(self, freq):
        prescale = int(round(25000000.0 / (4096.0 * freq)) - 1)
        
        # 1. 現在のモード設定を読み込む
        old_mode = self.read_reg(self.MODE1)
        
        # 2. スリープモードにする (設定書き込みのため)
        new_mode = (old_mode & 0x7F) | 0x10 
        self.write_reg(self.MODE1, new_mode) 
        
        # 3. プリスケーラー(周波数)を設定
        self.write_reg(self.PRESCALE, prescale)
        
        # 4. 元のモードに戻す (ここでWake-Up)
        self.write_reg(self.MODE1, old_mode)
        time.sleep(0.005)
        
        # 5. リスタート
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
        if abs(speed) < DEADZONE:
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
        
        # 方向が変わる場合は一旦停止
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
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640) #幅(320標準)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480) #高さ(240標準)
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"[*] 映像送信開始 -> {PC_IP}:{VIDEO_PORT}")
    
    while True:
        ret, frame = cap.read()
        if not ret: continue
        _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])#画質強度(標準30)
        if len(buffer) < 65000:
            try:
                udp_sock.sendto(buffer, (PC_IP, VIDEO_PORT))
            except Exception: pass 
        time.sleep(0.03)

# --- 操作受信 & 制御処理 ---
def receive_control(pi):
    # 1. サーボ初期化
    try:
        # ★ここでPCA9685クラスを呼ぶと、自動的にWake-UpとCH0動作チェックが走ります
        pca = PCA9685(pi)
        
        # チャンネルをシフト: 0→4, 1→5, 2→6, 3→7
        servo0 = Servo(pca, channel=4, min_angle=60, max_angle=120)
        servo1 = Servo(pca, channel=5, min_angle=0, max_angle=180)
        servo2 = Servo(pca, channel=6, min_angle=60, max_angle=130)
        servo3 = Servo(pca, channel=7, min_angle=0, max_angle=180)

        servo0.set_angle(90)
        servo1.set_angle(0)
        servo2.set_angle(90)
        servo3.set_angle(90)
        
        current_deg_0 = 90
        current_deg_1 = 0
        current_deg_2 = 90
        
        print("[*] PCA9685初期化完了: CH0(Test)駆動確認済, CH4,5,6,7 準備OK")
        
    except Exception as e:
        print(f"[!] PCA9685初期化エラー: {e}")
        pca = None
    
    # 2. モーター初期化 (pigpio使用、GPIO不要)
    try:
        motor_left = MotorController(pi, PIN_PWM_LEFT, PIN_DIR_LEFT, "左モーター")
        motor_right = MotorController(pi, PIN_PWM_RIGHT, PIN_DIR_RIGHT, "右モーター")
        motor_left_aux = MotorController(pi, PIN_PWM_LEFT_AUX, PIN_DIR_LEFT_AUX, "回収モーター")
        motor_right_aux = MotorController(pi, PIN_PWM_RIGHT_AUX, PIN_DIR_RIGHT_AUX, "ウィンチモーター")
        print("[*] モーター初期化完了: 足モーター×2, 特殊モーター×2")
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
                    
                    # データ更新時のみ処理
                    if current_data != last_received_data:
                        last_received_data = current_data
                        
                        ctl = current_data.get("controller", {})
                        kbd = current_data.get("keyboard", {})

                        # =================================================
                        # ★ モーター制御
                        # =================================================
                        
                        # --- 主モーター (左右スティック) ---
                        # 左スティック Y軸 → 左モーター (前後)
                        ls_y = -ctl.get("LS_Y", 0.0)
                        motor_left.set_speed(ls_y)
                        
                        # 右スティック Y軸 → 右モーター (前後)
                        rs_y = -ctl.get("RS_Y", 0.0)
                        motor_right.set_speed(rs_y)
                        
                        # デバッグ出力
                        if abs(ls_y) > DEADZONE or abs(rs_y) > DEADZONE:
                            print(f"MOTOR: L={ls_y:+.2f}, R={rs_y:+.2f}")

                        # --- 補助モーター (LB/LT, RB/RT) ---
                        
                        # [左側 - 維持] LB=後退(-), LT=前進(+)
                        lb_pressed = ctl.get("BUTTON_LB", False)
                        lt_value = ctl.get("TRIGGER_LT", 0.0)  # -1.0~1.0
                        lt_normalized = (lt_value + 1.0) / 2.0  # 0.0~1.0
                        
                        if lb_pressed:
                            # LB: 後退 (最大速度)
                            motor_left_aux.set_speed(-1.0)
                            print("MOTOR_AUX: LB 後退")
                        elif lt_normalized > 0.1:
                            # LT: 前進 (可変速度: 30%~100%)
                            speed = TRIGGER_MIN_SPEED + lt_normalized * (1.0 - TRIGGER_MIN_SPEED)
                            motor_left_aux.set_speed(speed)
                            print(f"MOTOR_AUX: LT 前進 {speed:.2f}")
                        else:
                            motor_left_aux.stop()
                        
                        # [右側 - 反転変更] RB=前進(+), RT=後退(-) 
                        rb_pressed = ctl.get("BUTTON_RB", False)
                        rt_value = ctl.get("TRIGGER_RT", 0.0)  # -1.0~1.0
                        rt_normalized = (rt_value + 1.0) / 2.0  # 0.0~1.0
                        
                        if rb_pressed:
                            # RB: 前進 (最大速度) ★ここを変更
                            motor_right_aux.set_speed(1.0)
                            print("MOTOR_AUX: RB 前進(反転設定)")
                        elif rt_normalized > 0.1:
                            # RT: 後退 (可変速度: -30%~-100%) ★ここを変更
                            speed_mag = TRIGGER_MIN_SPEED + rt_normalized * (1.0 - TRIGGER_MIN_SPEED)
                            motor_right_aux.set_speed(-speed_mag) # 負の値にする
                            print(f"MOTOR_AUX: RT 後退(反転設定) {-speed_mag:.2f}")
                        else:
                            motor_right_aux.stop()

                        # =================================================
                        # ★ サーボ制御 (十字キー+ボタン)
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

                            # サーボ1: 十字キー左右 (逆方向)
                            hat_x = ctl.get("HAT_X", 0)
                            if hat_x != 0:
                                step = 10
                                if hat_x == 1: current_deg_1 -= step  # 右入力で減少
                                elif hat_x == -1: current_deg_1 += step  # 左入力で増加
                                
                                current_deg_1 = max(0, min(180, current_deg_1))
                                servo1.set_angle(current_deg_1)
                                print(f"SERVO1: {current_deg_1}°")

                            # サーボ2: ボタンY(上下), ボタンX(左右)
                            button_y = ctl.get("BUTTON_Y", False)
                            button_x = ctl.get("BUTTON_X", False)
                            button_a = ctl.get("BUTTON_A", False)
                            button_b = ctl.get("BUTTON_B", False)
                            
                            if button_y or button_a or button_x or button_b:
                                step = 5
                                if button_y:  # Y押下 = 増加
                                    current_deg_2 += step
                                elif button_a:  # A押下 = 減少
                                    current_deg_2 -= step
                                
                                # X/Bでも制御可能にする場合
                                if button_x:  # X押下 = 減少
                                    current_deg_2 -= step
                                elif button_b:  # B押下 = 増加
                                    current_deg_2 += step
                                
                                current_deg_2 = max(60, min(130, current_deg_2))
                                servo2.set_angle(current_deg_2)
                                print(f"SERVO2: {current_deg_2}°")

                        # =================================================
                        # ★ その他の入力ログ
                        # =================================================
                        
                        if ctl.get("LS_PRESS"): 
                            print("LOG: 左スティック押し込み - 全モーター緊急停止")
                            motor_left.stop()
                            motor_right.stop()
                            motor_left_aux.stop()
                            motor_right_aux.stop()
                        if ctl.get("RS_PRESS"): 
                            print("LOG: 右スティック押し込み - 全モーター緊急停止")
                            motor_left.stop()
                            motor_right.stop()
                            motor_left_aux.stop()
                            motor_right_aux.stop()

                        lt = ctl.get("TRIGGER_LT", 0.0)
                        if lt > 0.5: print(f"LOG: LT {lt:.2f}")
                        
                        if kbd.get("W"): print("LOG: Key W")
                        if kbd.get("S"): print("LOG: Key S")

                except Exception as e:
                    print(f"エラー: {e}")
                    break
        
        # 接続切断時は全モーター停止
        print("[!] 切断されました - 全モーター停止")
        motor_left.stop()
        motor_right.stop()
        motor_left_aux.stop()
        motor_right_aux.stop()

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
        pi.stop()
        print("[*] 終了完了")