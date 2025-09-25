from __future__ import annotations

import os
import threading
import time
from queue import Queue
from typing import Any, Optional, Tuple, Dict

import cv2

from ..events import Action, InputEvent

class FaceProvider:
    """
    - まばたき -> ACTION1 (Space)
    - 口の開き具合 -> ACTION2 (Enter)
    - 笑顔 -> ACTION3 (Shift)
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
        fps: int | None = 15,
        buffersize: int = 1,
        use_mjpeg: bool = True,
        hysteresis: float = 0.05,  # ON/OFFの二段閾値（0で無効）
        smile_threshold: float = 0.5,
        delegate: str | None = None,  # 'CPU' or 'GPU' を指定可能（Noneでデフォルト）
    ) -> None:

        # 閾値（ヒステリシス対応）
        self._blink_on = float(blink_threshold)
        self._blink_off = float(max(0.0, blink_threshold - hysteresis))
        self._mouth_on = float(mouth_threshold)
        self._mouth_off = float(max(0.0, mouth_threshold - hysteresis))
        self._last_blink_active = False
        self._last_mouth_active = False
        self._smile_on = float(smile_threshold)
        self._smile_off = float(max(0.0, smile_threshold - hysteresis))
        self._last_smile_active = False

        # カメラ初期化（軽量化のためFPS/バッファ等を設定）
        self._cap = cv2.VideoCapture(camera_index)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open camera index {camera_index}.")
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, frame_width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, frame_height)
        if fps is not None:
            try:
                self._cap.set(cv2.CAP_PROP_FPS, int(fps))
            except Exception:
                pass
        try:
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, int(buffersize))
        except Exception:
            pass
        if use_mjpeg:
            try:
                fourcc = cv2.VideoWriter_fourcc(*"MJPG")
                self._cap.set(cv2.CAP_PROP_FOURCC, fourcc)
            except Exception:
                pass

        self._frame_skip = max(0, int(frame_skip))
        self._skip_stride = self._frame_skip + 1
        self._time_base = time.monotonic()
        self._result_lock = threading.Lock()
        # 最新のblendshape辞書とタイムスタンプのみ保持
        self._latest_result: Optional[Tuple[Optional[Dict[str, float]], int]] = None
        self._last_processed_ts: int = -1
        self._running = False
        self._worker: Optional[threading.Thread] = None

        # MediaPipe関連は遅延初期化
        self._detector = None  # type: ignore[assignment]
        self._mp_image_cls = None  # type: ignore[assignment]
        self._mp_format = None  # type: ignore[assignment]

        # モデルパスは保持
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self._model_path = os.path.join(base_dir, "assets/models", "face_landmarker.task")
        self._delegate = delegate

    def start(self, _out_queue: Queue | None = None) -> None:
        if self._running:
            return

        # 遅延インポートとFaceLandmarker初期化
        if self._detector is None:
            try:
                import mediapipe as mp  # type: ignore
                from mediapipe.tasks import python  # type: ignore
                from mediapipe.tasks.python import vision  # type: ignore
            except Exception as e:
                raise RuntimeError(f"Failed to import MediaPipe: {e}") from e

            base_opts_kwargs: dict[str, Any] = {"model_asset_path": self._model_path}
            if self._delegate:
                # 'CPU' or 'GPU' を想定（未知の値は無視）
                try:
                    if self._delegate.upper() == "CPU":
                        base_opts_kwargs["delegate"] = python.BaseOptions.Delegate.CPU
                    elif self._delegate.upper() == "GPU":
                        base_opts_kwargs["delegate"] = python.BaseOptions.Delegate.GPU
                except Exception:
                    pass

            options = vision.FaceLandmarkerOptions(
                base_options=python.BaseOptions(**base_opts_kwargs),
                output_face_blendshapes=True,
                num_faces=1,
                running_mode=vision.RunningMode.LIVE_STREAM,
                result_callback=self._on_async_result,
            )
            self._detector = vision.FaceLandmarker.create_from_options(options)

            self._mp_image_cls = mp.Image
            self._mp_format = mp.ImageFormat.SRGB

        self._running = True
        self._worker = threading.Thread(target=self._run_worker, name="FaceProviderWorker", daemon=True)
        self._worker.start()

    def stop(self) -> None:
        self._running = False
        worker = self._worker
        if worker and worker.is_alive():
            worker.join(timeout=1.0)
        self._worker = None

        # Detector/Cameraの明示的クローズ
        try:
            if self._detector is not None:
                # type: ignore[union-attr]
                self._detector.close()
        except Exception:
            pass
        try:
            if hasattr(self, "_cap") and self._cap is not None:
                self._cap.release()
        except Exception:
            pass

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
                # type: ignore[union-attr]
                self._detector.detect_async(mp_image, timestamp_ms)
            except RuntimeError:
                time.sleep(0.01)
                continue

    def _consume_latest_result(self) -> Optional[Tuple[Optional[Dict[str, float]], int]]:
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
        # Escキー
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

        shapes, _ = payload
        if shapes is None:
            self._last_blink_active = False
            self._last_mouth_active = False
            self._last_smile_active = False
            return

        blink = self._compute_blink(shapes)
        mouth_open = self._compute_mouth_openness(shapes)
        smile = self._compute_smile(shapes)

        if blink is not None:
            if not self._last_blink_active:
                blink_active = blink >= self._blink_on
            else:
                blink_active = blink >= self._blink_off
            if blink_active and not self._last_blink_active:
                out_queue.put(InputEvent(action=Action.ACTION1))
            self._last_blink_active = blink_active

        if mouth_open is not None:
            if not self._last_mouth_active:
                mouth_active = mouth_open >= self._mouth_on
            else:
                mouth_active = mouth_open >= self._mouth_off
            if mouth_active and not self._last_mouth_active:
                out_queue.put(InputEvent(action=Action.ACTION2))
            self._last_mouth_active = mouth_active

        if smile is not None:
            if not self._last_smile_active:
                smile_active = smile >= self._smile_on
            else:
                smile_active = smile >= self._smile_off
            if smile_active and not self._last_smile_active:
                out_queue.put(InputEvent(action=Action.ACTION3))
            self._last_smile_active = smile_active

    def _on_async_result(self, result: Any, _output_image: Any, timestamp_ms: int) -> None:
        # コールバック側でblendshape配列を辞書化して前処理
        shapes: Optional[Dict[str, float]] = None
        try:
            blends = getattr(result, "face_blendshapes", None)
            if blends and isinstance(blends, list) and len(blends) > 0:
                items = blends[0]
                if isinstance(items, list):
                    tmp: Dict[str, float] = {}
                    for c in items:
                        cname = getattr(c, "category_name", None)
                        score = getattr(c, "score", None)
                        if cname and (score is not None):
                            tmp[str(cname).lower()] = float(score)
                    shapes = tmp
        except Exception:
            shapes = None
        finally:
            with self._result_lock:
                self._latest_result = (shapes, timestamp_ms)

    def _get_blendshape(self, shapes: Dict[str, float], name: str) -> Optional[float]:
        return shapes.get(name.lower()) if shapes is not None else None

    def _compute_blink(self, shapes: Dict[str, float]) -> Optional[float]:
        # eyeBlink で判定
        left_blink = self._get_blendshape(shapes, "eyeBlinkLeft")
        right_blink = self._get_blendshape(shapes, "eyeBlinkRight")
        blink_avg = None
        if left_blink is not None and right_blink is not None:
            blink_avg = float((left_blink + right_blink) / 2.0)

        # eyeSquint でも判定
        left_squint = self._get_blendshape(shapes, "eyeSquintLeft")
        right_squint = self._get_blendshape(shapes, "eyeSquintRight")
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

    def _compute_mouth_openness(self, shapes: Dict[str, float]) -> Optional[float]:
        # jawOpen or (1 - mouthClose) で判定
        jo = self._get_blendshape(shapes, "jawOpen")
        if jo is None:
            mc = self._get_blendshape(shapes, "mouthClose")
            if mc is not None:
                jo = float(1.0 - mc)
        if jo is not None:
            return float(jo)
        return None

    def _compute_smile(self, shapes: Dict[str, float]) -> Optional[float]:
        # mouthSmileLeft/Right を平均。両方無い場合は mouthCornerPullLeft/Right をフォールバック
        l = self._get_blendshape(shapes, "mouthSmileLeft")
        r = self._get_blendshape(shapes, "mouthSmileRight")
        val = None
        if l is not None and r is not None:
            val = float((l + r) / 2.0)
        if val is None:
            l2 = self._get_blendshape(shapes, "mouthCornerPullLeft")
            r2 = self._get_blendshape(shapes, "mouthCornerPullRight")
            if l2 is not None and r2 is not None:
                val = float((l2 + r2) / 2.0)
        return val

    def __del__(self) -> None:
        try:
            self.stop()
        except Exception:
            pass
