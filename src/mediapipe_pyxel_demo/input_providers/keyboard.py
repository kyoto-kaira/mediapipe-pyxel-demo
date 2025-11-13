from __future__ import annotations

from queue import Queue
from typing import Optional

from ..events import Action, InputEvent


class KeyboardProvider:
    """
    Pyxel のキーボード状態をポーリングするデバッグ用入力プロバイダ。
    - Space -> ACTION1
    - Enter -> ACTION2
    - Shift -> ACTION3
    - Esc   -> QUIT
    """

    def __init__(self, note: str = "keyboard") -> None:
        self._last_space = False
        self._last_enter = False
        self._last_escape = False
        self._note = note

    def poll(self, px, out_queue: Queue) -> None:  # type: ignore[override]
        # Pyxel が利用可能になった後にキーコードへアクセスする（遅延参照）
        if px is None:
            return

        space = px.btnp(px.KEY_SPACE)
        enter = px.btnp(px.KEY_RETURN)
        shift = px.btnp(px.KEY_SHIFT)
        esc = px.btnp(px.KEY_ESCAPE)

        if space:
            out_queue.put(InputEvent(action=Action.ACTION1, note=self._note))
        if enter:
            out_queue.put(InputEvent(action=Action.ACTION2, note=self._note))
        if shift:
            out_queue.put(InputEvent(action=Action.ACTION3, note=self._note))
        if esc:
            out_queue.put(InputEvent(action=Action.QUIT, note=self._note))
