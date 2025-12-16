# Maizuru_Akebono2
廃炉ロボコン2025における舞鶴高専チーム**あけぼの**リポジトリ

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![License](https://img.shields.io/github/license/Yuura/Maizuru_Akebono2)
![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-OS-C51A4A?logo=raspberrypi&logoColor=white)

## Team Members
> 名倉 時春　**[Reader]**

> 山城 喬楽　**[CAD]**

> 内橋 慧悟　**[ECD]**

> 北条 博輝　**[CAD]**

> 宮川 颯季　**[Fitter]**

> 和泉 穂花　**[Fitter]**

> 岩本 千尋　**[Fab]**

> 高岡 優　**[PG (Super Supporter)]**

> 坂田 雄哉　**[PG (Repository Host)]**

## Commit Rules
コミットメッセージの初めには必ず prefix をつける様にしましょう.  
[参考：僕が考える最強のコミットメッセージの書き方(Qiita)](https://qiita.com/konatsu_p/items/dfe199ebe3a7d2010b3e)

| Prefix   | 意味                                                    |
| -------- | ------------------------------------------------------- |
| add      | ちょっとしたファイルやコードの追加(画像など)            |
| change   | ちょっとしたファイルやコードの変更(画像差し替え)        |
| feat     | ユーザが利用する機能の追加(add/change を内包しても良い) |
| style    | 機能部分を変更しない、コードの見た目の変化(CSS)         |
| refactor | リファクタリング                                        |
| fix      | バグ修正                                                |
| remove   | ファイルなどの削除                                      |
| test     | テスト関連                                              |
| move     | フォルダの移動                                         |
| chore    | ビルド、補助ツール、ライブラリ関連                      |

# How to Use
winodws環境版とRaspberry Pi版それぞれの環境で動作するプログラムを以下に記載しています。  
動作の際は、自身が実行する環境に合わせたプログラムで確認を行ってください。

## Windows 環境
* [環境セットアップ](#環境セットアップ)
* [コントローラー操作](#コントローラー操作)
* [カメラ動作確認](#カメラ動作確認)
* etc...


## Raspberry Pi 4B 環境
* [環境セットアップ](#環境セットアップ-1)
* [コントローラー操作](#コントローラー操作-1)
* [カメラ動作](#カメラ動作-1)
* etc...

## To team Menbers ロボットの動かし方
* [ラズパイの起動と疎通確認](#ラズパイの起動と疎通確認)
* [Raspberry Pi 側操作](#RaspberryPi側操作)
* [Windows 側操作](#Windows側操作)
* [実際実行手順実](#実際実行手順実)


## 環境セットアップ
Windows環境で本リポジトリのプログラムを動作させるためのセットアップ手順を説明します。

### 必要な環境
- "Git"&"Github"において、"Git clone"コマンドが実行可能な環境
- プログラミングエディタ (推奨 VScode)
- SSH接続が可能なPc (推奨 Windows 11)
- ["Real VNC Viewer"](#RealVNC)
-  LANポート対応Pc (USB to LANでも可能)
### 1. リポジトリのクローン
まず、以下のコマンドを実行し、GitHubリポジトリをローカルにクローンします。
```bash
git clone https://github.com/SakanaYuya/Maizuru_Akebono2.git
cd Maizuru_Akebono2
```

### 2. Python環境の構築とライブラリのインストール
#### Pythonの準備
Python 3.10以上がインストールされていることを確認してください。  
**[Caution]**PythonはVersion 3.12.6が最も安定して動作します。
[Python3.12.6](https://www.python.org/downloads/release/python-3126/)

#### 仮想環境の構築
Windowsでは、システムにインストールされている他のPythonライブラリとの競合を避けるため、プロジェクトごとに仮想環境を作成することが強く推奨されます。

以下のコマンドで、プロジェクト用の仮想環境 (`venv`) を作成し、有効化します。
```bash
python -m venv venv
.\venv\Scripts\activate
```
プロンプトの先頭に `(venv)` と表示されれば、仮想環境が有効になっています。

#### ライブラリのインストール
このプロジェクトでは、主に以下のライブラリを使用します。
- **OpenCV (`opencv-python`):** カメラ映像の取得や画像処理に使用します。
- **Pygame (`pygame`):** ゲームパッドやコントローラーからの入力を受け取るために使用します。

以下のコマンドで、必要なライブラリをまとめてインストールします。
```bash
pip install opencv-python pygame
```　
もしくは、リポジトリに含まれる`requirements.txt`ファイルを使ってインストールすることも可能です。
**[推奨]**
```bash
pip install -r requirements.txt
```
#### Real VNC 
ラズパイにVNC接続をするためのアプリケーション
以下サイトより、自身の環境に合わせてダウンロード
[Real VNC Viewer](https://www.realvnc.com/en/connect/download/viewer/?lai_vid=99GgAjyL6hbBA&lai_sr=15-19&lai_sl=l)  
初回実行時「log in/sign in」が聞かれるが。「with out」で使用可能なため、そちらを選択してください。

参考サイト
[最新のRaspberry PI OS (bookworm) にVNC接続を行う方法]()


これで、Windows環境での基本的なセットアップは完了です。
## コントローラー操作
> **背面ボタン**
>>Button 4 pressed.       :LB/5 押す
>>Button 4 released.      :LB/5 離す
>>Axis 4: -1.0000         :LT/7 最奥?
>>Axis 4: -1.0000         :LT/7 最手前?
>>Button 5 pressed.       :RB/6 押す
>>Button 5 released.      :RT/8 離す
>>Axis 5: -1.0000         :RT/8 最奥?
>>Axis 5: 1.0000          :RT/8 最手前?
>**ABXY入力**
>>Button 2 pressed.       :Xボタン 押す
>>Button 2 released.      :Xボタン 離す
>>Button 3 pressed.       :Yボタン 押す
>>Button 3 released.      :Yボタン 離す
>>Button 1 pressed.       :Bボタン 押す
>>Button 1 released.      :Bボタン 離す
>>Button 0 pressed.       :Aボタン 押す
>>Button 0 released.      :Aボタン 離す
>**十字スティック**
>>Hat 0: (-1, 0)          :左ボタン 押す
>>Hat 0: (0, 0)           :左ボタン 離す
>>Hat 0: (0, 1)           :上ボタン 押す
>>Hat 0: (0, 0)           :上ボタン 離す
>>Hat 0: (1, 0)           :右ボタン 押す
>>Hat 0: (0, 0)           :右ボタン 離す
>>Hat 0: (0, -1)          :下ボタン 押す
>>Hat 0: (0, 0)           :下ボタン 離す
>**特殊ボタン**
>>Button 7 pressed.       :START 押す
>>Button 7 released.      :START 離す
>>Button 6 pressed.       :BACK 押す
>>Button 6 released.      :BACK 離す
>>Button 10 pressed.      :センター 押す
>>Button 10 released.     :センター 離す

>**左スティック**
>>Button 8 pressed.         :ステック 押す
>>Button 8 released.        :ステック 離す
>>* 左右 (X軸)              : Axis 0
>>* 中央                    : 0.0
>>* 左最大                  : -1.0
>>* 右最大                  : 1.0
>>* 上下 (Y軸)              : Axis 1
>> * 中央                   : 0.0
>> * 上最大                 : -1.0
>> * 下最大                 : 1.0
>**右スティック**
>>Button 9 pressed.         :ステック 押す
>>Button 9 pressed.         :ステック 離す
>>* 左右 (X軸)              : Axis 2
>> * 中央                   : 0.0
>> * 左最大                 : -1.0
>> * 右最大                 : 1.0
>>* 上下 (Y軸)              : Axis 3
>> * 中央                   : 0.0
>> * 上最大                 : -1.0
>> * 下最大                 : 1.0

(末尾)ソースコードリンク
## カメラ動作確認
PCに接続されたカメラの映像を表示します。

### 実行手順
1. ターミナルを開き、`windows/camera` ディレクトリに移動します。
   ```bash
   cd windows/camera
   ```
2. 以下のコマンドを実行して、カメラ映像を表示します。
   ```bash
   python camera.py
   ```
3. 'q'キーを押すと、プログラムが終了します。

### 詳細
- デフォルトでは、外付けカメラ（インデックス `1`）を使用し、映像を反時計回りに90度回転して表示します。
- 内蔵カメラの使用や回転角度の変更など、詳細な設定は以下のドキュメントを参照してください。

[詳細な設定はこちら](./windows/camera/camera.md)


# Raspberry Pi
## 環境セットアップ
Raspberry Pi環境で本リポジトリのプログラムを動作させるためのセットアップ手順です。開発環境の汚染を防ぐため、Windowsと同様に仮想環境の利用を推奨します。

### 1. リポジトリのクローン
```bash
git clone https://github.com/SakanaYuya/Maizuru_Akebono2.git
cd Maizuru_Akebono2
```

### 2. Python環境の構築とライブラリのインストール
#### Pythonの準備
Raspberry Pi OSにはPythonがプリインストールされています。バージョンが3.10以上であることを確認してください。
```bash
python3 --version
```


これで、Raspberry Pi環境での基本的なセットアップは完了です。
## コントローラー操作

(末尾)ソースコードリンク
## カメラ動作
(末尾)ソースコードリンク

raspdev2を作成

## カメラ動作

## ラズパイの起動と疎通確認

## [Raspberry Pi 側操作]

## [Windows 側操作]

## [実際実行手順実]
