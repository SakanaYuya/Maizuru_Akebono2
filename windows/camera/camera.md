# Windows版カメラ利用ガイド

このドキュメントは、`windows/camera/camera.py` スクリプトの詳細な利用方法について説明します。

## 概要
このスクリプトは、PCに接続されたカメラの映像を取得し、ウィンドウに表示します。映像はデフォルトで反時計回りに90度回転して表示されます。

## 実行方法
1. ターミナルでこのディレクトリに移動します。
   ```bash
   cd windows/camera
   ```
2. 以下のコマンドを実行します。
   ```bash
   python camera.py
   ```
3. カメラ映像のウィンドウが表示されます。'q'キーを押すと終了します。

## 詳細設定
スクリプト内のコードを編集することで、動作をカスタマイズできます。

### カメラの選択
使用するカメラは `cv2.VideoCapture()` の引数で指定します。
- **内蔵カメラ:** `cv2.VideoCapture(0)`
- **外部カメラ:** `cv2.VideoCapture(1)` (PCに複数のカメラが接続されている場合、インデックスは2, 3...となることがあります)
```python
# camera.py L11
cap = cv2.VideoCapture(1)
```

### 映像の回転
映像の回転角度は `cv2.rotate()` 関数で変更できます。
- **反時計回りに90度回転 (デフォルト):** `cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)`
- **時計回りに90度回転:** `cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)`
- **180度回転:** `cv2.rotate(frame, cv2.ROTATE_180)`
```python
# camera.py L40
rotated_frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
```

### 解像度の設定
`cap.set()` でカメラの解像度を直接指定できます。
```python
# camera.py L14-15
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
```
### ウィンドウ名の変更
`cv2.namedWindow`で表示されるウィンドウの名前を変更できます。
```python
# camera.py L21
window_name = 'Camera1 exit:"q"'
```


## トラブルシューティング
### カメラ映像が正常に表示されない場合
Windows環境、特にMSMF (Media Foundation)バックエンドで問題が発生することがあります。スクリプトの冒頭にある以下の記述は、ハードウェア変換を無効にし、互換性を向上させるためのものです。
```python
import os
os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"
```
この設定でも問題が解決しない場合は、カメラドライバの更新や、別のカメラでの動作確認を試みてください。