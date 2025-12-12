import RPi.GPIO as GPIO
import time

# --- 設定値 ---
PIN_SW1 = 5  # GPIO 5
PIN_SW2 = 6  # GPIO 6
LOG_INTERVAL = 0.5  # ログを出力する間隔(秒)

def setup_gpio():
    """GPIOの初期設定"""
    GPIO.setmode(GPIO.BCM)
    # 内部プルアップ有効化
    # スイッチ未接続時はHIGH、GNDに落ちるとLOWになります
    GPIO.setup(PIN_SW1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(PIN_SW2, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def main():
    try:
        setup_gpio()
        print(f"--- 監視開始 (間隔: {LOG_INTERVAL}秒) ---")
        print("GPIO 5 | GPIO 6")
        print("-------+-------")

        while True:
            # 現在の電圧レベル(0または1)を読み取る
            val_sw1 = GPIO.input(PIN_SW1)
            val_sw2 = GPIO.input(PIN_SW2)

            # ログを見やすく整形 (1=HIGH, 0=LOW)
            # 内部プルアップなので、1がOFF(開放)、0がON(押下)です
            status1 = "HIGH" if val_sw1 == 1 else "LOW "
            status2 = "HIGH" if val_sw2 == 1 else "LOW "

            # 画面に出力
            print(f" {status1}  |  {status2}")

            # 指定時間待機 (この数値を小さくすると更新が速くなります)
            time.sleep(LOG_INTERVAL)

    except KeyboardInterrupt:
        print("\nプログラムを停止します。")
        
    finally:
        GPIO.cleanup()
        print("GPIO設定をクリーンアップしました。")

if __name__ == "__main__":
    main()