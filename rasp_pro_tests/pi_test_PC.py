#rasp2_pc_console_V3
#Bidirectional_Display
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
WINDOW_NAME = "Camera View (Press Q in Control Window to Quit)"

# ★ ロボットの状態 (FRONT or BACK)
ROBOT_MODE = "FRONT"

# --- UDP受信 (映像) ---
def receive_video():
    global is_running
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.settimeout(1.0)
    udp_sock.bind((MY_IP, VIDEO_PORT))
    print(f"[*] 映像待機中: UDP {VIDEO_PORT}")
    
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    
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
                
                cv2.imshow(WINDOW_NAME, frame)
            cv2.waitKey(1)
        except socket.timeout:
            continue
        except Exception:
            pass
    udp_sock.close()
    cv2.destroyAllWindows()

# --- ★ V3追加: ステータス受信スレッド ---
def receive_status_thread(sock):
    global ROBOT_MODE, is_running
    buffer = ""
    print("[*] ステータス受信スレッド開始")
    
    while is_running:
        try:
            # ラズパイからのデータを受信
            data = sock.recv(1024)
            if not data: break
            
            buffer += data.decode('utf-8')
            
            # 改行区切りでJSONをパース
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                try:
                    js = json.loads(line)
                    if "mode" in js:
                        ROBOT_MODE = js["mode"] # "FRONT" or "BACK"
                        print(f"[Recv] Mode Updated: {ROBOT_MODE}")
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            # タイムアウトや切断など
            if is_running: print(f"[!] Recv Error: {e}")
            break

# --- メイン制御ロジック ---
def main():
    global is_running, last_sent_json

    pygame.init()
    screen = pygame.display.set_mode((400, 250), pygame.RESIZABLE) # 少し縦長に
    pygame.display.set_caption("Control Panel")
    
    # フォント設定 (Windows 11想定: メイリオ)
    try:
        font_small = pygame.font.SysFont("meiryo", 20)
        font_big = pygame.font.SysFont("meiryo", 60, bold=True) # 巨大フォント
    except:
        font_small = pygame.font.SysFont(None, 24)
        font_big = pygame.font.SysFont(None, 100)

    # TCP接続
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        print(f"[*] 接続試行中... {RPI_IP}:{CONTROL_PORT}")
        tcp_sock.connect((RPI_IP, CONTROL_PORT))
        print(f"[*] 接続成功！")
    except Exception as e:
        print(f"[!] 接続失敗: {e}")
        return

    # ★ V3追加: 受信スレッド起動
    recv_thread = threading.Thread(target=receive_status_thread, args=(tcp_sock,))
    recv_thread.daemon = True
    recv_thread.start()

    clock = pygame.time.Clock()

    while is_running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                is_running = False
            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)

        screen.fill((0, 0, 0))
        
        # --- 描画処理 ---
        
        # 1. 巨大な状態表示
        if ROBOT_MODE == "FRONT":
            # 緑色で「前」
            text_mode = font_big.render("前", True, (0, 255, 0))
        else:
            # 赤色で「後」
            text_mode = font_big.render("後ろ", True, (255, 50, 50))
            
        # 中央に配置
        rect_mode = text_mode.get_rect(center=(screen.get_width()//2, 80))
        screen.blit(text_mode, rect_mode)

        # 2. 操作ガイド
        instructions = [
            "-------------北条専用機体-------------",
            "Move: 左[W/S], 右[O/L] ",
            "Cam: [3/4] (前/後ろ), [8/9] (上/下)",
            "Quit: [Q]"
        ]
        y_offset = 160
        for line in instructions:
            text = font_small.render(line, True, (200, 200, 200))
            screen.blit(text, (20, y_offset))
            y_offset += 25
            
        pygame.display.flip()

        # キー入力
        keys = pygame.key.get_pressed()
        if keys[pygame.K_q]:
            is_running = False
            break

        ls_y = 0.0
        if keys[pygame.K_w]: ls_y = -1.0
        elif keys[pygame.K_s]: ls_y = 1.0

        rs_y = 0.0
        if keys[pygame.K_o]: rs_y = -1.0
        elif keys[pygame.K_l]: rs_y = 1.0

        hat_y = 0
        if keys[pygame.K_3]: hat_y = 1
        elif keys[pygame.K_4]: hat_y = -1
        
        hat_x = 0
        if keys[pygame.K_9]: hat_x = 1 
        elif keys[pygame.K_8]: hat_x = -1 

        data = {
            "controller": {
                "LS_Y": ls_y, "RS_Y": rs_y,
                "HAT_X": hat_x, "HAT_Y": hat_y
            }
        }
        json_str = json.dumps(data)

        if json_str != last_sent_json:
            try:
                tcp_sock.sendall((json_str + "\n").encode('utf-8'))
                last_sent_json = json_str
            except Exception as e:
                print(f"[!] 送信エラー: {e}")
                is_running = False
                break

        clock.tick(30)

    # 終了
    stop_data = json.dumps({"controller": {"LS_Y": 0.0, "RS_Y": 0.0, "HAT_X": 0, "HAT_Y": 0}})
    try:
        tcp_sock.sendall((stop_data + "\n").encode('utf-8'))
    except: pass
    tcp_sock.close()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    t = threading.Thread(target=receive_video)
    t.daemon = True
    t.start()
    try:
        main()
    except KeyboardInterrupt:
        pass