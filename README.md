# MediaPipe × Pyxel デモ

MediaPipeによる画像認識を用いてPyxelで動作するゲームを操作します。

### SDL2ランタイムのインストール（Pyxel実行に必須）
PyxelはSDL2を使用します。環境によってはSDL2のランタイムを別途インストールする必要があります。

- Ubuntu/WSL:
  - `sudo apt update`
  - `sudo apt install -y libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-mixer-2.0-0`
- macOS (Homebrew): `brew install sdl2 sdl2_image sdl2_mixer`
- Windows (ネイティブ): 通常は追加インストール不要です。

## セットアップ（uv 利用）

1) 依存パッケージを同期:

```
uv sync
```

2) 実行

```
uv run -m mediapipe_pyxel_demo
```
デフォルトではゲームの選択画面が開きます。

## CLI ヘルプ

```
uv run -m mediapipe_pyxel_demo --help
```

- `--game <name>`: ゲーム名を指定します。
- `--provider <name>`: 入力プロバイダ：

## ゲームの追加方法
`src/mediapipe_pyxel_demo/games/<your_game>/game.py` を作成し、
`GAME_CLASS`（`on_event(event)`, `update()`, `draw()` を実装するクラス）を公開してください。

または、別パッケージとして公開し、エントリポイント `mediapipe_pyxel_demo.games` に登録することもできます。
