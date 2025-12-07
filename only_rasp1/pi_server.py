#rasp1_V3
import cv2
import socket
import threading
import time

# --- 設定 ---
# PCのIP (映像の投げ先)
PC_IP = "192.168.50.10"
VIDEO_PORT = 5005

# 自分のIP (操作受信待機用)
MY_IP = "0.0.0.0"
CONTROL_PORT = 5006

# --- UDP送信 (映像) ---
def send_video():
    # カメラ初期化 (0番デバイス)
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)  # 軽量化のため解像度を下げる
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    print(f"[*] 映像送信開始 -> {PC_IP}:{VIDEO_PORT}")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
            
        # JPEG圧縮 (品質を50%に落としてデータ量を減らす)
        _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
        
        # UDPのパケットサイズ上限(約65KB)を超えないように注意
        if len(buffer) < 65000:
            try:
                udp_sock.sendto(buffer, (PC_IP, VIDEO_PORT))
            except Exception as e:
                pass # ネットワークエラーは無視して投げ続ける
        
        time.sleep(0.03) # 約30FPS制限

# --- TCP受信 (操作) ---
def receive_control():
    tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_server.bind((MY_IP, CONTROL_PORT))
    tcp_server.listen(1)
    
    print(f"[*] 操作待機中: TCP {CONTROL_PORT}")
    
    while True:
        conn, addr = tcp_server.accept()
        print(f"[*] PC接続: {addr}")
        
        with conn:
            # ★追加: 直前のコマンドを記憶する変数
            last_command = None
            
            while True:
                try:
                    data = conn.recv(1024)
                    if not data:
                        break
                    
                    # 受信データを文字列に変換し、改行で分割してリストにする
                    # (TCPは "STOP\nSTOP\n" のようにまとめて届くことがあるため)
                    commands_list = data.decode('utf-8').split('\n')

                    for command in commands_list:
                        command = command.strip()
                        
                        # 空文字はスキップ
                        if not command:
                            continue
                        
                        # ★変更点: コマンドが変わった時だけ処理・表示する
                        if command != last_command:
                            print(f"受信コマンド: {command}")
                            last_command = command
                            
                            # --- ここにGPIO制御を書く ---
                            # (状態が変わった瞬間だけGPIOを操作すればよいので効率的です)
                            if command == "FORWARD":
                                pass # GPIO.output(...)
                            elif command == "BACK":
                                pass
                            elif command == "LEFT":
                                pass
                            elif command == "RIGHT":
                                pass
                            elif command == "STOP":
                                pass
                            elif command == "DPAD_UP":
                                pass
                            elif command == "DPAD_DOWN":
                                pass
                            elif command == "DPAD_LEFT":
                                pass
                            elif command == "DPAD_RIGHT":
                                pass
                            elif command == "BUTTON_A":
                                pass
                            elif command == "BUTTON_B":
                                pass
                            elif command == "BUTTON_X":
                                pass
                            elif command == "BUTTON_Y":
                                pass
                            elif command == "TRIGGER_LT":
                                pass
                            elif command == "TRIGGER_RT":
                                pass
                            elif command == "RS_FORWARD":
                                pass
                            elif command == "RS_BACK":
                                pass
                            elif command == "RS_LEFT":
                                pass
                            elif command == "RS_RIGHT":
                                pass
                            elif command == "BUTTON_LB":
                                pass
                            elif command == "BUTTON_RB":
                                pass
                            elif command == "BUTTON_BACK":
                                pass
                            elif command == "BUTTON_START":
                                pass
                            elif command == "BUTTON_LS_PRESS":
                                pass
                            elif command == "BUTTON_RS_PRESS":
                                pass

                except Exception as e:
                    print(e)
                    break
        print("[!] 切断されました")

if __name__ == "__main__":
    # 映像送信をバックグラウンドへ
    video_thread = threading.Thread(target=send_video)
    video_thread.daemon = True
    video_thread.start()
    
    # 操作受信をメインで実行
    receive_control()