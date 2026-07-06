"""
vision/visualizer.py — Live camera window showing YOLO detections.

Shows a floating window with:
  • Live camera feed
  • Bounding boxes around detected objects
  • Labels with confidence scores
  • Current activity in corner
  • Toggle with "Hey Jarvis, show camera" / "hide camera"
"""

import threading
import time
from typing import Optional

import cv2
import numpy as np

from utils.logger import get_logger

log = get_logger(__name__)


class VisionVisualizer:
    """
    Floating OpenCV window showing live camera + YOLO detections.
    Runs in its own thread so it doesn't block Jarvis.
    """

    # Color palette for different object classes
    COLORS = [
        (0, 255, 0),    # green
        (255, 100, 0),  # blue
        (0, 100, 255),  # red
        (255, 255, 0),  # cyan
        (255, 0, 255),  # magenta
        (0, 255, 255),  # yellow
        (128, 255, 0),  # lime
        (255, 128, 0),  # orange
    ]

    WINDOW_NAME = "Jarvis Vision"

    def __init__(self, vision_context) -> None:
        self._vision = vision_context
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._show = False

    def start(self) -> None:
        """Start the visualizer in background thread."""
        self._running = True
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="jarvis-visualizer"
        )
        self._thread.start()
        log.info("Vision visualizer started.")

    def stop(self) -> None:
        self._running = False
        cv2.destroyAllWindows()
        log.info("Vision visualizer stopped.")

    def show(self) -> None:
        """Show the camera window."""
        self._show = True
        log.info("Camera window shown.")

    def hide(self) -> None:
        """Hide the camera window."""
        self._show = False
        try:
            cv2.destroyWindow(self.WINDOW_NAME)
        except Exception:
            pass
        log.info("Camera window hidden.")

    def toggle(self) -> bool:
        """Toggle visibility. Returns True if now shown."""
        if self._show:
            self.hide()
            return False
        else:
            self.show()
            return True

    def _loop(self) -> None:
        """Main render loop."""
        while self._running:
            if not self._show:
                time.sleep(0.1)
                continue

            # Get latest frame from camera
            frame = self._vision._camera.get_latest_frame()
            if frame is None:
                # Force a capture
                frame = self._vision._camera.capture_now()
                if frame is None:
                    time.sleep(0.5)
                    continue

            # Get latest detections
            try:
                detection = self._vision._detector.detect(frame.copy())
                annotated = self._draw_detections(frame.copy(), detection)
                # Draw face boxes if available
                if self._vision._face_recognizer:
                    faces = self._vision._face_recognizer.recognize(frame)
                    annotated = self._draw_faces(annotated, faces)
                # Draw hand boxes if available
                if self._vision._hand_detector:
                    hand_result = self._vision._hand_detector.detect(frame)
                    annotated = self._vision._hand_detector.draw_hands(
                        annotated, hand_result
                    )
                annotated = self._draw_overlay(annotated)

                cv2.imshow(self.WINDOW_NAME, annotated)

                # Position window nicely (top right corner)
                cv2.moveWindow(self.WINDOW_NAME, 900, 50)

            except Exception as e:
                log.debug("Visualizer render error: %s", e)
                annotated = frame.copy()
                cv2.imshow(self.WINDOW_NAME, annotated)

            # Press Q to hide
            key = cv2.waitKey(100) & 0xFF
            if key == ord('q') or key == ord('Q'):
                self.hide()

            time.sleep(0.05)  # ~20 FPS max

    def _draw_detections(self, frame: np.ndarray, detection) -> np.ndarray:
        """Draw bounding boxes and labels on frame."""
        for i, det in enumerate(detection.detections):
            color = self.COLORS[i % len(self.COLORS)]
            x1, y1, x2, y2 = det.bbox

            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            # Draw label background
            label = f"{det.label} {det.confidence:.0%}"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.55
            thickness = 1
            (tw, th), _ = cv2.getTextSize(label, font, font_scale, thickness)

            label_y = max(y1 - 5, th + 5)
            cv2.rectangle(frame,
                          (x1, label_y - th - 4),
                          (x1 + tw + 4, label_y + 2),
                          color, -1)

            # Draw label text
            cv2.putText(frame, label,
                        (x1 + 2, label_y - 2),
                        font, font_scale, (0, 0, 0), thickness)

        return frame

    def _draw_faces(self, frame: np.ndarray, faces: list) -> np.ndarray:
        """Draw face recognition boxes."""
        for face in faces:
            x, y, w, h = face["bbox"]
            if face["is_owner"]:
                color = (0, 255, 100)   # Green for owner
                label = "Owner (You)"
            elif face["is_known"]:
                color = (255, 200, 0)   # Blue for known friend
                label = face["name"].capitalize()
            else:
                color = (0, 0, 255)     # Red for stranger
                label = "Unknown"

            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            # Label background
            cv2.rectangle(frame, (x, y - 22), (x + len(label) * 9, y), color, -1)
            cv2.putText(frame, label, (x + 2, y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)
        return frame

    def _draw_overlay(self, frame: np.ndarray) -> np.ndarray:
        """Draw activity overlay and stats in corners."""
        h, w = frame.shape[:2]
        state = self._vision.get_state()

        # Semi-transparent top bar
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 38), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        # Activity text top left
        activity_text = f"Activity: {state.activity} ({state.activity_confidence:.0%})"
        cv2.putText(frame, activity_text,
                    (8, 24), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 255, 100), 1)

        # Time top right
        time_text = time.strftime("%H:%M:%S")
        cv2.putText(frame, time_text,
                    (w - 80, 24), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (200, 200, 200), 1)

        # Object count bottom left
        obj_count = len(detection_set := set(state.objects_present) - {"person"})
        if obj_count:
            items_text = f"Objects: {', '.join(list(detection_set)[:4])}"
            cv2.putText(frame, items_text,
                        (8, h - 10), cv2.FONT_HERSHEY_SIMPLEX,
                        0.45, (180, 180, 180), 1)

        # "Press Q to hide" hint
        cv2.putText(frame, "Press Q to hide",
                    (w - 110, h - 10), cv2.FONT_HERSHEY_SIMPLEX,
                    0.4, (120, 120, 120), 1)

        # Person indicator
        if state.person_present:
            cv2.circle(frame, (w - 16, 52), 7, (0, 255, 0), -1)
        else:
            cv2.circle(frame, (w - 16, 52), 7, (0, 0, 255), -1)

        return frame
