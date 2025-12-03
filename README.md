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

> 坂田 雄哉　**[PG (Repository Host)]**

## Commit Rules
コミットメッセージの初めには必ず prefix をつける様にしましょう．
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
* VNC接続
* [コントローラー操作](#コントローラー操作-1)
* [カメラ動作](#カメラ動作-1)
* etc...

## 環境セットアップ
Windows環境で本リポジトリのプログラムを動作させるためのセットアップ手順を説明します。

### 1. リポジトリのクローン
まず、以下のコマンドを実行し、GitHubリポジトリをローカルにクローンします。
```bash
git clone https://github.com/Yuura/Maizuru_Akebono2.git
cd Maizuru_Akebono2
```

### 2. Python環境の構築とライブラリのインストール
#### Pythonの準備
Python 3.10以上がインストールされていることを確認してください。

#### 仮想環境の構築
次に、プロジェクト用の仮想環境を作成し、有効化します。これにより、プロジェクトごとのライブラリ管理が容易になります。
```bash
python -m venv venv
.\venv\Scripts\activate
```

#### ライブラリのインストール
このプロジェクトでは、主に以下のライブラリを使用します。
- **OpenCV (`opencv-python`):** カメラ映像の取得や画像処理に使用します。
- **Pygame (`pygame`):** ゲームパッドやコントローラーからの入力を受け取るために使用します。

以下のコマンドで、必要なライブラリをまとめてインストールします。
```bash
pip install opencv-python pygame
```
もしくは、リポジトリに含まれる`requirements.txt`ファイルを使ってインストールすることも可能です。
```bash
pip install -r requirements.txt
```

これで、Windows環境での基本的なセットアップは完了です。
## コントローラー操作

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

(末尾)ソースコードリンク
## コントローラー操作

(末尾)ソースコードリンク
## カメラ動作
(末尾)ソースコードリンク
