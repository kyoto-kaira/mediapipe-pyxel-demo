from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional
import time


class Action(Enum):
    # ゲーム内で扱う抽象アクション
    ACTION1 = auto()   # 主ボタン（ジャンプなど）
    ACTION2 = auto()   # サブボタン（任意機能）
    QUIT = auto()      # 終了要求


@dataclass
class InputEvent:
    # 入力イベント（抽象アクション＋任意の値）
    action: Action
    value: float = 1.0  # 連続量がある場合に使用（しきい値など）
    timestamp: float = field(default_factory=time.time)  # イベント発生時刻（秒）
    note: Optional[str] = None  # デバッグ用メモ

