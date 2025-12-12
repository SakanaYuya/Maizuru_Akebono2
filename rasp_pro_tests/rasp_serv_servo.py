#rasp1_6_servo
import cv2
import socket
import threading
import time
import json
import pigpio  # ★追加: pigpioライブラリ

# --- 設定 ---
# PCのIP (映像の投げ先)
PC_IP = "192.168.50.10"
VIDEO_PORT = 5005

# 自分のIP (操作受信待機用)
MY_IP = "0.0.0.0"
CONTROL_PORT = 5006

# --- ★追加: サーボ設定 (pigpio) ---
SERVO_PIN = 18       # サーボ信号線を接続するGPIOピン番号(BCM)
SERVO_MIN_DEG = 0    # 最小角度
SERVO_MAX_DEG = 180  # 最大角度
SERVO_STEP = 5       # 1回の入力で動く角度
SERVO_INIT = 90      # 初期角度

# パルス幅の設定 (一般的なサーボに合わせて500-2500μsとしています)
PULSE_MIN = 500
PULSE_MAX = 2500

# pigpioの初期化
pi = pigpio.pi()
if not pi.connected:
    print("[!] pigpioデーモンに接続できません。'sudo pigpiod' を実行しましたか？")
    exit()

# --- UDP送信 (映像) ---
def send_video():
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    print(f"[*] 映像送信開始 -> {PC_IP}:{VIDEO_PORT}")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
            
        _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
        
        if len(buffer) < 65000:
            try:
                udp_sock.sendto(buffer, (PC_IP, VIDEO_PORT))
            except Exception as e:
                pass 
        
        time.sleep(0.03)

# --- ★追加: サーボ角度設定用関数 ---
def set_servo_angle(angle):
    # 角度(0-180)をパルス幅(500-2500)に変換
    pulse = PULSE_MIN + (angle / 180.0) * (PULSE_MAX - PULSE_MIN)
    pi.set_servo_pulsewidth(SERVO_PIN, pulse)

# --- TCP受信 (操作) ---
def receive_control():
    tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_server.bind((MY_IP, CONTROL_PORT))
    tcp_server.listen(1)
    
    # 現在のサーボ角度を保持する変数
    current_servo_angle = SERVO_INIT
    # 初期位置へ移動
    set_servo_angle(current_servo_angle)
    
    print(f"[*] 操作待機中: TCP {CONTROL_PORT}")
    
    while True:
        conn, addr = tcp_server.accept()
        print(f"[*] PC接続: {addr}")
        
        with conn:
            last_received_data = None
            
            while True:
                try:
                    data = conn.recv(1024)
                    if not data:
                        break
                    
                    received_json_str = data.decode('utf-8').strip()
                    if not received_json_str:
                        continue
                    
                    try:
                        current_data = json.loads(received_json_str)
                    except json.JSONDecodeError:
                        continue
                    
                    if current_data != last_received_data:
                        # print(f"受信データ: {current_data}") # デバッグ時はコメントアウト解除
                        last_received_data = current_data
                        
                        controller_data = current_data.get("controller", {})
                        
                        # --- ★追加: 十字キーでサーボ操作 ---
                        hat_y = controller_data.get("HAT_Y", 0)
                        
                        # 前回のデータと異なるため、ここで1回分動かす処理を行う
                        # (PC側が押しっぱなしの連続送信をカットしているため、
                        #  「押した瞬間」に5度動く挙動になります)
                        
                        if hat_y == 1: # 上
                            current_servo_angle += SERVO_STEP
                            print(f"サーボ: 上 (+{SERVO_STEP}) -> {current_servo_angle}度")
                        elif hat_y == -1: # 下
                            current_servo_angle -= SERVO_STEP
                            print(f"サーボ: 下 (-{SERVO_STEP}) -> {current_servo_angle}度")
                        
                        # 範囲制限 (Clamp)
                        if current_servo_angle > SERVO_MAX_DEG:
                            current_servo_angle = SERVO_MAX_DEG
                        elif current_servo_angle < SERVO_MIN_DEG:
                            current_servo_angle = SERVO_MIN_DEG
                            
                        # サーボへ反映
                        if hat_y != 0: # 十字キー操作があった場合のみ送信
                            set_servo_angle(current_servo_angle)

                        # --- その他の表示ログ (既存) ---
                        # 必要に応じて残すか削除してください
                        if controller_data.get("BUTTON_A"):
                             print("ボタンA")

                except Exception as e:
                    print(f"エラー: {e}")
                    break
        print("[!] 切断されました")
        # 切断時にサーボを止める（信号を切る）場合は以下を有効化
        # pi.set_servo_pulsewidth(SERVO_PIN, 0)

if __name__ == "__main__":
    # 終了時のクリーンアップ処理用
    try:
        video_thread = threading.Thread(target=send_video)
        video_thread.daemon = True
        video_thread.start()
        
        receive_control()
    except KeyboardInterrupt:
        pass
    finally:
        print("終了処理: サーボ停止")
        pi.set_servo_pulsewidth(SERVO_PIN, 0) # サーボ脱力
        pi.stop()