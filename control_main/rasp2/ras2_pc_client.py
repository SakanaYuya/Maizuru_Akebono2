#rasp2_pc_console
import cv2
import socket
import numpy as np
import threading
import pygame
import time
import json
import sys

# --- 設定 ---
MY_IP = "0.0.0.0" 
VIDEO_PORT = 5005
RPI_IP = "192.168.50.20"
CONTROL_PORT = 5006
VIDEO_ROTATION = 270 

# グローバル変数
is_running = True
last_sent_json = ""

# --- UDP受信 (映像) ---
def receive_video():
    global is_running
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.settimeout(1.0)
    udp_sock.bind((MY_IP, VIDEO_PORT))
    print(f"[*] 映像待機中: UDP {VIDEO_PORT}")

    while is_running:
        try:
            data, addr = udp_sock.recvfrom(65535)
            nparr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is not None:
                if VIDEO_ROTATION == 90:
                    frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
                elif VIDEO_ROTATION == 180:
                    frame = cv2.rotate(frame, cv2.ROTATE_180)
                elif VIDEO_ROTATION == 270:
                    frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
                
                cv2.imshow("Camera (Press Q in Input Window to Quit)", frame)
                
            cv2.waitKey(1)
        except socket.timeout:
            continue
        except Exception:
            pass

    udp_sock.close()
    cv2.destroyAllWindows()

# --- メイン制御ロジック ---
def main():
    global is_running, last_sent_json

    # 1. Pygame初期化 (キー入力取得のため必須)
    pygame.init()
    # フォーカス用の小さなウィンドウを作成
    screen = pygame.display.set_mode((400, 100))
    pygame.display.set_caption("Click Here to Control")
    font = pygame.font.SysFont(None, 24)

    # 2. TCP接続
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        print(f"[*] 接続試行中... {RPI_IP}:{CONTROL_PORT}")
        tcp_sock.connect((RPI_IP, CONTROL_PORT))
        print(f"[*] 接続成功！")
        print("------------------------------------------------")
        print("【重要】操作するには「Click Here to Control」という")
        print("       小さな黒いウィンドウをクリックしてください。")
        print("------------------------------------------------")
        print(" [W/S]: 左足, [O/L]: 右足")
        print(" [5/6]: 上下, [7/8]: 左右")
        print(" [Q]  : 終了")
        print("------------------------------------------------")
    except Exception as e:
        print(f"[!] 接続失敗: {e}")
        return

    # 3. 操作ループ
    clock = pygame.time.Clock()

    while is_running:
        # Pygameイベント処理
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                is_running = False

        # 画面描画 (ユーザーへの指示)
        screen.fill((0, 0, 0))
        text = font.render("Focus HERE & Press Keys", True, (255, 255, 255))
        screen.blit(text, (20, 40))
        pygame.display.flip()

        # キー入力取得
        keys = pygame.key.get_pressed()

        # 終了チェック
        if keys[pygame.K_q]:
            print("\n[!] 終了操作 (Q)")
            is_running = False
            break

        # --- 入力判定 ---
        # 足回り
        ls_y = 0.0
        if keys[pygame.K_w]: ls_y = -1.0
        elif keys[pygame.K_s]: ls_y = 1.0

        rs_y = 0.0
        if keys[pygame.K_o]: rs_y = -1.0
        elif keys[pygame.K_l]: rs_y = 1.0

        # カメラ
        hat_y = 0
        if keys[pygame.K_5]: hat_y = 1
        elif keys[pygame.K_6]: hat_y = -1
        
        hat_x = 0
        if keys[pygame.K_8]: hat_x = 1
        elif keys[pygame.K_7]: hat_x = -1

        # データ作成
        data = {
            "controller": {
                "LS_Y": ls_y,
                "RS_Y": rs_y,
                "HAT_X": hat_x,
                "HAT_Y": hat_y
            }
        }
        json_str = json.dumps(data)

        # 前回と違う場合のみ送信＆ログ表示
        if json_str != last_sent_json:
            try:
                tcp_sock.sendall((json_str + "\n").encode('utf-8'))
                last_received_json = json_str
                
                # ログ出力作成
                log_parts = []
                if ls_y < 0: log_parts.append("左:前進")
                elif ls_y > 0: log_parts.append("左:後退")
                
                if rs_y < 0: log_parts.append("右:前進")
                elif rs_y > 0: log_parts.append("右:後退")

                if hat_y == 1: log_parts.append("Cam:上")
                elif hat_y == -1: log_parts.append("Cam:下")
                
                if hat_x == -1: log_parts.append("Cam:左")
                elif hat_x == 1: log_parts.append("Cam:右")
                
                if not log_parts:
                    print("[待機] 入力なし (停止信号送信)")
                else:
                    print(f"[送信] {' '.join(log_parts)}")
                
                last_sent_json = json_str

            except Exception as e:
                print(f"[!] 送信エラー: {e}")
                is_running = False
                break

        clock.tick(30) # 30FPSでループ

    # 終了処理
    print("[*] 終了処理中...")
    stop_data = json.dumps({"controller": {"LS_Y": 0.0, "RS_Y": 0.0, "HAT_X": 0, "HAT_Y": 0}})
    try:
        tcp_sock.sendall((stop_data + "\n").encode('utf-8'))
    except: pass
    tcp_sock.close()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    # 映像スレッド開始
    t = threading.Thread(target=receive_video)
    t.daemon = True
    t.start()

    # メインループ
    try:
        main()
    except KeyboardInterrupt:
        pass