from __future__ import annotations

from typing import Sequence

from ...events import Action, InputEvent
from .scenes import SceneManager, TitleScene


DEFAULT_CAMERA_INDICES: tuple[int, int] = (0, 1)
DEFAULT_PLAYER_LABELS: tuple[str, str] = ("Player 1", "Player 2")


class ReactionVsGame:
    """2プレイヤー対戦型の表情リアクションゲーム。"""

    width = 256
    height = 224

    def __init__(
        self,
        camera_indices: Sequence[int] | None = None,
        player_labels: Sequence[str] | None = None,
    ) -> None:
        indices = tuple(camera_indices) if camera_indices is not None else DEFAULT_CAMERA_INDICES
        labels = tuple(player_labels) if player_labels is not None else DEFAULT_PLAYER_LABELS
        if len(indices) != 2:
            raise ValueError("ReactionVsGame requires exactly 2 camera indices.")
        if len(labels) != len(indices):
            raise ValueError("Length of player_labels must match camera_indices.")
        self.camera_indices: tuple[int, ...] = tuple(int(i) for i in indices)
        self.player_labels: tuple[str, ...] = tuple(str(label) for label in labels)
        self.player_scores: list[int] = []
        self.mgr: SceneManager | None = None
        self.reset()

    # --- helper properties -------------------------------------------------
    @property
    def player_count(self) -> int:
        return len(self.camera_indices)

    @property
    def player_event_notes(self) -> list[str]:
        return [self.player_event_note(i) for i in range(self.player_count)]

    def player_event_note(self, player_index: int) -> str:
        return f"player:{player_index + 1}"

    # --- game lifecycle ----------------------------------------------------
    def reset(self) -> None:
        self.next_game = None
        self.reset_scores()
        self.mgr = SceneManager()
        self.mgr.push(TitleScene(self, self.mgr))

    def reset_scores(self) -> None:
        self.player_scores = [0 for _ in range(self.player_count)]

    def add_score(self, player_index: int, value: int = 1) -> None:
        if 0 <= player_index < len(self.player_scores):
            self.player_scores[player_index] += value

    def set_camera_indices(self, camera_indices: Sequence[int]) -> None:
        if len(tuple(camera_indices)) != self.player_count:
            raise ValueError("camera_indices length must match player count")
        self.camera_indices = tuple(int(i) for i in camera_indices)
        self.reset_scores()

    # --- event hooks -------------------------------------------------------
    def on_event(self, event: InputEvent) -> None:
        if event.action == Action.QUIT:
            self._return_to_menu()
            return
        if self.mgr:
            self.mgr.handle_event(event)

    def update(self) -> None:
        if self.mgr and self.mgr.current:
            self.mgr.current.update()

    def draw(self, _px=None) -> None:
        if self.mgr and self.mgr.current:
            self.mgr.current.draw()

    def _return_to_menu(self) -> None:
        from ..menu.game import MenuGame

        self.next_game = MenuGame()


# レジストリが `module.GAME_CLASS` を参照するため公開
GAME_CLASS = ReactionVsGame
