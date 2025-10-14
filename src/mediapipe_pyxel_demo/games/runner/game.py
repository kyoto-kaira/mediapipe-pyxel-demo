from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import pyxel

from ...events import Action, InputEvent

ASSET_RELATIVE_PATH = Path("assets") / "runner" / "images" / "kaira_kun_trans.png"


@dataclass
class Obstacle:
    """障害物を表すデータクラス"""
    x: float  # X座標
    y: int    # Y座標
    w: int    # 幅
    h: int    # 高さ
    passed: bool = False  # プレイヤーが通過したか


class RunnerGame:
    """口を開けてジャンプする横スクロールランナーゲーム"""

    width = 256
    height = 224

    # プレイヤー関連の定数
    _PLAYER_IMAGE_BANK = 0
    _PLAYER_SIZE = 45
    _INITIAL_PLAYER_X = 40.0
    _HITBOX_SCALE = 0.7  # 当たり判定のサイズ比率

    # 物理パラメータ
    _GRAVITY = 0.25
    _JUMP_VELOCITY = -6.5

    # ゲームスピード関連
    _INITIAL_SCROLL = 1.0
    _INITIAL_SPEED = 1.8
    _MAX_SPEED = 5
    _ACCELERATION = 0.005

    # 障害物のスポーン間隔
    _INITIAL_SPAWN_COOLDOWN = 120
    _MINIMUM_SPAWN_COOLDOWN = 60

    _CLOUD_LAYOUT = (
        (0.3, 40, ((-20, 20), (80, 35), (180, 25))),
        (0.2, 60, ((40, 45), (150, 50))),
    )

    def __init__(self) -> None:
        self.next_game = None
        self.player_image_bank = self._PLAYER_IMAGE_BANK
        self.player_image_loaded = False
        self._load_player_image()
        self._setup_sounds()
        self.reset()

    def _setup_sounds(self) -> None:
        """ジャンプ音を設定する"""
        pyxel.sound(0).set(
            notes="c3e3g3",
            tones="t",
            volumes="4",
            effects="n",
            speed=5,
        )

    def _load_player_image(self) -> None:
        """アセットディレクトリからプレイヤースプライトを読み込む"""
        root = Path(__file__).resolve().parents[4]
        image_path = root / ASSET_RELATIVE_PATH
        try:
            if image_path.exists():
                pyxel.image(self.player_image_bank).load(0, 0, str(image_path))
                self.player_image_loaded = True
        except Exception:
            self.player_image_loaded = False

    def reset(self) -> None:
        """ゲームをリセットする"""
        self._reset_world()
        self._reset_player_state()
        self._reset_obstacles()
        self._reset_score()

    def _reset_world(self) -> None:
        self.ground_y = int(self.height * 2 / 3)
        self.scroll = self._INITIAL_SCROLL
        self.speed = self._INITIAL_SPEED
        self.accel = self._ACCELERATION
        self.max_speed = self._MAX_SPEED

    def _reset_player_state(self) -> None:
        self.px = self._INITIAL_PLAYER_X
        self.py = float(self.ground_y)
        self.vy = 0.0
        self.gravity = self._GRAVITY
        self.jump_v = self._JUMP_VELOCITY
        self.on_ground = True
        self.player_w = self._PLAYER_SIZE
        self.player_h = self._PLAYER_SIZE

    def _reset_obstacles(self) -> None:
        self.obstacles: list[Obstacle] = []
        self.spawn_timer = 0
        self.spawn_cooldown = self._INITIAL_SPAWN_COOLDOWN

    def _reset_score(self) -> None:
        self.score = 0
        self.best = getattr(self, "best", 0)
        self.game_over = False
        self.frames = 0

    def on_event(self, event: InputEvent) -> None:
        """入力イベントを処理する"""
        # ESCキーでメニューに戻る
        if event.action == Action.QUIT:
            from ..menu.game import MenuGame
            self.next_game = MenuGame()
            return

        if event.action != Action.ACTION2:
            return

        if self.game_over:
            self.reset()
            return

        # 地面にいる時のみジャンプ可能
        if self.on_ground:
            self.vy = self.jump_v
            self.on_ground = False
            pyxel.play(0, 0)

    def update(self) -> None:
        """ゲーム状態を更新する"""
        if self.game_over:
            return

        self.frames += 1
        self._update_speed()
        self._update_player_position()
        self._maybe_spawn_obstacle()
        self._advance_obstacles()
        self._handle_collisions()

    def _update_speed(self) -> None:
        self.speed = min(self.max_speed, self.speed + self.accel)

    def _update_player_position(self) -> None:
        """プレイヤーの位置を更新する（重力・ジャンプ）"""
        self.vy += self.gravity
        self.py += self.vy

        if self.py >= self.ground_y:
            self.py = float(self.ground_y)
            self.vy = 0.0
            self.on_ground = True

    def _maybe_spawn_obstacle(self) -> None:
        """タイマーに従って障害物を生成する"""
        self.spawn_timer -= 1
        if self.spawn_timer > 0:
            return

        # 障害物のサイズを時間経過で変化させる
        base_height = 25
        height_variation = 10 if (self.frames // 180) % 2 == 0 else 0
        obstacle_height = base_height + height_variation
        obstacle_width = 15 + ((self.frames // 240) % 3) * 3

        obstacle = Obstacle(
            x=self.width + 8,
            y=self.ground_y - obstacle_height + 1,
            w=obstacle_width,
            h=obstacle_height,
        )
        self.obstacles.append(obstacle)

        # スポーン間隔を徐々に短くする
        self.spawn_cooldown = max(self._MINIMUM_SPAWN_COOLDOWN, self.spawn_cooldown - 1)
        gap = self.spawn_cooldown + (self.frames % 30)
        self.spawn_timer = gap

    def _advance_obstacles(self) -> None:
        """障害物を左に移動させ、通過したらスコアを加算する"""
        for obstacle in self.obstacles:
            obstacle.x -= self.speed
            if not obstacle.passed and obstacle.x + obstacle.w < self.px:
                obstacle.passed = True
                self.score += 1

        # 画面外の障害物を削除
        self.obstacles = [o for o in self.obstacles if o.x + o.w > -4]

    def _handle_collisions(self) -> None:
        if self._collides():
            self.game_over = True
            self.best = max(self.best, self.score)

    def _player_hitbox(self) -> tuple[float, float, float, float]:
        """プレイヤーの当たり判定を計算する（x1, y1, x2, y2）"""
        hitbox_w = self.player_w * self._HITBOX_SCALE
        hitbox_h = self.player_h * self._HITBOX_SCALE
        center_x = self.px
        center_y = self.py - self.player_h // 2
        half_w = hitbox_w / 2
        half_h = hitbox_h / 2
        return (
            center_x - half_w,
            center_y - half_h,
            center_x + half_w,
            center_y + half_h,
        )

    def _collides(self) -> bool:
        """プレイヤーと障害物の衝突判定を行う"""
        px1, py1, px2, py2 = self._player_hitbox()
        for obstacle in self.obstacles:
            ox1 = obstacle.x
            oy1 = obstacle.y
            ox2 = obstacle.x + obstacle.w
            oy2 = obstacle.y + obstacle.h
            # 矩形の衝突判定
            if not (px2 < ox1 or px1 > ox2 or py2 < oy1 or py1 > oy2):
                return True
        return False

    def draw(self, px) -> None:
        """ゲーム画面を描画する"""
        self._draw_background(px)
        self._draw_ground(px)
        self._draw_obstacles(px)
        self._draw_player(px)
        self._draw_ui(px)

    def _draw_background(self, px) -> None:
        self._draw_sky_gradient(px)
        self._draw_stars(px)
        self._draw_clouds(px)

    def _draw_sky_gradient(self, px) -> None:
        """グラデーションの空を描画する"""
        for y in range(self.height):
            if y < self.height // 4:
                color = 1
            elif y < self.height // 2:
                color = 5
            elif y < self.ground_y:
                color = 12
            else:
                color = 3
            px.line(0, y, self.width, y, color)

    def _draw_stars(self, px) -> None:
        """点滅する星を描画する"""
        for i in range(20):
            star_x = (i * 37 + int(self.frames * 0.1)) % self.width
            star_y = (i * 23) % (self.height // 3)
            if (self.frames + i * 10) % 60 < 30:
                px.pset(star_x, star_y, 7)

    def _draw_clouds(self, px) -> None:
        """流れる雲を描画する"""
        for speed, extra, offsets in self._CLOUD_LAYOUT:
            span = self.width + extra
            base_offset = int((self.frames * speed) % span)
            for offset_x, offset_y in offsets:
                self._draw_cloud(px, base_offset + offset_x, offset_y)

    def _draw_cloud(self, px, x: int, y: int) -> None:
        if x < -30 or x > self.width:
            return
        px.circ(x, y, 6, 7)
        px.circ(x + 8, y, 5, 7)
        px.circ(x + 14, y, 6, 7)
        px.circ(x + 4, y - 4, 5, 7)
        px.circ(x + 10, y - 3, 4, 7)

    def _draw_ground(self, px) -> None:
        """地面とその下の土を描画する"""
        ground_top = self.ground_y
        # 地面の草を描画
        for x in range(0, self.width, 4):
            offset = (x + self.frames) % 8
            if offset < 4:
                px.pset(x, ground_top - 1, 11)
            if (x + self.frames) % 17 < 3:
                px.pset(x, ground_top - 2, 11)

        # 地面のライン
        px.line(0, self.ground_y + 1, self.width, self.ground_y + 1, 11)
        px.line(0, self.ground_y + 2, self.width, self.ground_y + 2, 3)
        px.line(0, self.ground_y + 3, self.width, self.ground_y + 3, 5)

        # 地面の下の土のテクスチャ
        ground_depth = self.height - self.ground_y
        for x in range(0, self.width, 8):
            for dy in range(4, ground_depth, 3):
                if (x + dy) % 16 < 8:
                    px.pset(x + 4, self.ground_y + dy, 5)
                if (x * 7 + dy * 3) % 30 < 2:
                    px.pset(x + 2, self.ground_y + dy, 13)
                if dy > ground_depth // 2 and (x + dy) % 20 < 5:
                    px.pset(x, self.ground_y + dy, 1)

    def _draw_obstacles(self, px) -> None:
        """障害物を描画する（グラデーション、影付き）"""
        for obstacle in self.obstacles:
            ox = int(obstacle.x)
            oy = int(obstacle.y)

            # グラデーション塗りつぶし
            for dy in range(obstacle.h):
                ratio = dy / max(obstacle.h, 1)
                if ratio < 0.3:
                    color = 12
                elif ratio < 0.7:
                    color = 5
                else:
                    color = 1
                px.line(ox, oy + dy, ox + obstacle.w - 1, oy + dy, color)

            # 輪郭
            px.rectb(ox, oy, obstacle.w, obstacle.h, 0)

            # ハイライト
            if obstacle.w > 5 and obstacle.h > 5:
                px.line(ox + 2, oy + 2, ox + obstacle.w - 3, oy + 2, 7)
                px.pset(ox + 2, oy + 3, 7)
                px.pset(ox + 3, oy + 2, 7)
                if obstacle.w > 10:
                    px.pset(ox + obstacle.w - 4, oy + 4, 12)
                    px.pset(ox + obstacle.w - 5, oy + 5, 12)

            # 影
            shadow_length = 2
            for i in range(shadow_length):
                px.line(
                    ox - i,
                    oy + obstacle.h + i,
                    ox + obstacle.w - i,
                    oy + obstacle.h + i,
                    0,
                )

    def _draw_player(self, px) -> None:
        """プレイヤーを描画する"""
        left = int(self.px - self.player_w // 2)
        top = int(self.py - self.player_h)

        if self.player_image_loaded:
            # 画像がある場合
            px.blt(
                left,
                top,
                self.player_image_bank,
                0,
                0,
                self.player_w,
                self.player_h,
                0,
            )
            if not self.on_ground:
                self._draw_jump_aura(px)
        else:
            # フォールバック描画
            px.rect(left, top, self.player_w, self.player_h, 11)
            px.pset(left + 12, top + 15, 1)
            px.pset(left + 28, top + 15, 1)

    def _draw_jump_aura(self, px) -> None:
        """ジャンプ時のオーラ効果を描画する"""
        color = 12 if self.frames % 4 < 2 else 7
        radius_x = self.player_w // 2 + 3
        radius_y = self.player_h // 2 + 3
        center_x = self.px
        center_y = self.py - self.player_h // 2
        for angle_deg in range(0, 360, 45):
            angle = math.radians(angle_deg + self.frames * 10)
            aura_x = int(center_x + math.cos(angle) * radius_x)
            aura_y = int(center_y + math.sin(angle) * radius_y)
            px.pset(aura_x, aura_y, color)

    def _draw_ui(self, px) -> None:
        """スコアとゲームオーバー画面を描画する"""
        # スコア表示（影付き）
        px.text(5, 5, f"SCORE: {self.score}", 0)
        px.text(4, 4, f"SCORE: {self.score}", 7)

        # ベストスコア表示
        if self.best:
            px.text(93, 5, f"BEST: {self.best}", 0)
            px.text(92, 4, f"BEST: {self.best}", 12)

        if self.game_over:
            self._draw_game_over_overlay(px)

    def _draw_game_over_overlay(self, px) -> None:
        box_w = 180
        box_h = 50
        box_x = self.width // 2 - box_w // 2
        box_y = self.height // 2 - box_h // 2

        px.rect(box_x, box_y, box_w, box_h, 1)
        px.rectb(box_x, box_y, box_w, box_h, 12)

        msg = "GAME OVER"
        sub = "Open mouth to retry"

        msg_width = len(msg) * 4
        msg_x = self.width // 2 - msg_width // 2
        msg_y = self.height // 2 - 12
        px.text(msg_x + 1, msg_y + 1, msg, 0)
        px.text(msg_x, msg_y, msg, 10)

        sub_width = len(sub) * 4
        sub_x = self.width // 2 - sub_width // 2
        px.text(sub_x + 1, msg_y + 11, sub, 0)
        px.text(sub_x, msg_y + 10, sub, 12)


GAME_CLASS = RunnerGame

