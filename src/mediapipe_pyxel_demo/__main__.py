from __future__ import annotations

import argparse
from typing import Any, Dict, List, Optional

from . import __version__
from .app import App
from .registry import discover_games


def _build_provider(spec: str, player_slot: Optional[int] = None, fallback_camera: Optional[int] = None):
    name, _, param = spec.partition(":")
    name = name.strip()
    arg = param.strip()

    if name == "keyboard":
        from .input_providers.keyboard import KeyboardProvider

        return KeyboardProvider()
    if name == "mediapipe_face":
        from .input_providers.mediapipe_face import FaceProvider

        camera_index: int
        if arg:
            try:
                camera_index = int(arg)
            except ValueError as exc:
                raise SystemExit(f"Invalid camera index '{arg}' for mediapipe_face provider") from exc
        elif fallback_camera is not None:
            camera_index = int(fallback_camera)
        else:
            camera_index = 0
        player_index = (player_slot + 1) if player_slot is not None else None
        return FaceProvider(camera_index=camera_index, player_index=player_index)
    raise SystemExit(f"Unknown provider: {name}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="MediaPipe × Pyxel Demo")
    # デフォルトでメニュー（ゲーム選択画面）を起動する
    parser.add_argument("--game", default="menu", help="Game name (discovered)")
    parser.add_argument(
        "--provider",
        action="append",
        metavar="SPEC",
        help="Input provider spec (e.g. mediapipe_face or mediapipe_face:1). Repeat to add players.",
    )
    parser.add_argument(
        "--camera-indices",
        nargs="+",
        type=int,
        metavar="INDEX",
        help="Override camera indices for multi-player games (example: --camera-indices 0 1)",
    )
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

    requested_camera_indices: Optional[tuple[int, ...]] = None
    if args.camera_indices:
        requested_camera_indices = tuple(int(idx) for idx in args.camera_indices)

    game = game_cls()

    camera_index_hint: Optional[tuple[int, ...]] = None
    setter = getattr(game, "set_camera_indices", None)
    if requested_camera_indices is not None:
        camera_index_hint = requested_camera_indices
        if callable(setter):
            try:
                setter(requested_camera_indices)
            except ValueError as exc:
                raise SystemExit(str(exc)) from exc
            if hasattr(game, "reset"):
                game.reset()
    else:
        attr_hint = getattr(game, "camera_indices", None)
        if isinstance(attr_hint, (list, tuple)):
            camera_index_hint = tuple(int(i) for i in attr_hint)

    provider_specs: List[str] = list(args.provider) if args.provider else []
    if not provider_specs:
        provider_specs = ["mediapipe_face"]
    if not any(spec.split(":")[0].strip().lower() == "keyboard" for spec in provider_specs):
        provider_specs.append("keyboard")

    player_count = getattr(game, "player_count", 1)
    if not isinstance(player_count, int) or player_count <= 0:
        player_count = 1

    hint_len = len(camera_index_hint) if camera_index_hint else 0
    target_count = max(1, player_count, len(provider_specs), hint_len)

    base_specs = list(provider_specs)
    while len(base_specs) < target_count:
        base_specs.append(base_specs[-1])

    effective_specs = base_specs[:target_count]

    providers = []
    multi_source = target_count > 1
    for slot, spec in enumerate(effective_specs):
        fallback_camera = None
        if camera_index_hint and slot < len(camera_index_hint):
            fallback_camera = int(camera_index_hint[slot])
        player_slot = slot if multi_source else None
        providers.append(_build_provider(spec, player_slot=player_slot, fallback_camera=fallback_camera))

    app = App(game=game, providers=providers, scale=args.scale)
    app.run()


if __name__ == "__main__":
    main()
