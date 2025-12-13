#停止したI2C基盤を再起動させるコード
import time
import pigpio

# I2Cアドレス
PCA9685_ADDR = 0x40

# レジスタアドレス
MODE1 = 0x00
PRESCALE = 0xFE
LED0_ON_L = 0x06
LED0_ON_H = 0x07
LED0_OFF_L = 0x08
LED0_OFF_H = 0x09

def wake_up_and_move():
    pi = pigpio.pi()
    if not pi.connected:
        print("pigpioデーモンに接続できません。")
        return

    h = pi.i2c_open(1, PCA9685_ADDR)

    print("--- 1. ICのリセットと起床 ---")
    # MODE1レジスタを 0x00 に書き込み (Sleepビットを解除 = 起床)
    # これにより内部発振器が動き出します
    pi.i2c_write_byte_data(h, MODE1, 0x00)
    time.sleep(0.01) # 起床待ち

    # 再度設定 (Auto-Increment有効化など)
    pi.i2c_write_byte_data(h, MODE1, 0xA1) # 1010 0001 (AI=1, RESTART=1, ALLCALL=1)
    time.sleep(0.01)

    print("--- 2. 周波数設定 (50Hz) ---")
    # 念のため周波数を設定しなおす手順（スリープさせる必要がある）
    # 1. スリープさせる
    old_mode = pi.i2c_read_byte_data(h, MODE1)
    new_mode = (old_mode & 0x7F) | 0x10 # Sleep bit ON
    pi.i2c_write_byte_data(h, MODE1, new_mode)
    
    # 2. プリスケーラ書き込み (50Hz = 121 / 0x79)
    pi.i2c_write_byte_data(h, PRESCALE, 0x79)
    
    # 3. 起こす
    pi.i2c_write_byte_data(h, MODE1, old_mode)
    time.sleep(0.005)
    pi.i2c_write_byte_data(h, MODE1, old_mode | 0x80) # RESTART

    print("--- 3. サーボ駆動 (CH0) ---")
    # 角度90度 (1.5ms) の設定値を書き込む
    # ONタイミング = 0
    # OFFタイミング = 307 (約1.5ms幅)
    
    # CH0 ON_L
    pi.i2c_write_byte_data(h, LED0_ON_L, 0x00)
    # CH0 ON_H
    pi.i2c_write_byte_data(h, LED0_ON_H, 0x00)
    
    # CH0 OFF_L (307の下位バイト = 0x33)
    pi.i2c_write_byte_data(h, LED0_OFF_L, 0x33)
    # CH0 OFF_H (307の上位バイト = 0x01)
    pi.i2c_write_byte_data(h, LED0_OFF_H, 0x01)

    print("命令送信完了: CH0のサーボが90度で固まるはずです。")
    print("この状態でサーボを手で回そうとして、抵抗があれば成功です。")

    pi.i2c_close(h)
    pi.stop()

if __name__ == "__main__":
    wake_up_and_move()
