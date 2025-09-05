from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Type


@dataclass
class GameInfo:
    # ゲーム情報（名前 / クラス / 由来）
    name: str
    cls: type
    source: str  # "local" または パッケージ配布物の名前


def _maybe_get_game_class(obj: Any) -> Optional[type]:
    # 受け入れる形式: クラス本体 / GAME_CLASS 変数 / クラスを返すファクトリ
    if isinstance(obj, type):
        return obj
    if hasattr(obj, "GAME_CLASS") and isinstance(obj.GAME_CLASS, type):
        return obj.GAME_CLASS
    if callable(obj):
        try:
            v = obj()
            if isinstance(v, type):
                return v
        except Exception:
            return None
    return None


def discover_local_games(base_pkg: str = "mediapipe_pyxel_demo.games") -> Dict[str, GameInfo]:
    # パッケージ内のローカルゲームを探索
    found: Dict[str, GameInfo] = {}
    try:
        pkg = importlib.import_module(base_pkg)
    except ImportError:
        return found

    for m in pkgutil.iter_modules(pkg.__path__):
        if not m.ispkg:
            continue
        mod_name = f"{base_pkg}.{m.name}.game"
        try:
            mod = importlib.import_module(mod_name)
        except Exception:
            continue
        cls = _maybe_get_game_class(mod)
        if cls:
            found[m.name] = GameInfo(name=m.name, cls=cls, source="local")
    return found


def discover_entrypoint_games(group: str = "mediapipe_pyxel_demo.games") -> Dict[str, GameInfo]:
    # エントリポイント経由で登録された外部パッケージのゲームを探索
    from importlib import metadata

    found: Dict[str, GameInfo] = {}
    try:
        # Python 3.10+ のエントリポイント API
        entry_points = metadata.entry_points
        try:
            eps = entry_points(group=group)  # type: ignore[arg-type]
        except TypeError:
            eps = entry_points().get(group, [])  # type: ignore[index]
    except Exception:
        return found

    for ep in eps:
        try:
            obj = ep.load()
            cls = _maybe_get_game_class(obj)
            if cls:
                found[ep.name] = GameInfo(name=ep.name, cls=cls, source=getattr(ep, "dist", ep.module))
        except Exception:
            continue
    return found


def discover_games() -> Dict[str, GameInfo]:
    # ローカル + エントリポイントの両方からゲームを集約
    games = {}
    games.update(discover_local_games())
    games.update(discover_entrypoint_games())
    return games

