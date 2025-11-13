from __future__ import annotations

from typing import List, Tuple
import random

from ...events import Action, InputEvent
from ...registry import discover_games
import pyxel


class MenuGame:
    """
    ゲーム選択メニュー。

    - ACTION1（Space）で項目を下に移動
    - ACTION2（Enter）で選択したゲームを開始
    - QUIT（Esc）で終了要求（アプリ側で処理）

    切り替えは `self.next_game` に次のゲームインスタンスを設定して
    アプリ側（App）が検知して実行する。
    """

    width = 256
    height = 224

    def __init__(self) -> None:
        # ゲーム一覧を取得（自分自身のメニューは除外）
        games = discover_games()
        items: List[Tuple[str, type, str]] = []
        for name, info in games.items():
            if name in {"menu"}:
                continue
            items.append((name, info.cls, info.source))

        # ソートして安定表示
        items.sort(key=lambda x: x[0])

        self.items = items
        self.idx = 0
        self.blink = 0
        self.next_game = None  # App 側が検知してゲーム切り替え

        # 背景用の星とスキャンライン
        rnd = random.Random(42)
        self.stars = [
            [rnd.randrange(0, self.width), rnd.randrange(0, self.height // 2), 0.1 + rnd.random() * 0.5]
            for _ in range(60)
        ]
        # 効果音の初期化フラグ（Pyxel 初期化後に設定）
        self._sfx_ready = False

    def _setup_sounds(self) -> None:
        # シンプルなビープ音をサウンドスロット5に設定
        pyxel.sounds[5].set(
            notes="c4",
            tones="t",
            volumes="4",
            effects="n",
            speed=10,
        )
        self._sfx_ready = True

    def _ensure_sounds(self) -> None:
        if self._sfx_ready:
            return
        try:
            self._setup_sounds()
        except Exception:
            # Pyxel 未初期化や他要因で失敗しても無視（次フレームで再試行）
            self._sfx_ready = False

    # --- 入力 ---
    def on_event(self, e: InputEvent) -> None:
        if not self.items:
            return
        if e.action == Action.ACTION1:
            self.idx = (self.idx + 1) % len(self.items)
            # カーソル移動時の効果音（初回は遅延初期化）
            self._ensure_sounds()
            try:
                if self._sfx_ready:
                    pyxel.play(1, 5)
            except Exception:
                pass
        elif e.action == Action.ACTION2:
            # 選択したゲームをインスタンス化して切り替え要求
            _, cls, _ = self.items[self.idx]
            try:
                self.next_game = cls()
            except Exception:
                # 失敗したら何もしない（次フレームで再度操作可能）
                self.next_game = None

    # --- 更新 ---
    def update(self) -> None:
        self.blink = (self.blink + 1) % 60
        for s in self.stars:
            s[0] -= s[2]
            if s[0] < -2:
                s[0] = self.width + 2

    # --- 描画 ---
    def draw(self, px) -> None:
        # 背景（夜空のグラデーション）
        for i in range(self.height):
            col = 1 if i < self.height // 2 else 5
            px.line(0, i, self.width, i, col)

        # 星
        for x, y, sp in self.stars:
            px.pset(int(x), int(y), 7 if (self.blink // 15) % 2 == 0 else 6)

        # タイトル
        title = "MediaPipe × Pyxel"
        sub = "SPACE: next  ENTER: start  ESC: quit"
        tx = self.width // 2 - len(title) * 2
        # アウトライン
        for dx, dy in ((-1,0),(1,0),(0,-1),(0,1)):
            px.text(tx+dx, 12+dy, title, 0)
        px.text(tx, 12, title, 7)
        px.text(self.width // 2 - len(sub) * 2, 26, sub, 6)

        if not self.items:
            px.text(20, 60, "No games found.", 8)
            return

        # リスト描画
        top = 48
        for i, (name, _, source) in enumerate(self.items):
            y = top + i * 12
            color = 11 if i == self.idx else 7
            px.text(36, y, name, color)
            px.text(self.width - 110, y, f"({source})", 5)

        # 選択中のハイライト枠
        if self.items:
            y = top + self.idx * 12 - 2
            px.rectb(28, y - 2, self.width - 56, 12, 10)


# レジストリが `module.GAME_CLASS` を参照するため公開
GAME_CLASS = MenuGame
