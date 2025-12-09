# --- 操作受信 & サーボ制御処理 (修正版) ---
def receive_control(pi):
    # 1. サーボの初期化・宣言
    try:
        pca = PCA9685(pi)
        
        # --- サーボ定義エリア ---
        servo0 = Servo(pca, channel=0, min_angle=60, max_angle=120)
        servo1 = Servo(pca, channel=1, min_angle=0, max_angle=180)
        servo2 = Servo(pca, channel=2, min_angle=60, max_angle=130)
        servo3 = Servo(pca, channel=3, min_angle=0, max_angle=180)

        # 全て基準位置(90度)へ移動
        servo0.set_angle(90)
        servo1.set_angle(90)
        servo2.set_angle(90)
        servo3.set_angle(90)
        
        # インチング動作(十字キー)用に現在の角度を変数で持つ
        current_deg_0 = 90
        # ★★★ 修正箇所: ここに変数を追加しました ★★★
        current_deg_1 = 90 
        
        print("[*] PCA9685初期化完了: サーボ0,1,2,3 準備OK")
        
    except Exception as e:
        print(f"[!] PCA9685初期化エラー: {e}")
        return

    # 2. 通信待機
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

                        # -------------------------------------------------
                        # ★ 1. サーボ制御エリア
                        # -------------------------------------------------
                        
                        # [サーボ0] 十字キー上下
                        hat_y = ctl.get("HAT_Y", 0)
                        if hat_y != 0:
                            step = 5
                            if hat_y == 1: current_deg_0 += step   # 上
                            elif hat_y == -1: current_deg_0 -= step # 下
                            
                            if current_deg_0 > 120: current_deg_0 = 120
                            if current_deg_0 < 60: current_deg_0 = 60
                            
                            servo0.set_angle(current_deg_0)
                            print(f"ACT: サーボ0 -> {current_deg_0}度")

                        # [サーボ1] 十字キー左右
                        hat_x = ctl.get("HAT_X", 0)
                        if hat_x != 0:
                            step = 5 # 動きすぎる場合はここを小さくしてください
                            if hat_x == 1: current_deg_1 += step    # 右
                            elif hat_x == -1: current_deg_1 -= step # 左
                            
                            if current_deg_1 > 180: current_deg_1 = 180
                            if current_deg_1 < 0: current_deg_1 = 0
                            
                            servo1.set_angle(current_deg_1)
                            print(f"ACT: サーボ1(左右) -> {current_deg_1}度")

                        # -------------------------------------------------
                        # その他の入力ログ
                        # -------------------------------------------------
                        if ctl.get("BUTTON_A"): print("LOG: ボタンA")
                        # (他のログ処理は省略)

                except Exception as e:
                    # ここでエラー内容が表示されていたはずです
                    print(f"エラー: {e}")
                    break
        print("[!] 切断されました")