from __future__ import annotations

from typing import List, Tuple

from ...events import Action, InputEvent
from ...registry import discover_games


class MenuGame:
    """
    ゲーム選択メニュー。

    - ACTION1（Space）で項目を下に移動
    - ACTION2（Enter）で選択したゲームを開始
    - QUIT（Esc）で終了要求（アプリ側で処理）

    切り替えは `self.next_game` に次のゲームインスタンスを設定して
    アプリ側（App）が検知して実行する。
    """

    width = 160
    height = 120

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

    # --- 入力 ---
    def on_event(self, e: InputEvent) -> None:
        if not self.items:
            return
        if e.action == Action.ACTION1:
            self.idx = (self.idx + 1) % len(self.items)
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

    # --- 描画 ---
    def draw(self, px) -> None:
        px.cls(0)

        title = "Select Game"
        sub = "SPACE: next  ENTER: start  ESC: quit"
        # タイトル
        x = self.width // 2 - len(title) * 2
        px.text(x, 8, title, 7)
        px.text(self.width // 2 - len(sub) * 2, 18, sub, 6)

        if not self.items:
            px.text(20, 60, "No games found.", 8)
            return

        # リスト描画
        top = 36
        for i, (name, _, source) in enumerate(self.items):
            y = top + i * 10
            color = 11 if i == self.idx else 7
            marker = ">" if (i == self.idx and self.blink < 45) else " "
            px.text(24, y, f"{marker} {name}", color)
            px.text(120, y, f"({source})", 5)


# レジストリが `module.GAME_CLASS` を参照するため公開
GAME_CLASS = MenuGame

