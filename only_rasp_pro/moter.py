import RPi.GPIO as GPIO
import time

# --- 設定エリア ---
PIN_PWM = 16   # PWM制御用ピン (MDD20A PWM入力)
PIN_DIR = 20   # 方向制御用ピン (MDD20A DIR入力)
PWM_FREQ = 20000  # PWM周波数 20kHz
DUTY_CYCLE = 50.0 # 動作時の出力 (50%)
# ------------------

def main():
    # GPIOセットアップ
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PIN_PWM, GPIO.OUT)
    GPIO.setup(PIN_DIR, GPIO.OUT)

    # PWMインスタンス作成
    pwm_motor = GPIO.PWM(PIN_PWM, PWM_FREQ)
    
    # 初期状態: PWM 0% (停止), DIR 0 (Low)
    pwm_motor.start(0)
    GPIO.output(PIN_DIR, GPIO.LOW)
    current_dir = 0

    print("-------------------------------------------------")
    print("コマンドを入力してください:")
    print("  dir1   : 方向を正転(High)に設定")
    print("  dir0   : 方向を逆転(Low)に設定")
    print("  pwmX   : X秒間、出力50%で動作 (例: pwm5 -> 5秒動作)")
    print("  q      : 終了")
    print("-------------------------------------------------")

    try:
        while True:
            # 入力待ち
            raw_input = input(">> ").strip().lower()

            # 終了コマンド
            if raw_input == 'q' or raw_input == 'exit':
                break

            # 方向制御 (dir1, dir0)
            elif raw_input.startswith("dir"):
                try:
                    val = int(raw_input.replace("dir", ""))
                    if val == 1:
                        GPIO.output(PIN_DIR, GPIO.HIGH)
                        current_dir = 1
                        print("OK: Direction -> HIGH (1)")
                    elif val == 0:
                        GPIO.output(PIN_DIR, GPIO.LOW)
                        current_dir = 0
                        print("OK: Direction -> LOW (0)")
                    else:
                        print("Error: dirは 0 か 1 で指定してください")
                except ValueError:
                    print("Error: 数値を読み取れませんでした")

            # 動作時間制御 (pwmX)
            elif raw_input.startswith("pwm"):
                try:
                    # 'pwm'を除去して数値(秒数)を取得
                    sec_str = raw_input.replace("pwm", "")
                    duration = float(sec_str)

                    if duration > 0:
                        print(f"Run: {duration}秒間動作します (Duty {DUTY_CYCLE}%) ...")
                        
                        # 指定時間だけ回す
                        pwm_motor.ChangeDutyCycle(DUTY_CYCLE)
                        time.sleep(duration)
                        
                        # 停止
                        pwm_motor.ChangeDutyCycle(0)
                        print("Done: 停止しました")
                    else:
                        print("Error: 0より大きい秒数を指定してください")

                except ValueError:
                    print("Error: 秒数を読み取れませんでした (例: pwm3.5)")

            else:
                print("Unknown command. (dir0, dir1, pwmX, q)")

    except KeyboardInterrupt:
        print("\nForce stopped by user.")

    finally:
        pwm_motor.stop()
        GPIO.cleanup()
        print("GPIO Cleaned up. Exiting.")

if __name__ == "__main__":
    main()