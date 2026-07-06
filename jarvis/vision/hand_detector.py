"""
vision/hand_detector.py — Hand and held object detection using MediaPipe.

Detects:
  - Hand presence and position
  - What region the hand is in (helps YOLO focus there)
  - Triggers on-demand capture when hand is raised toward camera
"""

import time
import numpy as np
from utils.logger import get_logger

log = get_logger(__name__)


class HandDetector:
    """
    Uses MediaPipe Hands to detect hands and their position.
    When a hand is raised, triggers immediate camera capture
    so YOLO can detect what's being held.
    """

    def __init__(self) -> None:
        self._hands = None
        self._last_detection = 0
        self._hand_region = None
        self._load_model()

    def _load_model(self) -> None:
        try:
            # Try new MediaPipe API first
            import mediapipe as mp
            try:
                # New API (mediapipe >= 0.10)
                from mediapipe.tasks import python as mp_tasks
                from mediapipe.tasks.python import vision as mp_vision
                self._hands = None  # Use legacy fallback
                self._use_legacy = False
                log.info("Hand detector: new MediaPipe API detected, using legacy fallback.")
            except Exception:
                pass

            # Legacy API (mediapipe < 0.10)
            if hasattr(mp, 'solutions') and hasattr(mp.solutions, 'hands'):
                self._mp_hands = mp.solutions.hands
                self._hands = self._mp_hands.Hands(
                    static_image_mode=False,
                    max_num_hands=2,
                    min_detection_confidence=0.6,
                    min_tracking_confidence=0.5,
                )
                self._use_legacy = True
                log.info("Hand detector loaded (legacy API).")
            else:
                self._hands = None
                log.warning("MediaPipe hands not available in this version.")
        except Exception as e:
            log.warning("Could not load hand detector: %s", e)
            self._hands = None

    def detect(self, frame: np.ndarray) -> dict:
        """
        Detect hands in frame.
        Returns dict with hand info.
        """
        if self._hands is None or not getattr(self, "_use_legacy", False):
            return {"hands_detected": False, "hand_regions": []}

        import cv2
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._hands.process(rgb)

        if not results.multi_hand_landmarks:
            return {"hands_detected": False, "hand_regions": []}

        h, w = frame.shape[:2]
        hand_regions = []

        for hand_landmarks in results.multi_hand_landmarks:
            # Get bounding box of hand
            xs = [lm.x for lm in hand_landmarks.landmark]
            ys = [lm.y for lm in hand_landmarks.landmark]

            x1 = max(0, int(min(xs) * w) - 30)
            y1 = max(0, int(min(ys) * h) - 30)
            x2 = min(w, int(max(xs) * w) + 30)
            y2 = min(h, int(max(ys) * h) + 30)

            # Check if hand is raised toward camera (wrist lower than fingers)
            wrist_y = hand_landmarks.landmark[0].y
            middle_tip_y = hand_landmarks.landmark[12].y
            hand_raised = middle_tip_y < wrist_y  # In image coords, smaller y = higher

            hand_regions.append({
                "bbox": (x1, y1, x2 - x1, y2 - y1),
                "raised": hand_raised,
                "center": ((x1 + x2) // 2, (y1 + y2) // 2),
            })

        self._last_detection = time.time()
        return {
            "hands_detected": True,
            "hand_count": len(hand_regions),
            "hand_regions": hand_regions,
        }

    def get_hand_crop(self, frame: np.ndarray) -> "np.ndarray | None":
        """
        Return a cropped region of the frame focused on the hand area.
        Used to help YOLO detect what's being held.
        """
        result = self.detect(frame)
        if not result["hands_detected"]:
            return None

        import cv2
        h, w = frame.shape[:2]
        hand = result["hand_regions"][0]
        x, y, bw, bh = hand["bbox"]

        # Expand crop area to include held object
        padding = 80
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(w, x + bw + padding)
        y2 = min(h, y + bh + padding)

        return frame[y1:y2, x1:x2]

    def draw_hands(self, frame: np.ndarray, hand_result: dict) -> np.ndarray:
        """Draw hand bounding boxes on frame."""
        import cv2
        for hand in hand_result.get("hand_regions", []):
            x, y, w, h = hand["bbox"]
            color = (0, 255, 255) if hand["raised"] else (255, 255, 0)
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            label = "Hand (raised)" if hand["raised"] else "Hand"
            cv2.putText(frame, label, (x, y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        return frame
