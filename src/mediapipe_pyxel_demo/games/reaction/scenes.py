from __future__ import annotations

import random
import traceback
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Self

import pyxel
from PyxelUniversalFont import Writer as PythonUniversalFont

from ...events import Action, InputEvent


# --- 設定とアセット管理 --------------------------------

class ReactionType(Enum):
    NONE = 0
    SURPRISE = 1  # 口を開けて驚く表情
    SMILE = 2     # 笑顔

    # 整数値（0/1/2）から列挙値に変換
    @classmethod
    def from_value(cls, value: int) -> Self:
        for item in cls:
            if item.value == value:
                return item
        return cls.NONE


@dataclass(frozen=True)
class GameConfig:
    title_text: str = "Speed React"
    title_prompt: str = "Smile to start!"
    restart_prompt: str = "Smile to return"
    countdown_values: tuple[int, ...] = (3, 2, 1)
    countdown_interval: int = 15        # カウントダウンの数字が切り替わるまでのフレーム数
    total_rounds: int = 5               # 1ゲームの問題数
    line2_delay: int = 90               # 2行目の台詞が表示されるまでのフレーム数
    reaction_prompt_delay: int = 30     # 2行目の後、プロンプト/ゲージが表示されるまでのフレーム数
    reaction_window: int = 120          # プレイヤーが反応できる猶予フレーム数
    time_up_hold: int = 60              # 「Time Up!」の表示を保持するフレーム数
    result_hold: int = 60               # Good/Badの結果を表示し続けるフレーム数
    prompt_blink: int = 30              # プロンプト（例：Smile to start）の点滅間隔
    scene_dialogue_height: int = 80     # セリフ欄の高さ
    reaction_gauge_height: int = 3      # 残り時間ゲージの高さ
    reaction_gauge_margin: int = 6      # 残り時間ゲージの余白

CONFIG = GameConfig()


class ReactionAsset:
    # シーン用のアセットを読み込みます。
    # ファイルが無い場合でもゲームが動くよう、プレースホルダーにフォールバックします。

    def __init__(self) -> None:
        root = Path(__file__).resolve().parents[4]
        self.base_dir = root / "assets" / "reaction"
        self.image1_dir = self.base_dir / "images_1"
        self.image2_dir = self.base_dir / "images_2"
        self.sound_dir = self.base_dir / "sounds"
        self.lines1 = self._load_lines(self.base_dir / "lines_1.txt")
        self.lines2 = self._load_lines(self.base_dir / "lines_2.txt")
        self.answers = self._load_answers(self.base_dir / "answers.txt")
        max_count = max(len(self.lines1), len(self.lines2), len(self.answers), 0)
        self.max_qst_id = max_count if max_count > 0 else CONFIG.total_rounds

    def _load_lines(self, path: Path) -> list[str]:
        try:
            return path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []

    def _load_answers(self, path: Path) -> list[ReactionType]:
        answers: list[ReactionType] = []
        lines = self._load_lines(path)
        for ln in lines:
            s = ln.strip()
            if not s:
                continue
            try:
                answers.append(ReactionType.from_value(int(s)))
            except ValueError:
                answers.append(ReactionType.NONE)
        return answers

    # 利用可能なIDから問題をランダムに選びます。足りない場合は重複を許して補充します。
    def pick_questions(self, total: int) -> list[int]:
        pool = list(range(1, self.max_qst_id + 1))
        if not pool:
            pool = list(range(1, total + 1))
        if len(pool) >= total:
            return random.sample(pool, total)
        random.shuffle(pool)
        result = pool[:]
        while len(result) < total:
            take = min(len(pool), total - len(result))
            result.extend(random.sample(pool, take))
        return result[:total]

    def line1(self, qst_id: int) -> str:
        idx = qst_id - 1
        if 0 <= idx < len(self.lines1):
            return self.lines1[idx]
        return f"Line 1 for scene {qst_id}"

    def line2(self, qst_id: int) -> str:
        idx = qst_id - 1
        if 0 <= idx < len(self.lines2):
            return self.lines2[idx]
        return f"Line 2 for scene {qst_id}"

    def answer(self, qst_id: int) -> ReactionType:
        idx = qst_id - 1
        if 0 <= idx < len(self.answers):
            return self.answers[idx]
        return ReactionType.NONE

    def image_path(self, qst_id: int, phase: int = 1) -> Optional[Path]:
        dirs = [self.image2_dir, self.image1_dir] if phase == 2 else [self.image1_dir]
        for d in dirs:
            path = self._resolve_image_path(d, qst_id)
            if path:
                return path
        return dirs[0] / f"scene_{qst_id}.jpeg"

    def _resolve_image_path(self, dir: Path, qst_id: int) -> Optional[Path]:
        fname = f"scene_{qst_id}"
        exts = (".png", ".jpg", ".jpeg")
        for e in exts:
            path = dir / f"{fname}{e}"
            if path.exists():
                return path
        return None

ASSET = ReactionAsset()


class ReactionSoundPlayer:

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def play(self, event: str, qst_id: Optional[int] = None) -> bool:
        path = self._find_sound_path(event, qst_id)
        if not path:
            return False
        try:
            pyxel.load(str(path),exclude_images=True)
            pyxel.play(0, 0)
        except Exception as e:
            print(f"[ReactionSoundPlayer] Sound load error for '{path}': {e}")
            traceback.print_exc()
            return False

    def _find_sound_path(self, event: str, qst_id: Optional[int]) -> Optional[Path]:
        names: list[str] = []
        if qst_id is not None:
            names.append(f"scene_{qst_id}_{event}")
        names.append(event)
        for n in names:
            path = self.base_dir / f"{n}.pyxres"
            if path.exists():
                return path
        return None

SOUND_PLAYER = ReactionSoundPlayer(ASSET.sound_dir)


# --- シーン基盤-----------------------------------------
# 画面をクラス（Scene）として分け、SceneManagerでスタック管理（push/pop/replace）と出題セッションを制御します。


@dataclass
class ReactionSession:
    questions: list[int]
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
        self.stack: list[Scene] = []
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

    def start_session(self, questions: list[int]) -> None:
        self.session = ReactionSession(questions=questions)

    def current_qst_id(self) -> Optional[int]:
        if self.session:
            return self.session.current_question()
        return None

    def advance_question(self) -> None:
        if self.session:
            self.session.advance()


# --- ヘルパー関数 ----------------------------------------------------------------

FONT_NAME = "IPA_Gothic.ttf"
FONT_BASE_SIZE = 16
FONT_WRITER = PythonUniversalFont(FONT_NAME)


def measure_text_width(text: str, scale: int = 1) -> int:
    if not text:
        return 0
    font_size = FONT_BASE_SIZE * max(1, scale)
    return font_size * len(text)


def draw_text(text: str, x: int, y: int, color: int, scale: int = 1, outline: bool = False) -> None:
    if not text:
        return
    font_size = FONT_BASE_SIZE * max(1, scale)
    if outline:
        for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            FONT_WRITER.draw(
                x + ox,
                y + oy,
                text,
                font_size=font_size,
                font_color=0,
                background_color=-1,
            )
    FONT_WRITER.draw(
        x,
        y,
        text,
        font_size=font_size,
        font_color=color,
        background_color=-1,
    )


def draw_centered_text(
    text: str,
    y: int,
    color: int,
    scale: int = 1,
    width: int = 256,
    offset_x: int = 0,
    outline: bool = False
) -> None:
    text_width = measure_text_width(text, scale)
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
            questions = ASSET.pick_questions(CONFIG.total_rounds)
            self.mgr.start_session(questions)
            self.app.score = 0
            self.start_requested = False
            SOUND_PLAYER.play("count")
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

        draw_centered_text(CONFIG.title_text, h // 3 + 1, 0, scale=2, width=w, offset_x=84)
        draw_centered_text(CONFIG.title_text, h // 3, 7, scale=2, width=w, offset_x=84)

        blink_on = (pyxel.frame_count // CONFIG.prompt_blink) % 2 == 0
        if blink_on:
            draw_centered_text(CONFIG.title_prompt, h - 40 + 1, 0, width=w, offset_x=58)
            draw_centered_text(CONFIG.title_prompt, h - 40, 7, width=w, offset_x=58)


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
                qst_id = self.mgr.current_qst_id()
                if qst_id is None:
                    qst_id = 1
                self.mgr.replace(PlayScene(self.app, self.mgr, qst_id))
            else:
                SOUND_PLAYER.play("count")

    def draw(self) -> None:
        pyxel.cls(0)
        if self.index < len(self.sequence):
            current_number = str(self.sequence[self.index])
            draw_centered_text(current_number, self.app.height // 2 - 30, 7, scale=3, width=self.app.width, offset_x=10)


class PlayScene(Scene):

    def __init__(self, app, mgr, qst_id: int):
        super().__init__(app, mgr)
        self.qst_id = qst_id
        self.round_number = (self.mgr.session.index + 1) if self.mgr.session else 1
        self.line1_text = ASSET.line1(qst_id)
        self.line2_text = ASSET.line2(qst_id)
        self.expected = ASSET.answer(qst_id)
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
        self.scene_bank = 1
        self.current_image_variant = 0
        self.line2_transition_done = False
        self.prompt_sound_played = False
        self.time_up_sound_played = False
        self.result_sound_played = False

    def on_enter(self) -> None:
        self.scene_loaded = self._load_scene_image(variant=1)
        if self.scene_loaded:
            self.current_image_variant = 1
        self._play_sound("start")

    def _load_scene_image(self, variant: int) -> bool:
        path = ASSET.image_path(self.qst_id, variant)
        if not path or not path.exists():
            return False
        try:
            pyxel.images[self.scene_bank].load(0, 0, str(path))
        except Exception:
            return False
        self.scene_loaded = True
        self.current_image_variant = variant
        return True

    def _play_sound(self, *events: str) -> None:
        for event in events:
            if SOUND_PLAYER.play(event, self.qst_id):
                return

    def _handle_line2_shown(self) -> None:
        self.line2_shown = True
        self.reaction_window_active = True
        self.reaction_elapsed = 0
        self.line2_transition_done = self._load_scene_image(variant=2)
        self._play_sound("line2")

    def on_event(self, event: InputEvent) -> None:
        if not self.reaction_window_active:
            return
        if event.action == Action.ACTION2:
            if self.reaction_registered != ReactionType.SURPRISE:
                self.reaction_registered = ReactionType.SURPRISE
        elif event.action == Action.ACTION3:
            if self.reaction_registered != ReactionType.SMILE:
                self.reaction_registered = ReactionType.SMILE

    def update(self) -> None:
        self.frames += 1
        if not self.line2_shown and self.frames >= CONFIG.line2_delay:
            self._handle_line2_shown()

        if self.line2_shown and not self.result_ready:
            self.reaction_elapsed += 1
            if (
                not self.prompt_active
                and self.reaction_elapsed >= CONFIG.reaction_prompt_delay
            ):
                self.prompt_active = True
                if not self.prompt_sound_played:
                    self._play_sound("prompt")
                    self.prompt_sound_played = True
            if self.reaction_elapsed >= CONFIG.reaction_window:
                if self.reaction_window_active:
                    self.reaction_window_active = False
                if self.prompt_active:
                    self.prompt_active = False
                if not self.time_up_phase:
                    self.time_up_phase = True
                    self.time_up_timer = 0
                    if not self.time_up_sound_played:
                        self._play_sound("line2")
                        self.time_up_sound_played = True

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
        if not self.result_sound_played:
            if correct:
                self._play_sound("result_good")
            else:
                self._play_sound("result_bad")
            self.result_sound_played = True

    def _proceed_next(self) -> None:
        self.mgr.advance_question()
        if self.mgr.session and self.mgr.session.index < self.mgr.session.total:
            SOUND_PLAYER.play("count")
            self.mgr.replace(CountScene(self.app, self.mgr))
        else:
            self._play_sound("finish")
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
            placeholder = f"Scene #{self.qst_id}"
            draw_centered_text(placeholder, scene_height // 2 - 6, 7, width=w)


        dialog_y = scene_height
        pyxel.rect(0, dialog_y, w, CONFIG.scene_dialogue_height, 0)
        draw_text(self.line1_text, 6, dialog_y + 6, 7)
        round_text = f"{self.round_number}/{self.mgr.session.total if self.mgr.session else CONFIG.total_rounds}"
        round_text_width = measure_text_width(round_text)
        right_margin = 6
        draw_text(round_text, w - right_margin - round_text_width + 20, dialog_y + 6, 7)
        if self.line2_shown:
            draw_text(self.line2_text, 6, dialog_y + 30, 7)
        else:
            draw_text("..." if self.line2_text else "", 6, dialog_y + 30, 7)

        if self.prompt_active and not self.result_ready:
            draw_text("Reaction Now!", 6, dialog_y + 54, 8)
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
            draw_centered_text("Time Up!", dialog_y + 54, 10, scale=1, width=w, offset_x=30)

        if self.result_ready:
            if getattr(self, "evaluation_is_correct", False):
                color = 11
                message = "Good Reaction!"
            else:
                color = 8
                message = "Bad Reaction..."
            draw_centered_text(message, dialog_y + 54, color, scale=1, width=w, offset_x=60)


class ScoreScene(Scene):
    def __init__(self, app, mgr):
        super().__init__(app, mgr)

    def on_event(self, event: InputEvent) -> None:
        if event.action == Action.ACTION3:
            SOUND_PLAYER.play("count")
            self.app.reset()

    def draw(self) -> None:
        pyxel.cls(0)
        w = self.app.width
        total = self.mgr.session.total if self.mgr.session else CONFIG.total_rounds
        draw_centered_text("Your reaction score is", 60, 7, width=w, offset_x=90)
        score_text = f"{self.app.score}/{total}"
        draw_centered_text(score_text, self.app.height // 2 - 8, 7, scale=2, width=w, offset_x=20)
        blink_on = (pyxel.frame_count // CONFIG.prompt_blink) % 2 == 0
        if blink_on:
            draw_centered_text(CONFIG.restart_prompt, self.app.height - 40, 7, width=w, offset_x=58)
