from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
import time

from ...events import Action, InputEvent


@dataclass
class Flash:
    # 直近の入力のフラッシュ表示管理
    active: bool = False
    t_on: float = 0.0
    duration: float = 0.25  # 秒

    def trigger(self) -> None:
        self.active = True
        self.t_on = time.time()

    def on(self) -> bool:
        if not self.active:
            return False
        if time.time() - self.t_on > self.duration:
            self.active = False
            return False
        return True


class TestGame:
    """
    入力テスト用ゲーム。

    - ACTION1: カウント + フラッシュ
    - ACTION2: カウント + フラッシュ
    - ACTION3: カウント + フラッシュ
    - QUIT: アプリ側で処理
    """

    width = 256
    height = 224

    def __init__(self) -> None:
        self.counts: Dict[Action, int] = {Action.ACTION1: 0, Action.ACTION2: 0, Action.ACTION3: 0}
        self.flash: Dict[Action, Flash] = {
            Action.ACTION1: Flash(),
            Action.ACTION2: Flash(),
            Action.ACTION3: Flash(),
        }
        self.last_event: str = "-"
        self.start_time = time.time()

    # --- 入力 ---
    def on_event(self, e: InputEvent) -> None:
        if e.action in (Action.ACTION1, Action.ACTION2, Action.ACTION3):
            self.counts[e.action] = self.counts.get(e.action, 0) + 1
            self.flash[e.action].trigger()
            self.last_event = f"{e.action.name}  val={e.value:.2f}"

    # --- 更新 ---
    def update(self) -> None:
        # 特にロジックは不要。フラッシュは時間で自動オフ。
        pass

    # --- 描画 ---
    def draw(self, px) -> None:
        # 背景
        px.cls(0)
        for y in range(0, self.height, 8):
            c = 1 if (y // 8) % 2 == 0 else 5
            px.line(0, y, self.width, y, c)

        # タイトル
        title = "INPUT TEST"
        tx = self.width // 2 - len(title) * 2
        for dx, dy in ((-1,0),(1,0),(0,-1),(0,1)):
            px.text(tx+dx, 8+dy, title, 0)
        px.text(tx, 8, title, 7)

        # 説明
        px.text(10, 24, "Press inputs to verify.", 6)
        px.text(10, 34, "ACTION1: Space / Blink", 7)
        px.text(10, 42, "ACTION2: Enter / Mouth", 7)
        px.text(10, 50, "ACTION3: Smile", 7)
        px.text(10, 58, "ESC: Quit", 5)

        # パネル枠
        px.rectb(8, 72, self.width - 16, 128, 10)

        # ラベル + カウント + フラッシュインジケータ
        rows = [
            (Action.ACTION1, "ACTION1"),
            (Action.ACTION2, "ACTION2"),
            (Action.ACTION3, "ACTION3"),
        ]
        for i, (act, name) in enumerate(rows):
            y = 86 + i * 32
            px.text(20, y, name, 7)
            cnt = self.counts.get(act, 0)
            px.text(20, y + 10, f"COUNT: {cnt}", 11)
            # ランプ
            on = self.flash[act].on()
            col = 8 if not on else 11
            px.circ(112, y + 6, 5, 0)
            px.circ(112, y + 6, 4, col)

            # バー（最近値の可視化: on中はバー点灯）
            px.rect(128, y + 2, 104, 9, 0)
            if on:
                px.rect(128, y + 2, 104, 9, 3)
                px.rectb(128, y + 2, 104, 9, 7)
            else:
                px.rectb(128, y + 2, 104, 9, 5)

        # 直近イベント
        px.text(10, 200, f"LAST: {self.last_event}", 6)


# レジストリが参照する公開シンボル
GAME_CLASS = TestGame

