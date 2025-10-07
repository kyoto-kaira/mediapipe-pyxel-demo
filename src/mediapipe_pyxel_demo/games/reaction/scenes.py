from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional

import pyxel

from ...events import Action, InputEvent


# --- 設定とアセット管理 --------------------------------

class ReactionType(Enum):
    NONE = 0
    SURPRISE = 1  # 口を開けて驚く表情
    SMILE = 2     # 笑顔

    # 整数値（0/1/2）から列挙値に変換するユーティリティ。未知の値はNONEにフォールバックします。
    @classmethod
    def from_value(cls, value: int) -> "ReactionType":
        for item in cls:
            if item.value == value:
                return item
        return cls.NONE


@dataclass(frozen=True)
class GameConfig:
    title_text: str = "Reaction Game"
    title_prompt: str = "Smile to start!"
    countdown_values: tuple[int, ...] = (3, 2, 1)
    countdown_interval: int = 15        # カウントダウンの数字が切り替わるまでのフレーム数
    total_rounds: int = 5
    line2_delay: int = 90               # 2行目の台詞が表示されるまでのフレーム数
    reaction_prompt_delay: int = 30     # 2行目の後、プロンプト/ゲージが表示されるまでのフレーム数
    reaction_window: int = 120          # プレイヤーが反応できる猶予（フレーム数）
    time_up_hold: int = 60              # 「Time Up!」の表示を保持するフレーム数
    result_hold: int = 60              # Good/Badの結果を表示し続けるフレーム数
    prompt_blink: int = 30              # プロンプト（例：Smile to start）の点滅間隔（フレーム）
    scene_dialogue_height: int = 44     # セリフ欄の高さ
    reaction_gauge_height: int = 3      # 残り時間ゲージの高さ
    reaction_gauge_margin: int = 6      # 残り時間ゲージの余白
    restart_prompt: str = "Smile to return"


CONFIG = GameConfig()


class ReactionContent:
    # シーン用の画像や台詞・解答を読み込みます。
    # ファイルが無い場合でもゲームが動くよう、プレースホルダーにフォールバックします。

    def __init__(self) -> None:
        root = Path(__file__).resolve().parents[4]
        self.base_dir = root / "assets" / "reaction"
        self.image_dir = self.base_dir / "images"
        self.lines1 = self._load_lines(self.base_dir / "lines_1.txt")
        self.lines2 = self._load_lines(self.base_dir / "lines_2.txt")
        self.answers = self._load_answers(self.base_dir / "answers.txt")
        max_count = max(len(self.lines1), len(self.lines2), len(self.answers), 0)
        self.max_question_id = max_count if max_count > 0 else CONFIG.total_rounds

    def _load_lines(self, path: Path) -> List[str]:
        try:
            with path.open("r", encoding="utf-8") as fp:
                return [line.rstrip("\n") for line in fp]
        except FileNotFoundError:
            return []

    def _load_answers(self, path: Path) -> List[ReactionType]:
        answers: List[ReactionType] = []
        try:
            with path.open("r", encoding="utf-8") as fp:
                for raw in fp:
                    stripped = raw.strip()
                    if not stripped:
                        continue
                    try:
                        val = int(stripped, 10)
                    except ValueError:
                        val = 0
                    answers.append(ReactionType.from_value(val))
        except FileNotFoundError:
            pass
        return answers

    def available_ids(self) -> List[int]:
        return list(range(1, self.max_question_id + 1))

    # 利用可能なIDからラウンド数ぶんの出題を選びます。足りない場合は重複を許して補充します。
    def pick_questions(self, total: int) -> List[int]:
        candidates = self.available_ids()
        if not candidates:
            candidates = list(range(1, total + 1))
        if len(candidates) >= total:
            return random.sample(candidates, total)
        random.shuffle(candidates)
        result = candidates[:]
        while len(result) < total:
            take = min(len(candidates), total - len(result))
            result.extend(random.sample(candidates, take))
        return result[:total]

    def line1(self, question_id: int) -> str:
        idx = question_id - 1
        if 0 <= idx < len(self.lines1):
            return self.lines1[idx]
        return f"Line 1 for scene {question_id}"

    def line2(self, question_id: int) -> str:
        idx = question_id - 1
        if 0 <= idx < len(self.lines2):
            return self.lines2[idx]
        return f"Line 2 for scene {question_id}"

    def answer(self, question_id: int) -> ReactionType:
        idx = question_id - 1
        if 0 <= idx < len(self.answers):
            return self.answers[idx]
        return ReactionType.NONE

    def image_path(self, question_id: int) -> Path:
        return self.image_dir / f"scene_{question_id}.jpeg"


CONTENT = ReactionContent()


# --- シーン基盤-----------------------------------------
# 画面をクラス（Scene）として分け、SceneManagerでスタック管理（push/pop/replace）と出題セッションを制御します。


@dataclass
class ReactionSession:
    questions: List[int]
    index: int = 0

    def current_question(self) -> Optional[int]:
        if 0 <= self.index < len(self.questions):
            return self.questions[self.index]
        return None

    def advance(self) -> None:
        self.index += 1

    @property
    def total(self) -> int:
        return len(self.questions)


class Scene:

    def __init__(self, app, manager):
        self.app = app
        self.mgr = manager

    def on_enter(self) -> None:
        pass

    def on_exit(self) -> None:
        pass

    def on_event(self, event: InputEvent) -> None:
        pass

    def update(self) -> None:
        pass

    def draw(self) -> None:
        pass


class SceneManager:

    def __init__(self):
        self.stack: List[Scene] = []
        self.session: Optional[ReactionSession] = None

    @property
    def current(self) -> Optional[Scene]:
        return self.stack[-1] if self.stack else None

    def push(self, scene: Scene) -> None:
        self.stack.append(scene)
        scene.on_enter()

    def pop(self) -> None:
        if self.stack:
            self.stack[-1].on_exit()
            self.stack.pop()

    def replace(self, scene: Scene) -> None:
        self.pop()
        self.push(scene)

    def handle_event(self, event: InputEvent) -> None:
        if self.current:
            self.current.on_event(event)

    def start_session(self, questions: List[int]) -> None:
        self.session = ReactionSession(questions=questions)

    def current_question_id(self) -> Optional[int]:
        if self.session:
            return self.session.current_question()
        return None

    def advance_question(self) -> None:
        if self.session:
            self.session.advance()


# --- ヘルパー関数 ----------------------------------------------------------------


def draw_text(text: str, x: int, y: int, color: int, scale: int = 1, outline: bool = False) -> None:
    if scale <= 1:
        if outline:
            pyxel.text(x - 1, y, text, 0)
            pyxel.text(x + 1, y, text, 0)
            pyxel.text(x, y - 1, text, 0)
            pyxel.text(x, y + 1, text, 0)
        pyxel.text(x, y, text, color)
        return

    if outline:
        for oy, ox in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            for dy in range(scale):
                for dx in range(scale):
                    pyxel.text(x + ox + dx, y + oy + dy, text, 0)

    for dy in range(scale):
        for dx in range(scale):
            pyxel.text(x + dx, y + dy, text, color)


def draw_centered_text(
    text: str,
    y: int,
    color: int,
    scale: int = 1,
    width: int = 160,
    offset_x: int = 0,
    outline: bool = False
) -> None:
    text_width = len(text) * 4 * max(1, scale)
    x = width // 2 - text_width // 2 + offset_x
    draw_text(text, x, y, color, scale, outline)


# --- 各シーンの実装 ----------------------------------------------------------------
# タイトル → カウントダウン → プレイ → スコア表示、という流れで遷移します。


class TitleScene(Scene):
    def __init__(self, app, mgr):
        super().__init__(app, mgr)
        self.start_requested = False

    def on_event(self, event: InputEvent) -> None:
        if event.action == Action.ACTION3:
            self.start_requested = True

    def update(self) -> None:
        if self.start_requested:
            questions = CONTENT.pick_questions(CONFIG.total_rounds)
            self.mgr.start_session(questions)
            self.app.score = 0
            self.start_requested = False
            self.mgr.replace(CountScene(self.app, self.mgr))

    def draw(self) -> None:
        pyxel.cls(0)
        w = self.app.width
        h = self.app.height
        palette = (1, 1, 2, 2, 4, 4, 5, 5)
        for y in range(h):
            idx = int(y / h * len(palette))
            idx = min(idx, len(palette) - 1)
            pyxel.line(0, y, w, y, palette[idx])

        draw_centered_text(CONFIG.title_text, h // 3 + 1, 0, scale=1, width=w)
        draw_centered_text(CONFIG.title_text, h // 3, 7, scale=1, width=w)

        blink_on = (pyxel.frame_count // CONFIG.prompt_blink) % 2 == 0
        if blink_on:
            draw_centered_text(CONFIG.title_prompt, h - 18, 7, width=w)


class CountScene(Scene):
    def __init__(self, app, mgr):
        super().__init__(app, mgr)
        self.index = 0
        self.timer = 0
        self.sequence = list(CONFIG.countdown_values)

    def update(self) -> None:
        self.timer += 1
        if self.timer >= CONFIG.countdown_interval:
            self.timer = 0
            self.index += 1
            if self.index >= len(self.sequence):
                question_id = self.mgr.current_question_id()
                if question_id is None:
                    question_id = 1
                self.mgr.replace(PlayScene(self.app, self.mgr, question_id))

    def draw(self) -> None:
        pyxel.cls(0)
        if self.index < len(self.sequence):
            current_number = str(self.sequence[self.index])
            draw_centered_text(current_number, self.app.height // 2 - 8, 7, scale=1, width=self.app.width)


class PlayScene(Scene):

    def __init__(self, app, mgr, question_id: int):
        super().__init__(app, mgr)
        self.question_id = question_id
        self.round_number = (self.mgr.session.index + 1) if self.mgr.session else 1
        self.line1_text = CONTENT.line1(question_id)
        self.line2_text = CONTENT.line2(question_id)
        self.expected = CONTENT.answer(question_id)
        self.frames = 0
        self.reaction_elapsed = 0
        self.line2_shown = False
        self.prompt_active = False
        self.reaction_window_active = False
        self.reaction_registered: Optional[ReactionType] = None
        self.result_ready = False
        self.result_timer = 0
        self.time_up_timer = 0
        self.time_up_phase = False
        self.score_applied = False
        self.scene_loaded = False
        self.scene_bank = 0

    def on_enter(self) -> None:
        self._load_scene_image()

    def _load_scene_image(self) -> None:
        path = CONTENT.image_path(self.question_id)
        try:
            if path.exists():
                pyxel.image(self.scene_bank).load(0, 0, str(path))
                self.scene_loaded = True
        except Exception:
            self.scene_loaded = False

    def on_event(self, event: InputEvent) -> None:
        if not self.reaction_window_active:
            return
        if event.action == Action.ACTION2:
            self.reaction_registered = ReactionType.SURPRISE
        elif event.action == Action.ACTION3:
            self.reaction_registered = ReactionType.SMILE

    def update(self) -> None:
        self.frames += 1
        if not self.line2_shown and self.frames >= CONFIG.line2_delay:
            self.line2_shown = True
            self.reaction_window_active = True
            self.reaction_elapsed = 0

        if self.line2_shown and not self.result_ready:
            self.reaction_elapsed += 1
            if self.reaction_elapsed >= CONFIG.reaction_prompt_delay:
                self.prompt_active = True
            if self.reaction_elapsed >= CONFIG.reaction_window:
                self.reaction_window_active = False
                self.prompt_active = False
                self.time_up_phase = True

        if self.time_up_phase and not self.result_ready:
            self.time_up_timer += 1
            if self.time_up_timer >= CONFIG.time_up_hold:
                self.time_up_phase = False
                self.result_ready = True
                self._evaluate_reaction()

        if self.result_ready:
            self.result_timer += 1
            if self.result_timer >= CONFIG.result_hold:
                self._proceed_next()

    def _evaluate_reaction(self) -> None:
        observed = self.reaction_registered or ReactionType.NONE
        correct = observed == self.expected
        if correct and not self.score_applied:
            self.app.score += 1
            self.score_applied = True
        self.evaluation_is_correct = correct

    def _proceed_next(self) -> None:
        self.mgr.advance_question()
        if self.mgr.session and self.mgr.session.index < self.mgr.session.total:
            self.mgr.replace(CountScene(self.app, self.mgr))
        else:
            self.mgr.replace(ScoreScene(self.app, self.mgr))

    def draw(self) -> None:
        pyxel.cls(0)
        w = self.app.width
        scene_height = self.app.height - CONFIG.scene_dialogue_height
        if self.scene_loaded:
            pyxel.rect(0, 0, w, scene_height, 0)
            pyxel.blt(0, 0, self.scene_bank, 0, 0, w, scene_height, 0)
        else:
            pyxel.rect(0, 0, w, scene_height, 1)
            placeholder = f"Scene #{self.question_id}"
            draw_centered_text(placeholder, scene_height // 2 - 6, 7, width=w)


        dialog_y = scene_height
        pyxel.rect(0, dialog_y, w, CONFIG.scene_dialogue_height, 0)
        pyxel.text(6, dialog_y + 6, self.line1_text, 7)
        round_text = f"{self.round_number}/{self.mgr.session.total if self.mgr.session else CONFIG.total_rounds}"
        round_text_width = len(round_text) * 4
        right_margin = 6
        pyxel.text(w - right_margin - round_text_width, dialog_y + 6, round_text, 7)
        if self.line2_shown:
            pyxel.text(6, dialog_y + 14, self.line2_text, 7)
        else:
            pyxel.text(6, dialog_y + 14, "..." if self.line2_text else "", 7)

        if self.prompt_active and not self.result_ready:
            pyxel.text(6, dialog_y + 27, "Reaction Now!", 8)
            remaining = max(0, CONFIG.reaction_window - self.reaction_elapsed)
            total = max(1, CONFIG.reaction_window)
            ratio = remaining / total
            margin = CONFIG.reaction_gauge_margin
            gauge_width = w - margin * 2
            filled = int(gauge_width * ratio)
            gauge_y = dialog_y + CONFIG.scene_dialogue_height - CONFIG.reaction_gauge_height - margin
            pyxel.rect(margin, gauge_y, gauge_width, CONFIG.reaction_gauge_height, 2)
            pyxel.rect(margin, gauge_y, filled, CONFIG.reaction_gauge_height, 8)

        if self.time_up_phase:
            draw_centered_text("Time Up!", dialog_y + 25, 10, scale=1, width=w)

        if self.result_ready:
            if getattr(self, "evaluation_is_correct", False):
                color = 11
                message = "Good Reaction!"
            else:
                color = 8
                message = "Bad Reaction..."
            draw_centered_text(message, dialog_y + 25, color, scale=1, width=w)


class ScoreScene(Scene):
    def __init__(self, app, mgr):
        super().__init__(app, mgr)

    def on_event(self, event: InputEvent) -> None:
        if event.action == Action.ACTION3:
            self.app.reset()

    def draw(self) -> None:
        pyxel.cls(0)
        w = self.app.width
        total = self.mgr.session.total if self.mgr.session else CONFIG.total_rounds
        draw_centered_text("Your reaction score is", 20, 7, width=w)
        score_text = f"{self.app.score}/{total}"
        draw_centered_text(score_text, self.app.height // 2 - 8, 7, scale=1, width=w)
        blink_on = (pyxel.frame_count // CONFIG.prompt_blink) % 2 == 0
        if blink_on:
            draw_centered_text(CONFIG.restart_prompt, self.app.height - 18, 7, width=w)
