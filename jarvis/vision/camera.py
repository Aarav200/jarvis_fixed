"""
vision/camera.py — Camera capture module.

Features:
  • Auto-detects available cameras
  • Supports switching between built-in and external
  • Interval-based background capture (10s default)
  • On-demand capture
  • Continuous mode for when webcam arrives
"""

import threading
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from utils.logger import get_logger

log = get_logger(__name__)


class Camera:
    """
    Manages camera capture with auto-detection and mode switching.

    Modes:
      - interval: capture every N seconds (default 10s, for built-in)
      - continuous: capture as fast as possible (for external webcam)
      - on_demand: only capture when explicitly asked
    """

    def __init__(
        self,
        camera_index: int = -1,       # -1 = auto-detect
        interval: float = 1.0,       # seconds between captures
        mode: str = "interval",       # interval | continuous | on_demand
    ) -> None:
        self._index = camera_index
        self._interval = interval
        self._mode = mode
        self._cap: Optional[cv2.VideoCapture] = None
        self._latest_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._capture_thread: Optional[threading.Thread] = None
        self._on_frame_callbacks: list = []

        # Auto-detect camera if index is -1
        if self._index == -1:
            self._index = self._auto_detect()

        log.info("Camera initialized on index %d, mode=%s, interval=%.1fs",
                 self._index, self._mode, self._interval)

    # ── Public API ─────────────────────────────────────────────────────────────

    def start(self) -> bool:
        """Open camera and start capture thread."""
        self._cap = cv2.VideoCapture(self._index)
        if not self._cap.isOpened():
            log.error("Could not open camera index %d", self._index)
            return False

        # Set reasonable resolution
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        self._stop_event.clear()
        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            daemon=True,
            name="jarvis-camera"
        )
        self._capture_thread.start()
        log.info("Camera started.")
        return True

    def stop(self) -> None:
        """Stop capture and release camera."""
        self._stop_event.set()
        if self._capture_thread:
            self._capture_thread.join(timeout=3)
        if self._cap:
            self._cap.release()
        log.info("Camera stopped.")

    def capture_now(self) -> Optional[np.ndarray]:
        """Capture a single frame immediately (on-demand)."""
        if not self._cap or not self._cap.isOpened():
            log.warning("Camera not open — cannot capture.")
            return None
        ret, frame = self._cap.read()
        if ret:
            with self._frame_lock:
                self._latest_frame = frame
            self._notify_callbacks(frame)
            return frame
        return None

    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Return the most recently captured frame."""
        with self._frame_lock:
            return self._latest_frame.copy() if self._latest_frame is not None else None

    def set_mode(self, mode: str, interval: float = None) -> None:
        """
        Switch capture mode at runtime.
        Call this when external webcam arrives:
            camera.set_mode("continuous")
        """
        self._mode = mode
        if interval is not None:
            self._interval = interval
        log.info("Camera mode switched to '%s'", mode)

    def on_frame(self, callback) -> None:
        """Register a callback that receives each new frame."""
        self._on_frame_callbacks.append(callback)

    def switch_camera(self, index: int) -> bool:
        """Hot-switch to a different camera (e.g. built-in → external)."""
        log.info("Switching camera from index %d to %d", self._index, index)
        self.stop()
        self._index = index
        return self.start()

    def save_frame(self, frame: np.ndarray, path: Path) -> None:
        """Save a frame to disk (for debugging or training data)."""
        cv2.imwrite(str(path), frame)

    # ── Private ────────────────────────────────────────────────────────────────

    def _auto_detect(self) -> int:
        """Try camera indices 0, 1, 2 and return the first that opens."""
        for idx in range(3):
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                cap.release()
                log.info("Auto-detected camera at index %d", idx)
                return idx
        log.warning("No camera found — defaulting to index 0")
        return 0

    def _capture_loop(self) -> None:
        while not self._stop_event.is_set():
            if self._mode == "on_demand":
                time.sleep(0.5)
                continue

            ret, frame = self._cap.read()
            if ret:
                with self._frame_lock:
                    self._latest_frame = frame
                self._notify_callbacks(frame)

            if self._mode == "interval":
                # Sleep in small chunks so we can respond to stop quickly
                for _ in range(int(self._interval * 0.1)):
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.1)
            elif self._mode == "continuous":
                time.sleep(0.033)  # ~30 FPS

    def _notify_callbacks(self, frame: np.ndarray) -> None:
        for cb in self._on_frame_callbacks:
            try:
                cb(frame)
            except Exception as e:
                log.debug("Frame callback error: %s", e)
