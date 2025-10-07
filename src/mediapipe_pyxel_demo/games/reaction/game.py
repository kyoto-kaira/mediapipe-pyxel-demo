from __future__ import annotations
from ...events import InputEvent
from .scenes import SceneManager, TitleScene

class ReactionGame:
    """
    表情リアクションゲーム:
    - ACTION2（Enter）で驚き顔
    - ACTION3（Shift）で笑顔
    - シーンに合わせたリアクションを選ぶとスコア加算
    - 笑顔でタイトル開始・リスタート
    """

    width = 160
    height = 120

    def __init__(self) -> None:
        self.reset()

    # --- game lifecycle ---
    def reset(self) -> None:
        self.score = 0
        self.mgr = SceneManager()
        self.mgr.push(TitleScene(self, self.mgr))

    def on_event(self, event: InputEvent) -> None:
        if self.mgr:
            self.mgr.handle_event(event)

    def update(self):
        if self.mgr.current:
            self.mgr.current.update()

    def draw(self, _px=None):
        if self.mgr.current:
            self.mgr.current.draw()

# レジストリが `module.GAME_CLASS` を参照するため、
# モジュール変数として公開しておく
GAME_CLASS = ReactionGame
