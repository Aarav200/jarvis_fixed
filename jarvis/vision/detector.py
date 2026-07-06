"""
vision/detector.py — Object detection using YOLO + personal learned objects.

Features:
  • YOLOv8 nano (fast, lightweight) for standard objects
  • Personal learned objects dictionary (memory/learned_objects.json)
  • Unknown object detection → triggers "may I ask what that is?"
  • Confidence thresholding
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from utils.logger import get_logger

log = get_logger(__name__)

# Path to personal learned objects
LEARNED_OBJECTS_FILE = Path(__file__).parent.parent / "memory" / "learned_objects.json"

# Confidence threshold below which we ask the user
UNKNOWN_THRESHOLD = 0.45
# How long to wait before asking about the same unknown object again (seconds)
UNKNOWN_COOLDOWN = 60


@dataclass
class Detection:
    label: str
    confidence: float
    bbox: tuple          # (x1, y1, x2, y2)
    is_known: bool = True
    is_learned: bool = False   # True if from personal dictionary


@dataclass
class DetectionResult:
    detections: list[Detection] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    frame_shape: tuple = (480, 640, 3)

    @property
    def labels(self) -> list[str]:
        return [d.label for d in self.detections]

    @property
    def has_person(self) -> bool:
        return "person" in self.labels

    @property
    def unknown_detections(self) -> list[Detection]:
        return [d for d in self.detections if not d.is_known]


class Detector:
    """
    Multi-layer object detector:
    1. YOLOv8 nano for standard COCO objects
    2. Personal learned objects for custom items
    3. Unknown object flagging with cooldown
    """

    def __init__(self) -> None:
        self._model = None
        self._learned: dict = {}
        self._unknown_cooldowns: dict = {}   # label_hash -> last_asked_time
        self._load_model()
        self._load_learned_objects()

    # ── Public API ─────────────────────────────────────────────────────────────

    def detect(self, frame: np.ndarray) -> DetectionResult:
        """Run detection on a frame and return structured results."""
        result = DetectionResult(frame_shape=frame.shape)

        if self._model is None:
            return result

        try:
            yolo_results = self._model(frame, verbose=False, conf=0.65)
            for r in yolo_results:
                for box in r.boxes:
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    label = self._model.names[cls_id]
                    x1, y1, x2, y2 = map(int, box.xyxy[0])

                    detection = Detection(
                        label=label,
                        confidence=conf,
                        bbox=(x1, y1, x2, y2),
                        is_known=True,
                        is_learned=False,
                    )
                    result.detections.append(detection)

        except Exception as e:
            log.error("YOLO detection error: %s", e)

        # Also check learned objects (simple color/shape matching placeholder)
        # In Phase 2 we'll add embedding-based matching
        result.detections.extend(self._check_learned_objects(frame))

        return result

    def learn_object(self, name: str, description: str = "",
                     yolo_label: str = "") -> None:
        """
        Store a new learned object by name.
        yolo_label: what YOLO incorrectly called it (e.g. "cell phone")
        name: what it actually is (e.g. "mouse")
        """
        entry = {
            "name": name,
            "description": description,
            "learned_at": time.time(),
            "times_seen": 1,
        }
        # Store by actual name
        self._learned[name.lower()] = entry

        # Also store YOLO override — when YOLO says yolo_label, replace with name
        if yolo_label:
            override_key = f"__override__{yolo_label.lower()}"
            self._learned[override_key] = {
                "name": name,
                "replaces": yolo_label,
                "learned_at": time.time(),
            }
            log.info("YOLO override: '%s' -> '%s'", yolo_label, name)

        self._save_learned_objects()
        log.info("Learned new object: '%s'", name)

    def apply_overrides(self, labels: list[str]) -> list[str]:
        """
        Apply user-taught overrides to YOLO labels.
        e.g. "cell phone" -> "mouse" if user taught that.
        """
        result = []
        for label in labels:
            override_key = f"__override__{label.lower()}"
            if override_key in self._learned:
                new_name = self._learned[override_key]["name"]
                log.debug("Override applied: '%s' -> '%s'", label, new_name)
                result.append(new_name)
            else:
                result.append(label)
        return result

    def should_ask_about(self, detection: Detection) -> bool:
        """
        Return True if Jarvis should ask the user about this detection.
        Uses cooldown to avoid repeated questions.
        """
        key = detection.label.lower()
        last_asked = self._unknown_cooldowns.get(key, 0)
        if time.time() - last_asked > UNKNOWN_COOLDOWN:
            self._unknown_cooldowns[key] = time.time()
            return True
        return False

    def get_learned_objects(self) -> dict:
        return self._learned.copy()

    def describe_scene(self, result: DetectionResult) -> str:
        """Generate a natural language description of what's detected."""
        if not result.detections:
            return "I don't see anything clearly identifiable."

        items = {}
        for d in result.detections:
            items[d.label] = items.get(d.label, 0) + 1

        parts = []
        for label, count in items.items():
            if count > 1:
                parts.append(f"{count} {label}s")
            else:
                parts.append(f"a {label}")

        if len(parts) == 1:
            return f"I can see {parts[0]}."
        elif len(parts) == 2:
            return f"I can see {parts[0]} and {parts[1]}."
        else:
            return f"I can see {', '.join(parts[:-1])}, and {parts[-1]}."

    # ── Private ────────────────────────────────────────────────────────────────

    def _load_model(self) -> None:
        try:
            from ultralytics import YOLO
            log.info("Loading YOLOv8 nano model...")
            self._model = YOLO("yolov8n.pt")  # Downloads automatically first time
            log.info("YOLO model loaded.")
        except Exception as e:
            log.error("Could not load YOLO model: %s", e)
            self._model = None

    def _load_learned_objects(self) -> None:
        LEARNED_OBJECTS_FILE.parent.mkdir(exist_ok=True)
        if LEARNED_OBJECTS_FILE.exists():
            try:
                self._learned = json.loads(
                    LEARNED_OBJECTS_FILE.read_text(encoding="utf-8")
                )
                log.info("Loaded %d learned objects.", len(self._learned))
            except Exception:
                self._learned = {}

    def _save_learned_objects(self) -> None:
        LEARNED_OBJECTS_FILE.write_text(
            json.dumps(self._learned, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def _check_learned_objects(self, frame: np.ndarray) -> list[Detection]:
        """
        Placeholder for learned object matching.
        Phase 2 will use image embeddings (CLIP) for visual similarity.
        For now returns empty — learned objects are name-based from user input.
        """
        return []
