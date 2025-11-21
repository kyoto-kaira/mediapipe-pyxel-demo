from __future__ import annotations

import queue
from queue import Queue
import sys
import traceback
from typing import Any, List, Optional

from .events import Action, InputEvent


class App:
    def __init__(self, game: Any, providers: List[Any], scale: int = 3) -> None:
        self.game = game
        self.providers = providers
        self.scale = scale
        self.events: "Queue[InputEvent]" = Queue()
        self._px = None  # Pyxel モジュール（遅延読み込み）
        self._should_quit = False
        self._menu_cls = None

    # --- ライフサイクル ---

    def run(self) -> None:
        import pyxel  # ユニットテスト時の import 失敗を避けるため遅延インポート

        self._px = pyxel
        # スレッド型プロバイダを起動
        for p in self.providers:
            if hasattr(p, "start"):
                try:
                    p.start(self.events)
                except Exception:
                    traceback.print_exc(file=sys.stderr)

        try:
            pyxel.init(
                self.game.width,
                self.game.height,
                title="MediaPipe × Pyxel Demo",
                scale=self.scale,
            )
        except TypeError:
            pyxel.init(
                self.game.width,
                self.game.height,
                title="MediaPipe × Pyxel Demo",
            )
        pyxel.run(self._update, self._draw)

    def _update(self) -> None:
        assert self._px is not None
        # 1フレーム毎に Pyxel へアクセスが必要なプロバイダをポーリング
        for p in self.providers:
            if hasattr(p, "poll"):
                try:
                    p.poll(self._px, self.events)
                except Exception:
                    # ログが毎フレーム大量に出ないよう、各プロバイダにつき一度だけ詳細を出力
                    if not getattr(p, "_error_logged", False):
                        traceback.print_exc(file=sys.stderr)
                        try:
                            setattr(p, "_error_logged", True)
                        except Exception:
                            pass

        menu_active = self._is_menu_game()

        # 入力イベントキューを空にしつつゲームへ転送
        while True:
            try:
                e = self.events.get_nowait()
            except queue.Empty:
                break
            if menu_active and getattr(e, "note", None) != "keyboard":
                continue
            if e.action == Action.QUIT:
                # ゲームに先に渡して、ゲーム側で処理するか判断させる
                try:
                    self.game.on_event(e)
                except Exception:
                    pass
                # ゲームが next_game を設定しなかった場合のみ終了フラグを立てる
                try:
                    next_game = getattr(self.game, "next_game", None)
                except Exception:
                    next_game = None
                if next_game is None:
                    self._should_quit = True
            else:
                try:
                    self.game.on_event(e)
                except Exception:
                    pass

        # ゲームロジックの更新
        try:
            self.game.update()
        except Exception:
            pass

        # ゲーム側からのゲーム切り替え要求に対応
        # （メニューから選択されたゲームへ切り替え）
        try:
            next_game = getattr(self.game, "next_game", None)
        except Exception:
            next_game = None
        if next_game is not None:
            # 次のゲームへ切り替え
            self.game = next_game
            self._should_quit = False

        if self._should_quit:
            # ESC（KeyboardProvider 側の対応）やウィンドウクローズで終了を促す
            # Pyxel は直接 quit を呼べないため、ここではフラグのみ保持
            pass

    def _draw(self) -> None:
        assert self._px is not None
        try:
            self.game.draw(self._px)
        except Exception:
            # 描画で例外が起きても画面をクリアして安全に継続
            self._px.cls(0)

    def _is_menu_game(self) -> bool:
        if self._menu_cls is None:
            from .games.menu.game import MenuGame

            self._menu_cls = MenuGame
        return isinstance(self.game, self._menu_cls)
