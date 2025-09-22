from __future__ import annotations

import argparse
from typing import Any, Dict

from . import __version__
from .app import App
from .registry import discover_games


def _build_provider(name: str):
    if name == "keyboard":
        from .input_providers.keyboard import KeyboardProvider

        return KeyboardProvider()
    if name == "mediapipe_face":
        from .input_providers.mediapipe_face import FaceProvider

        return FaceProvider()
    raise SystemExit(f"Unknown provider: {name}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="MediaPipe × Pyxel Demo")
    # デフォルトでメニュー（ゲーム選択画面）を起動する
    parser.add_argument("--game", default="menu", help="Game name (discovered)")
    parser.add_argument("--provider", default="mediapipe_face", choices=["keyboard", "mediapipe_face"], help="Input provider")
    parser.add_argument("--scale", type=int, default=3, help="Pyxel window scale")
    parser.add_argument("--list", action="store_true", help="List discovered games and exit")
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return

    games = discover_games()
    if args.list:
        if not games:
            print("No games found.")
            return
        for name, info in games.items():
            print(f"- {name} ({info.source})")
        return

    if args.game not in games:
        # 存在しないゲーム名が指定された場合は、利用可能な一覧を表示
        available = ", ".join(sorted(games.keys())) or "<none>"
        raise SystemExit(f"Game '{args.game}' not found. Available: {available}")

    game_cls = games[args.game].cls
    game = game_cls()

    provider = _build_provider(args.provider)
    app = App(game=game, providers=[provider], scale=args.scale)
    app.run()


if __name__ == "__main__":
    main()
