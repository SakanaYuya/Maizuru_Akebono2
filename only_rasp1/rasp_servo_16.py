#ラズパイ側、servo_16制御用コード
import pigpio
import time
import math

class PCA9685:
    """pigpioを使用したPCA9685制御クラス"""
    
    # レジスタアドレス定義
    MODE1 = 0x00
    PRESCALE = 0xFE
    LED0_ON_L = 0x06

    def __init__(self, pi, address=0x40, freq=50):
        self.pi = pi
        self.address = address
        self.handle = self.pi.i2c_open(1, self.address)
        self.set_frequency(freq)

    def write_reg(self, reg, value):
        self.pi.i2c_write_byte_data(self.handle, reg, value)
    
    def set_frequency(self, freq):
        """PWM周波数を設定（修正版）"""
        prescale = int(round(25000000.0 / (4096.0 * freq)) - 1)
        
        # 1. スリープモードにしてプリスケーラー（周波数）を設定可能にする
        # 0x10 = Sleep, 0x20 = Auto-Increment (これが必要！)
        mode_sleep = 0x10 | 0x20 
        self.write_reg(self.MODE1, mode_sleep)
        
        # 2. プリスケーラー値を書き込み
        self.write_reg(self.PRESCALE, prescale)
        
        # 3. スリープ解除 (Restart有効 + Auto-Increment有効)
        # 0x80 = Restart, 0x20 = Auto-Increment, 0x01 = AllCall
        mode_wake = 0x80 | 0x20 | 0x01
        self.write_reg(self.MODE1, mode_wake)
        
        # 安定するまで少し待つ
        time.sleep(0.005)
        
        # 設定モードへ移行
        old_mode = self.pi.i2c_read_byte_data(self.handle, self.MODE1)
        new_mode = (old_mode & 0x7F) | 0x10 # Sleep mode
        self.write_reg(self.MODE1, new_mode)
        self.write_reg(self.PRESCALE, prescale)
        self.write_reg(self.MODE1, old_mode)
        time.sleep(0.005)
        self.write_reg(self.MODE1, old_mode | 0x80) # Auto increment

    def set_pwm(self, channel, on, off):
        """各チャンネルのPWMを設定"""
        base_reg = self.LED0_ON_L + 4 * channel
        self.pi.i2c_write_i2c_block_data(self.handle, base_reg, [
            on & 0xFF,
            on >> 8,
            off & 0xFF,
            off >> 8
        ])

    def close(self):
        self.pi.i2c_close(self.handle)

class Servo:
    """角度指定で制御するためのラッパークラス"""
    
    def __init__(self, pca, channel, min_pulse=500, max_pulse=2400, min_angle=0, max_angle=180):
        self.pca = pca
        self.channel = channel
        self.min_pulse = min_pulse # 0度のときのパルス幅(us)
        self.max_pulse = max_pulse # 180度のときのパルス幅(us)
        self.min_angle = min_angle
        self.max_angle = max_angle
        self.current_angle = 0

    def angle_to_pulse(self, angle):
        """角度をPCA9685用のカウント値(0-4095)に変換"""
        # 範囲制限
        if angle < self.min_angle: angle = self.min_angle
        if angle > self.max_angle: angle = self.max_angle
        
        pulse_us = self.min_pulse + (angle / 180.0) * (self.max_pulse - self.min_pulse)
        # 50Hz (20000us) における 4096段階のカウント値を計算
        # count = (pulse_us / 20000) * 4096
        count = int((pulse_us / 20000.0) * 4096)
        return count

    def set_angle(self, angle):
        """指定した角度へ即座に移動"""
        count = self.angle_to_pulse(angle)
        self.pca.set_pwm(self.channel, 0, count)
        self.current_angle = angle
        # print(f"Ch:{self.channel} Angle:{angle} Count:{count}")

    def move_smooth(self, target_angle, speed=0.01):
        """
        指定した角度へゆっくり移動
        speed: ステップごとの待機時間(秒)。大きいほど遅くなる。
        """
        start = self.current_angle
        step = 1 if target_angle > start else -1
        
        # 整数ステップでループ（必要に応じて細かく調整可）
        for a in range(int(start), int(target_angle) + step, step):
            self.set_angle(a)
            time.sleep(speed)

# --- メイン処理 ---
if __name__ == "__main__":
    pi = pigpio.pi()
    if not pi.connected:
        print("pigpioデーモンに接続できません。")
        exit()

    try:
        pca = PCA9685(pi)
        
        # --- 設定エリア ---
        
        # 1番のモーター (Channel 0)
        # 基準:90, 最小:60, 最大:90
        servo1 = Servo(pca, channel=0, min_angle=60, max_angle=90)

        # 2番のモーター (Channel 1)
        # 基準:90, 最小:0, 最大:180
        servo2 = Servo(pca, channel=1, min_angle=0, max_angle=180)

        # 3番のモーター (Channel 2)
        # 基準:90, 最小:50, 最大:130
        servo3 = Servo(pca, channel=2, min_angle=50, max_angle=130)

        servos = [servo1, servo2, servo3]

        # --- 動作開始 ---

        print("初期設定: 全て基準位置（90度）へセットします")
        # 最初に必ず90度にする
        servo1.set_angle(90)
        servo2.set_angle(90)
        servo3.set_angle(90)
        time.sleep(1) # 移動完了まで少し待つ

        
        # --- 動作テスト ---
        
        print("\n--- 範囲制限のテスト ---")
        
        # テスト1: 1番モーター (範囲 60~90)
        print("1番(Ch0): 0度を指令 -> 制限により60度で止まるはず")
        servo1.move_smooth(0) 
        time.sleep(0.5)
        
        print("1番(Ch0): 180度を指令 -> 制限により90度で止まるはず")
        servo1.move_smooth(180)
        time.sleep(0.5)
        
        # テスト2: 3番モーター (範囲 50~130)
        print("3番(Ch2): 最小(50)から最大(130)へ往復")
        servo3.move_smooth(50)
        time.sleep(0.5)
        servo3.move_smooth(130)
        time.sleep(0.5)
        
        # 最後に基準に戻る
        print("\n全て基準位置(90度)に戻して終了")
        for s in servos:
            s.move_smooth(90)
            
    except KeyboardInterrupt:
        print("\n停止")
        # 脱力
        pca.set_pwm(0, 0, 0)
        pca.set_pwm(1, 0, 0)
        pca.set_pwm(2, 0, 0)
    finally:
        if 'pca' in locals(): pca.close()
        pi.stop()