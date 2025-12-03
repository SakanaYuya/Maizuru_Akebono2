import os
os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"

import cv2

def capture_and_display():
    # デフォルトのカメラを開く
    cap = cv2.VideoCapture(1)
    # cv2.VideoCapture(0)では内蔵カメラを使用します。外付けカメラを使用する場合は1に変更してください。
    
    # 解像度を1280x720に設定
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    if not cap.isOpened():
        print("エラー: カメラを開けませんでした。")
        return

    # ウィンドウ名を設定し、リサイズ可能にする_[Topic]ウィンドウ名を調整する際はここを入力
    window_name = 'Camera1 exit:"q"'
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    # ウィンドウの初期サイズを90度回転後の解像度に合わせる
    cv2.resizeWindow(window_name, 720, 1280)

    print("カメラ映像が表示されます。終了するには 'q' キーを押してください。")

    while True:
        # カメラからフレームを読み込む
        ret, frame = cap.read()

        if not ret:
            print("エラー: フレームを読み込めませんでした。")
            break

        # フレームを回転して表示_[Tpic]もし仮にカメラ角度を変えたい場合はここを調整してください

        # 時計回りに90度回転: rotated_frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        # 反時計回りに90度回転: rotated_frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        # 180度回転: rotated_frame = cv2.rotate(frame, cv2.ROTATE_180)
        rotated_frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        cv2.imshow(window_name, rotated_frame)

        # 'q'キーが押されたらループを抜ける
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # カメラを解放し、すべてのウィンドウを破棄する
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    capture_and_display()
