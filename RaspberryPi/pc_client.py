import cv2
import socket
import numpy as np
import threading
import pygame
import time

# --- 設定 ---
# 自分のIP (受信待機用)
MY_IP = "0.0.0.0" 
VIDEO_PORT = 5005

# ラズパイのIP (送信先)
RPI_IP = "192.168.50.20"
CONTROL_PORT = 5006

# --- UDP受信 (映像) ---
def receive_video():
    # UDPソケット作成
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.bind((MY_IP, VIDEO_PORT))
    print(f"[*] 映像待機中: UDP {VIDEO_PORT}")

    while True:
        try:
            # データ受信 (パケットサイズは少し大きめに確保)
            data, addr = udp_sock.recvfrom(65535)
            
            # 受信データをバイナリ配列に変換
            nparr = np.frombuffer(data, np.uint8)
            
            # デコードして画像にする
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is not None:
                cv2.imshow("Raspberry Pi Camera (Low Latency)", frame)
                
            # 'q'で終了
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        except Exception as e:
            print(f"Video Error: {e}")

    udp_sock.close()
    cv2.destroyAllWindows()

# --- TCP送信 (操作) ---
def send_control():
    # Pygame初期化 (キー入力用)
    pygame.init()
    screen = pygame.display.set_mode((100, 100)) # 入力検知用の小さな窓
    pygame.display.set_caption("Input")

    # TCP接続
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        print(f"[*] 接続試行中... {RPI_IP}:{CONTROL_PORT}")
        tcp_sock.connect((RPI_IP, CONTROL_PORT))
        print("[*] 接続成功！ WASDキーで操作してください")
    except:
        print("[!] ラズパイへの接続に失敗しました。ラズパイ側を先に起動してください。")
        return

    running = True
    while running:
        command = "STOP"
        
        # イベント取得
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # キー入力判定
        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]:
            command = "FORWARD"
        elif keys[pygame.K_s]:
            command = "BACK"
        elif keys[pygame.K_a]:
            command = "LEFT"
        elif keys[pygame.K_d]:
            command = "RIGHT"
        
        # データ送信 (改行コードを区切り文字とする)
        msg = command + "\n"
        try:
            tcp_sock.sendall(msg.encode('utf-8'))
            # 少しWaitを入れないと送りすぎる（調整可）
            time.sleep(0.05) 
        except:
            print("送信エラー")
            break

    tcp_sock.close()
    pygame.quit()

if __name__ == "__main__":
    # 映像受信は別スレッドで動かす
    video_thread = threading.Thread(target=receive_video)
    video_thread.daemon = True
    video_thread.start()

    # メインスレッドで操作送信を行う
    send_control()