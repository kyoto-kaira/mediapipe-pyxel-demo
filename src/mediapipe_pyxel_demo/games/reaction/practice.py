import random
from enum import Enum
from pathlib import Path
from dataclasses import dataclass
from typing import Self


class ReactionType(Enum):
    NONE = 0
    SURPRISED = 1
    SMILE = 2

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
    countdown_values: tuple[int, ...] = (3, 2, 1)
    countdown_interval: int = 15        # カウントダウンの数字が切り替わるまでのフレーム数
    total_rounds: int = 5               # 1ゲームの問題数
    line2_delay: int = 90               # 2行目の台詞が表示されるまでのフレーム数
    reaction_prompt_delay: int = 30     # 2行目の後、プロンプト/ゲージが表示されるまでのフレーム数
    reaction_window: int = 120          # プレイヤーが反応できる猶予（フレーム数）
    time_up_hold: int = 60              # 「Time Up!」の表示を保持するフレーム数
    result_hold: int = 60              # Good/Badの結果を表示し続けるフレーム数
    prompt_blink: int = 30              # プロンプト（例：Smile to start）の点滅間隔（フレーム）
    scene_dialogue_height: int = 80     # セリフ欄の高さ
    reaction_gauge_height: int = 3      # 残り時間ゲージの高さ
    reaction_gauge_margin: int = 6      # 残り時間ゲージの余白
    restart_prompt: str = "Smile to return"

CONFIG = GameConfig()


class ReactionAsset:
    def __init__(self):
        self.root = Path(__file__).parents[4]
        self.base_dir = self.root / "assets" / "reaction"
        self.images1_dir = self.base_dir / "images_1"
        self.images2_dir = self.base_dir / "images_2"
        self.sounds_dir = self.base_dir / "sounds"
        self.lines1 = self._load_lines(self.base_dir / "lines_1.txt")
        self.lines2 = self._load_lines(self.base_dir / "lines_2.txt")
        self.answers = self.load_answers(self.base_dir / "answers.txt")
        self.max_cnt = max(len(self.lines1), len(self.lines2), len(self.answers))
        self.max_qst_id = self.max_cnt if self.max_cnt > 0 else CONFIG.toal_rounds

    def _load_lines(self, path: Path) -> list[str]:
        try:
            return path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []

    def _load_answers(self, path: Path) -> list[ReactionType]:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []
        answers: list[ReactionType] = []
        for l in lines:
            s = l.strip()
            if not s:
                continue
            try:
                answers.append(ReactionType.from_value(int(s)))
            except ValueError:
                answers.append(ReactionType.NONE)
        return answers

    def pick_questions(self, total: int) -> list[int]:
        if self.max_qst_id > 0:
            pool = list(range(1, self.max_qst_id + 1))
        else:
            pool = list(range(1, total + 1))
        if len(pool) > total:
            return random.sample(pool, total)
        random.shuffle(pool)
        result = pool[:]
        while len(result) < total:
            take_cnt = min(pool, total - len(result))
            result.extend(random.sample(pool, take_cnt))
        return result[:total]