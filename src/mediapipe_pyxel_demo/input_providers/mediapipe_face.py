from __future__ import annotations

import os
import threading
import time
from queue import Queue
from typing import Any, Optional, Tuple

import cv2

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
        blink_threshold: float = 0.5,
        mouth_threshold: float = 0.3,
        frame_width: int = 80,
        frame_height: int = 60,
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
        self._frame_skip = max(0, int(frame_skip))
        self._skip_stride = self._frame_skip + 1
        self._time_base = time.monotonic()
        self._result_lock = threading.Lock()
        self._latest_result: Optional[Tuple[Any, int]] = None
        self._last_processed_ts: int = -1
        self._running = False
        self._worker: Optional[threading.Thread] = None

        # FaceLandmarkerを作成
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        model_path = os.path.join(base_dir, "assets/models", "face_landmarker.task")
        options = vision.FaceLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=model_path),
            output_face_blendshapes=True,
            num_faces=1,
            running_mode=vision.RunningMode.LIVE_STREAM,
            result_callback=self._on_async_result,
        )
        self._detector = vision.FaceLandmarker.create_from_options(options)

        self._mp_image_cls = mp.Image
        self._mp_format = mp.ImageFormat.SRGB

    def start(self, _out_queue: Queue | None = None) -> None:
        if self._running:
            return
        self._running = True
        self._worker = threading.Thread(target=self._run_worker, name="FaceProviderWorker", daemon=True)
        self._worker.start()

    def stop(self) -> None:
        self._running = False
        worker = self._worker
        if worker and worker.is_alive():
            worker.join(timeout=1.0)
        self._worker = None

    def _run_worker(self) -> None:
        skip_counter = 0
        while self._running:
            if self._frame_skip > 0:
                grabbed = self._cap.grab()
                if not grabbed:
                    time.sleep(0.01)
                    continue
                skip_counter = (skip_counter + 1) % self._skip_stride
                if skip_counter != 0:
                    continue
                ok, frame_bgr = self._cap.retrieve()
            else:
                ok, frame_bgr = self._cap.read()
            if not ok or frame_bgr is None:
                time.sleep(0.01)
                continue

            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            mp_image = self._mp_image_cls(image_format=self._mp_format, data=rgb)
            timestamp_ms = int((time.monotonic() - self._time_base) * 1000)

            try:
                self._detector.detect_async(mp_image, timestamp_ms)
            except Exception:
                time.sleep(0.01)
                continue

    def _consume_latest_result(self) -> Optional[Tuple[Any, int]]:
        with self._result_lock:
            latest = self._latest_result
            if not latest:
                return None
            result, ts_ms = latest
            if ts_ms == self._last_processed_ts:
                return None
            self._last_processed_ts = ts_ms
        return result, ts_ms

    def poll(self, px, out_queue: Queue) -> None:  # type: ignore[override]
        # Escキー（仮）
        if px is not None:
            try:
                if px.btnp(px.KEY_ESCAPE):
                    out_queue.put(InputEvent(action=Action.QUIT))
            except Exception:
                pass

        if not self._running:
            self.start()

        payload = self._consume_latest_result()
        if payload is None:
            return

        result, _ = payload
        if result is None:
            self._last_blink_active = False
            self._last_mouth_active = False
            return

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

    def _on_async_result(self, result: Any, _output_image: mp.Image, timestamp_ms: int) -> None:
        with self._result_lock:
            self._latest_result = (result, timestamp_ms)

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
            self.stop()
            if hasattr(self, "_cap") and self._cap is not None:
                self._cap.release()
        except Exception:
            pass
