from __future__ import annotations

from dataclasses import dataclass
from typing import List

from ...events import Action, InputEvent


@dataclass
class Obstacle:
    # 障害物の情報（位置とサイズ、通過済みフラグ）
    x: float
    y: int
    w: int
    h: int
    passed: bool = False


class RunnerGame:
    """
    1ボタンランナーゲーム:
    - ACTION1（Space）でジャンプ
    - 迫ってくる障害物を回避
    - 障害物を通過するとスコア加算
    - ゲームオーバー後はACTION1でリスタート
    """

    width = 160
    height = 120

    def __init__(self) -> None:
        self.reset()

    # --- game lifecycle ---
    def reset(self) -> None:
        # ワールド関連
        self.ground_y = self.height - 16
        self.scroll = 1.0
        self.speed = 1.5
        self.max_speed = 3.0
        self.accel = 0.0008  # 時間とともに少しずつ加速

        # プレイヤー関連
        self.px = 24.0
        self.py = float(self.ground_y)
        self.vy = 0.0
        self.gravity = 0.25
        self.jump_v = -4.6
        self.on_ground = True
        self.player_w = 10
        self.player_h = 12

        # 障害物
        self.obstacles: List[Obstacle] = []
        self.spawn_timer = 0
        self.spawn_cooldown = 60  # 生成間隔（フレーム数）

        # スコア / 状態
        self.score = 0
        self.best = getattr(self, "best", 0)
        self.game_over = False
        self.frames = 0

    # --- アプリから呼ばれる入力API ---
    def on_event(self, e: InputEvent) -> None:
        if e.action == Action.ACTION1:
            if self.game_over:
                self.reset()
                return
            if self.on_ground:
                self.vy = self.jump_v
                self.on_ground = False
        # ACTION2 と QUIT はここでは未使用（QUITはアプリ側で処理）

    # --- 更新 / 描画 ---
    def update(self) -> None:
        if self.game_over:
            return

        self.frames += 1
        # 時間経過で少しずつ速度アップ
        self.speed = min(self.max_speed, self.speed + self.accel)

        # 重力を適用して位置を更新
        self.vy += self.gravity
        self.py += self.vy

        # 地面との当たり判定
        if self.py >= self.ground_y:
            self.py = float(self.ground_y)
            self.vy = 0.0
            self.on_ground = True

        # 障害物の生成
        self.spawn_timer -= 1
        if self.spawn_timer <= 0:
            # 高さ・幅を少し変化させてバリエーションを出す
            base_h = 10
            var = 4 if (self.frames // 180) % 2 == 0 else 0
            h = base_h + var
            w = 8 + ((self.frames // 240) % 3) * 2
            obs = Obstacle(x=self.width + 8, y=self.ground_y - h + 1, w=w, h=h)
            self.obstacles.append(obs)
            # 次回の生成タイミング（疑似ランダムな間隔）
            self.spawn_cooldown = max(40, self.spawn_cooldown - 1)
            gap = self.spawn_cooldown + (self.frames % 23)
            self.spawn_timer = gap

        # 障害物の移動とスコア加算・掃除
        for obs in self.obstacles:
            obs.x -= self.speed
            # プレイヤーを通過したらスコア加算
            if not obs.passed and obs.x + obs.w < self.px:
                obs.passed = True
                self.score += 1

        # 画面外の障害物を削除
        self.obstacles = [o for o in self.obstacles if o.x + o.w > -4]

        # 当たり判定（AABB）
        if self._collides():
            self.game_over = True
            self.best = max(self.best, self.score)

    def _collides(self) -> bool:
        # プレイヤーの矩形
        px1 = self.px - self.player_w // 2
        py1 = self.py - self.player_h
        px2 = self.px + self.player_w // 2
        py2 = self.py

        for o in self.obstacles:
            ox1 = o.x
            oy1 = o.y
            ox2 = o.x + o.w
            oy2 = o.y + o.h
            if not (px2 < ox1 or px1 > ox2 or py2 < oy1 or py1 > oy2):
                return True
        return False

    def draw(self, px) -> None:
        # 背景クリア
        px.cls(0)

        # 地面ライン
        px.line(0, self.ground_y + 1, self.width, self.ground_y + 1, 5)

        # プレイヤー（四角＋目）
        p_left = int(self.px - self.player_w // 2)
        p_top = int(self.py - self.player_h)
        px.rect(p_left, p_top, self.player_w, self.player_h, 11)
        # 目
        px.pset(p_left + 3, p_top + 3, 1)
        px.pset(p_left + 6, p_top + 3, 1)

        # 障害物
        for o in self.obstacles:
            px.rect(int(o.x), int(o.y), o.w, o.h, 8)

        # UI
        px.text(4, 4, f"SCORE: {self.score}", 7)
        if self.best:
            px.text(92, 4, f"BEST: {self.best}", 6)

        if self.game_over:
            msg = "GAME OVER"
            sub = "Press SPACE to retry"
            w = len(msg) * 4
            x = self.width // 2 - w // 2
            y = self.height // 2 - 10
            px.text(x, y, msg, 7)
            w2 = len(sub) * 4
            x2 = self.width // 2 - w2 // 2
            px.text(x2, y + 10, sub, 5)

# レジストリが `module.GAME_CLASS` を参照するため、
# モジュール変数として公開しておく
GAME_CLASS = RunnerGame
