#rasp1_5
import cv2
import socket
import threading
import time
import json

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
            # ★追加: 直前の受信データを記憶する変数 (JSONデータ全体を比較)
            last_received_data = None
            
            while True:
                try:
                    data = conn.recv(1024)
                    if not data:
                        break
                    
                    # 受信データをUTF-8でデコード
                    received_json_str = data.decode('utf-8').strip()
                    
                    # 空文字はスキップ
                    if not received_json_str:
                        continue
                    
                    try:
                        current_data = json.loads(received_json_str)
                    except json.JSONDecodeError:
                        print(f"JSONデコードエラー: {received_json_str}")
                        continue
                    
                    # 受信データが前回と異なる場合のみ処理
                    if current_data != last_received_data:
                        print(f"受信データ: {current_data}")
                        last_received_data = current_data
                        
                        controller_data = current_data.get("controller", {})
                        keyboard_data = current_data.get("keyboard", {})
                            
                        # --- ジョイスティック入力の処理 ---
                        # アナログスティック (例: 左スティックのY軸)
                        ls_y = controller_data.get("LS_Y", 0.0)
                        ls_x = controller_data.get("LS_X", 0.0)
                        if ls_y < -0.5:
                            print("ジョイスティック: 左スティック前進")
                        elif ls_y > 0.5:
                            print("ジョイスティック: 左スティック後退")
                        
                        if ls_x < -0.5:
                            print("ジョイスティック: 左スティック左")
                        elif ls_x > 0.5:
                            print("ジョイスティック: 左スティック右")

                        rs_y = controller_data.get("RS_Y", 0.0)
                        rs_x = controller_data.get("RS_X", 0.0)
                        if rs_y < -0.5:
                            print("ジョイスティック: 右スティック前進")
                        elif rs_y > 0.5:
                            print("ジョイスティック: 右スティック後退")
                        
                        if rs_x < -0.5:
                            print("ジョイスティック: 右スティック左")
                        elif rs_x > 0.5:
                            print("ジョイスティック: 右スティック右")

                        # スティック押下
                        if controller_data.get("LS_PRESS"):
                            print("ジョイスティック: 左スティック押下")
                        if controller_data.get("RS_PRESS"):
                            print("ジョイスティック: 右スティック押下")

                        # ボタン
                        if controller_data.get("BUTTON_A"):
                            print("ジョイスティック: ボタンA押下")
                        if controller_data.get("BUTTON_B"):
                            print("ジョイスティック: ボタンB押下")
                        if controller_data.get("BUTTON_X"):
                            print("ジョイスティック: ボタンX押下")
                        if controller_data.get("BUTTON_Y"):
                            print("ジョイスティック: ボタンY押下")
                        if controller_data.get("BUTTON_LB"):
                            print("ジョイスティック: ボタンLB押下")
                        if controller_data.get("BUTTON_RB"):
                            print("ジョイスティック: ボタンRB押下")
                        if controller_data.get("BUTTON_BACK"):
                            print("ジョイスティック: ボタンBACK押下")
                        if controller_data.get("BUTTON_START"):
                            print("ジョイスティック: ボタンSTART押下")

                        # トリガー
                        lt_val = controller_data.get("TRIGGER_LT", 0.0)
                        rt_val = controller_data.get("TRIGGER_RT", 0.0)
                        if lt_val > 0.5:
                            print(f"ジョイスティック: LT (値: {lt_val:.2f})")
                        if rt_val > 0.5:
                            print(f"ジョイスティック: RT (値: {rt_val:.2f})")

                        # ハット (十字キー)
                        hat_x = controller_data.get("HAT_X", 0)
                        hat_y = controller_data.get("HAT_Y", 0)
                        if hat_y == 1:
                            print("ジョイスティック: 十字キー上")
                        elif hat_y == -1:
                            print("ジョイスティック: 十字キー下")
                        if hat_x == -1:
                            print("ジョイスティック: 十字キー左")
                        elif hat_x == 1:
                            print("ジョイスティック: 十字キー右")
                        
                        # --- キーボード入力の処理 ---
                        if keyboard_data.get("W"):
                            print("キーボード: W (前進)")
                        if keyboard_data.get("S"):
                            print("キーボード: S (後退)")
                        if keyboard_data.get("A"):
                            print("キーボード: A (左)")
                        if keyboard_data.get("D"):
                            print("キーボード: D (右)")

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