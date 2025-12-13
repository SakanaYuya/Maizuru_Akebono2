# ファイル名: neopixel_gpio26.py
import time
import board
import neopixel

# --- 設定値 ---
# GPIO 26 (Pin 37) を指定
PIN_PIXEL = board.D26

# LEDの個数
NUM_PIXELS = 1

# 発光色 (R, G, B) - ここではシアン
TARGET_COLOR = (0, 255, 255)

# 輝度 (0.0 - 1.0)
BRIGHTNESS = 0.2

def main():
    # pixel_orderはLEDの種類によって RGB または GRB の場合があります
    pixels = neopixel.NeoPixel(
        PIN_PIXEL, 
        NUM_PIXELS, 
        brightness=BRIGHTNESS, 
        auto_write=False,
        pixel_order=neopixel.GRB
    )

    try:
        print(f"GPIO 26にてLED点灯開始: RGB={TARGET_COLOR}")
        
        pixels.fill(TARGET_COLOR)
        pixels.show()

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n停止します。")
        
    finally:
        pixels.fill((0, 0, 0))
        pixels.show()
        pixels.deinit()
        print("消灯・クリーンアップ完了。")

if __name__ == "__main__":
    main()