from __future__ import annotations

import os
import cv2
import numpy as np
from queue import Queue
from typing import Optional, Any

from ..events import Action, InputEvent

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

class FaceProvider:
    """
    - まばたき -> ACTION1 (Space)
    - 口の開き具合 -> ACTION2 (Enter)
    - Escキー -> QUIT (Esc)
    """

    def __init__(
        self,
        camera_index: int = 0,
        blink_threshold: float = 0.6,
        mouth_threshold: float = 0.4,
        frame_width: int = 80,
        frame_height: int = 60,
        fps: int = 30,
        frame_skip: int = 0,  # 任意のフレームおきに処理する (0なら全フレーム)
    ) -> None:

        self._blink_threshold = blink_threshold
        self._mouth_threshold = mouth_threshold
        self._last_blink_active = False
        self._last_mouth_active = False

        self._cap = cv2.VideoCapture(camera_index)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open camera index {camera_index}.")
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, frame_width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, frame_height)
        self._cap.set(cv2.CAP_PROP_FPS, fps)
        self._frame_skip = max(0, int(frame_skip))
        self._frame_id = -1
        self._ts_ms = 0

        # FaceLandmarkerを作成
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        model_path = os.path.join(base_dir, "assets/models", "face_landmarker.task")
        options = vision.FaceLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=model_path),
            output_face_blendshapes=True,
            num_faces=1,
            running_mode=vision.RunningMode.VIDEO,
        )
        self._detector = vision.FaceLandmarker.create_from_options(options)

        self._mp_image_cls = mp.Image
        self._mp_format = mp.ImageFormat.SRGB

    def detect_landmarks(self) -> Any:
        image = self._read_frame()
        if image is None:
            return None
        self._ts_ms += 33
        return self._detector.detect_for_video(image, self._ts_ms)

    def poll(self, px, out_queue: Queue) -> None:  # type: ignore[override]
        # Escキー（仮）
        if px is not None:
            try:
                if px.btnp(px.KEY_ESCAPE):
                    out_queue.put(InputEvent(action=Action.QUIT))
            except Exception:
                pass

        self._frame_id += 1
        if self._frame_skip > 0 and (self._frame_id % (self._frame_skip + 1)) != 0:
            _ = self._read_frame()
            return

        result = self.detect_landmarks()
        landmarks = getattr(result, "face_landmarks", None)
        if not landmarks:
            self._last_blink_active = False
            self._last_mouth_active = False
            return

        blink = self._compute_blink(result, landmarks)
        mouth_open = self._compute_mouth_openness(result, landmarks)

        if blink is not None:
            blink_active = blink >= self._blink_threshold
            if blink_active and not self._last_blink_active:
                out_queue.put(InputEvent(action=Action.ACTION1))
            self._last_blink_active = blink_active

        if mouth_open is not None:
            mouth_active = mouth_open >= self._mouth_threshold
            if mouth_active and not self._last_mouth_active:
                out_queue.put(InputEvent(action=Action.ACTION2))
            self._last_mouth_active = mouth_active

    def _read_frame(self) -> Optional[mp.Image]:
        ok, frame_bgr = self._cap.read()
        if not ok or frame_bgr is None:
            return None
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        return self._mp_image_cls(image_format=self._mp_format, data=rgb)

    def _get_blendshape(self, result: Any, name: str) -> Optional[float]:
        try:
            blends = getattr(result, "face_blendshapes", None)
            if not blends:
                return None
            items = blends[0]
            if not isinstance(items, list):
                return None
            target = name.lower()
            for c in items:
                cname = getattr(c, "category_name", None)
                if not cname or cname.lower() != target:
                    continue
                score = getattr(c, "score", None)
                if score is not None:
                    return float(score)
        except Exception:
            pass
        return None

    def _compute_blink(self, result: Any, landmarks: Any) -> Optional[float]:
        # eyeBlinkで判定する
        left_blink = self._get_blendshape(result, "eyeBlinkLeft")
        right_blink = self._get_blendshape(result, "eyeBlinkRight")
        blink_avg = None
        if left_blink is not None and right_blink is not None:
            blink_avg = float((left_blink + right_blink) / 2.0)

        # eyeSquintでも判定する
        left_squint = self._get_blendshape(result, "eyeSquintLeft")
        right_squint = self._get_blendshape(result, "eyeSquintRight")
        squint_avg = None
        if left_squint is not None and right_squint is not None:
            squint_avg = float((left_squint + right_squint) / 2.0)

        if blink_avg is not None and squint_avg is not None:
            return max(blink_avg, squint_avg)
        if blink_avg is not None:
            return blink_avg
        if squint_avg is not None:
            return squint_avg
        return None

    def _compute_mouth_openness(self, result: Any, landmarks: Any) -> Optional[float]:
        # jawOpen or (1 - mouthClose)で判定する
        jo = self._get_blendshape(result, "jawOpen")
        if jo is None:
            mc = self._get_blendshape(result, "mouthClose")
            if mc is not None:
                jo = float(1.0 - mc)
        if jo is not None:
            return float(jo)
        return None

    def __del__(self) -> None:
        try:
            if hasattr(self, "_cap") and self._cap is not None:
                self._cap.release()
        except Exception:
            pass
