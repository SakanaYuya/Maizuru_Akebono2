#コントローラー入力のコード

import pygame
# コントローラーのマッピング情報 (README.mdより)
# Axis: スティックやトリガー
AXIS_MAPPING = {
    0: {"name": "左スティック X", "min": "左", "center": "中央", "max": "右"},
    1: {"name": "左スティック Y", "min": "上", "center": "中央", "max": "下"},
    2: {"name": "右スティック X", "min": "左", "center": "中央", "max": "右"},
    3: {"name": "右スティック Y", "min": "上", "center": "中央", "max": "下"},
    4: {"name": "LT (トリガー)", "min": "最手前", "center": "中央", "max": "最奥"}, # 値の解釈は環境による
    5: {"name": "RT (トリガー)", "min": "最手前", "center": "中央", "max": "最奥"}, # 値の解釈は環境による
}

# Buttons: 各ボタン
BUTTON_MAPPING = {
    0: "Aボタン",
    1: "Bボタン",
    2: "Xボタン",
    3: "Yボタン",
    4: "LB (背面ボタン)",
    5: "RB (背面ボタン)",
    6: "BACK (特殊ボタン)",
    7: "START (特殊ボタン)",
    8: "左スティック押し込み",
    9: "右スティック押し込み",
    10: "センターボタン (特殊ボタン)",
}

# Hats: 十字キー
HAT_MAPPING = {
    (0, 0): "中央",
    (-1, 0): "左",
    (0, 1): "上",
    (1, 0): "右",
    (0, -1): "下",
    (-1, 1): "左上",
    (1, 1): "右上",
    (-1, -1): "左下",
    (1, -1): "右下",
}

def get_axis_direction(axis_id, value):
    if axis_id not in AXIS_MAPPING:
        return f"不明な軸 {axis_id}"

    axis_info = AXIS_MAPPING[axis_id]
    if value < -0.75: # 適当な閾値
        return axis_info.get("min", "最小方向")
    elif value > 0.75: # 適当な閾値
        return axis_info.get("max", "最大方向")
    elif -0.2 < value < 0.2: # 適当な閾値
        return axis_info.get("center", "中央")
    else:
        return "中間"


def print_controller_input():
    pygame.init()
    joystick_count = pygame.joystick.get_count()

    if joystick_count == 0:
        print("No joystick detected.")
        return

    joystick = pygame.joystick.Joystick(0)
    joystick.init()

    print(f"Detected joystick: {joystick.get_name()}")
    print(f"Number of axes: {joystick.get_numaxes()}")
    print(f"Number of buttons: {joystick.get_numbuttons()}")
    print(f"Number of hats: {joystick.get_numhats()}")

    try:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.JOYAXISMOTION:
                    axis_name = AXIS_MAPPING.get(event.axis, {}).get("name", f"Axis {event.axis}")
                    direction = get_axis_direction(event.axis, event.value)
                    print(f"{axis_name}: {event.value:.4f} ({direction})")
                elif event.type == pygame.JOYBUTTONDOWN:
                    button_name = BUTTON_MAPPING.get(event.button, f"Button {event.button}")
                    print(f"{button_name} 押し込み.")
                elif event.type == pygame.JOYBUTTONUP:
                    button_name = BUTTON_MAPPING.get(event.button, f"Button {event.button}")
                    print(f"{button_name} 離す.")
                elif event.type == pygame.JOYHATMOTION:
                    hat_direction = HAT_MAPPING.get(event.value, "不明な方向")
                    print(f"十字スティック Hat {event.hat}: {event.value} ({hat_direction})")
            pygame.time.wait(10) # Small delay to prevent busy-waiting
    except KeyboardInterrupt:
        print("Exiting controller input reader.")
    finally:
        pygame.quit()

if __name__ == "__main__":
    print_controller_input()
