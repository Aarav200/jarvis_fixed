"""
vision/context.py — Combines camera + detection + activity into rich context.

This is the main orchestrator of the vision system.
It runs in a background thread and maintains current visual state.
Brain module reads from this to inject context into LLM prompts.
"""

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from utils.logger import get_logger
from vision.camera import Camera
from vision.detector import Detector, DetectionResult
from vision.activity import ActivityClassifier, ActivityResult

# Optional modules
HandDetector = None
FaceRecognizer = None

try:
    from vision.hand_detector import HandDetector as _HD
    HandDetector = _HD
except Exception:
    pass

try:
    from vision.face_recognition_mp import FaceRecognizer as _FR
    FaceRecognizer = _FR
except Exception:
    pass

log = get_logger(__name__)

BEHAVIOR_LOG_FILE = Path(__file__).parent.parent / "memory" / "vision_behavior.json"


@dataclass
class VisualState:
    """Complete snapshot of what Jarvis currently sees."""
    activity: str = "unknown"
    activity_confidence: float = 0.0
    activity_context: str = ""
    objects_present: list = field(default_factory=list)
    person_present: bool = False
    unknown_objects: list = field(default_factory=list)
    last_updated: float = 0.0
    camera_active: bool = False
    faces_detected: list = field(default_factory=list)   # [{name, is_owner, bbox}]
    owner_present: bool = False
    strangers_present: bool = False
    hands_detected: bool = False
    hand_objects: list = field(default_factory=list)

    def to_prompt_context(self) -> str:
        """Format visual state for LLM prompt injection."""
        if not self.camera_active:
            return ""

        hour = int(time.strftime("%H"))
        if 5 <= hour < 12:
            time_of_day = "morning"
        elif 12 <= hour < 17:
            time_of_day = "afternoon"
        elif 17 <= hour < 21:
            time_of_day = "evening"
        else:
            time_of_day = "night"

        parts = [f"It is currently {time_of_day}."]

        if self.person_present:
            if self.activity != "unknown":
                parts.append(
                    f"The user appears to be {self.activity} "
                    f"(confidence: {self.activity_confidence:.0%})."
                )
        else:
            parts.append("The user does not appear to be at their desk.")

        if self.objects_present:
            items = [o for o in self.objects_present if o != "person"]
            if items:
                parts.append(f"Visible objects: {', '.join(set(items))}.")

        if self.faces_detected:
            known = [f["name"] for f in self.faces_detected if f["is_known"] and not f["is_owner"]]
            strangers = sum(1 for f in self.faces_detected if not f["is_known"])
            if known:
                parts.append(f"Known people present: {', '.join(known)}.")
            if strangers:
                parts.append(f"There are {strangers} unrecognized people visible.")

        return " ".join(parts)

    def to_dict(self) -> dict:
        return {
            "activity": self.activity,
            "confidence": self.activity_confidence,
            "objects": self.objects_present,
            "person_present": self.person_present,
            "time": time.strftime("%H:%M"),
        }


class VisionContext:
    """
    Main vision orchestrator.

    Usage:
        vision = VisionContext()
        vision.start()
        state = vision.get_state()
        vision.stop()
    """

    def __init__(
        self,
        interval: float = 10.0,
        mode: str = "interval",
        on_unknown_object=None,   # callback(object_name) when unknown seen
    ) -> None:
        self._camera = Camera(interval=interval, mode=mode)
        self._detector = Detector()
        self._classifier = ActivityClassifier()
        self._hand_detector = HandDetector() if HandDetector is not None else None
        self._face_recognizer = FaceRecognizer() if FaceRecognizer is not None else None
        log.info("Hand detection: %s", "enabled" if self._hand_detector else "disabled")
        log.info("Face recognition: %s", "enabled" if self._face_recognizer else "disabled")
        self._state = VisualState()
        self._state_lock = threading.Lock()
        self._on_unknown_object = on_unknown_object
        self._on_stranger = None   # callback when unknown person appears
        self._behavior_log: list = []
        self._running = False
        self._last_stranger_alert = 0

        # Register frame callback
        self._camera.on_frame(self._on_frame)

    # ── Public API ─────────────────────────────────────────────────────────────

    def start(self) -> bool:
        """Start vision system."""
        success = self._camera.start()
        if success:
            self._running = True
            with self._state_lock:
                self._state.camera_active = True
            log.info("Vision context started.")
        else:
            log.error("Failed to start vision system.")
        return success

    def stop(self) -> None:
        """Stop vision system."""
        self._running = False
        self._camera.stop()
        with self._state_lock:
            self._state.camera_active = False
        self._save_behavior_log()
        log.info("Vision context stopped.")

    def get_state(self) -> VisualState:
        """Get current visual state (thread-safe)."""
        with self._state_lock:
            return self._state

    def capture_now(self) -> Optional[VisualState]:
        """Force an immediate capture and return updated state."""
        frame = self._camera.capture_now()
        if frame is not None:
            self._on_frame(frame)
        return self.get_state()

    def describe_now(self) -> str:
        """
        Capture and describe what Jarvis sees right now.
        Used for "Hey Jarvis, what do you see?"
        """
        state = self.capture_now()
        if not state or not state.camera_active:
            return "My camera doesn't seem to be working right now."

        parts = []

        # Face-based greeting (more accurate than person detection)
        if state.owner_present:
            parts.append("I can see you, sir.")
        elif state.person_present:
            if state.faces_detected:
                known = [f["name"] for f in state.faces_detected if f["is_known"] and not f["is_owner"]]
                if known:
                    parts.append(f"I can see {', '.join(known)}.")
                else:
                    parts.append("I can see someone but I don't recognize them.")
            else:
                parts.append("I can see someone.")

        if not state.person_present and not state.owner_present:
            parts.append("I don't see anyone right now.")

        # Activity
        if state.activity not in ("unknown", "present") and state.activity_confidence > 0.5:
            parts.append(state.activity_context)

        # Objects — only high confidence ones
        items = [o for o in set(state.objects_present) if o != "person"]
        if items:
            parts.append(f"I can also see: {', '.join(items)}.")

        return " ".join(parts) if parts else "I'm not sure what I'm seeing."

    def learn_object(self, name: str, description: str = "") -> None:
        """Teach Jarvis about an unknown object."""
        self._detector.learn_object(name, description)
        log.info("Vision learned: '%s'", name)

    def set_stranger_callback(self, cb) -> None:
        """Set callback for when an unknown person appears."""
        self._on_stranger = cb

    def learn_current_face(self, name: str) -> bool:
        """Learn the face currently visible in camera."""
        if not self._face_recognizer:
            return False
        frame = self._camera.capture_now()
        if frame is None:
            return False
        return self._face_recognizer.learn_face(frame, name)

    def set_mode(self, mode: str, interval: float = None) -> None:
        """Switch camera mode (e.g. to 'continuous' for external webcam)."""
        self._camera.set_mode(mode, interval)

    def switch_to_external_camera(self, index: int = 1) -> bool:
        """Switch to external webcam and enable continuous mode."""
        log.info("Switching to external camera index %d", index)
        self._camera.set_mode("continuous")
        return self._camera.switch_camera(index)

    def get_prompt_context(self) -> str:
        """Get visual context string for LLM prompt injection."""
        return self.get_state().to_prompt_context()

    # ── Private ────────────────────────────────────────────────────────────────

    def _on_frame(self, frame: np.ndarray) -> None:
        """Called for every captured frame."""
        try:
            # Detect objects
            detection: DetectionResult = self._detector.detect(frame)

            # Apply user-taught label overrides BEFORE activity classification
            corrected_labels = self._detector.apply_overrides(detection.labels)

            # Classify activity
            activity: ActivityResult = self._classifier.classify(corrected_labels)

            # Detect faces
            if self._face_recognizer:
                faces = self._face_recognizer.recognize(frame)
            else:
                faces = []
            owner_present = any(f["is_owner"] for f in faces)
            strangers = [f for f in faces if not f["is_known"]]

            # Detect hands + what's being held
            hand_objects = []
            if self._hand_detector:
                hand_result = self._hand_detector.detect(frame)
                if hand_result["hands_detected"]:
                    hand_crop = self._hand_detector.get_hand_crop(frame)
                    if hand_crop is not None and hand_crop.size > 0:
                        hand_det = self._detector.detect(hand_crop)
                        hand_objects = [l for l in hand_det.labels if l != "person"]
            else:
                hand_result = {"hands_detected": False, "hand_regions": []}

            # Update state
            with self._state_lock:
                self._state.objects_present = corrected_labels
                self._state.person_present = detection.has_person or owner_present
                self._state.activity = activity.activity
                self._state.activity_confidence = activity.confidence
                self._state.activity_context = activity.context
                self._state.last_updated = time.time()
                self._state.unknown_objects = []
                self._state.faces_detected = faces
                self._state.owner_present = owner_present
                self._state.strangers_present = len(strangers) > 0
                self._state.hands_detected = hand_result.get("hands_detected", False)
                self._state.hand_objects = hand_objects

            # Check for unknown detections
            for d in detection.unknown_detections:
                if self._detector.should_ask_about(d):
                    with self._state_lock:
                        self._state.unknown_objects.append(d.label)
                    if self._on_unknown_object:
                        self._on_unknown_object(d.label)

            # Alert about strangers (cooldown 120s)
            # Only alert if owner is NOT detected (avoid false stranger alerts)
            if strangers and self._on_stranger and not owner_present:
                now = time.time()
                if now - self._last_stranger_alert > 120:
                    self._last_stranger_alert = now
                    self._on_stranger(len(strangers))

            # Log behavior
            self._log_behavior(activity)

        except Exception as e:
            log.error("Vision frame processing error: %s", e, exc_info=True)

    def _log_behavior(self, activity: ActivityResult) -> None:
        """Store activity in behavior log for pattern analysis."""
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "hour": int(time.strftime("%H")),
            **activity.to_dict(),
        }
        self._behavior_log.append(entry)

        # Keep only last 1000 entries in memory
        if len(self._behavior_log) > 1000:
            self._behavior_log = self._behavior_log[-1000:]

        # Save every 50 entries
        if len(self._behavior_log) % 50 == 0:
            self._save_behavior_log()

    def _save_behavior_log(self) -> None:
        try:
            BEHAVIOR_LOG_FILE.parent.mkdir(exist_ok=True)
            BEHAVIOR_LOG_FILE.write_text(
                json.dumps(self._behavior_log[-500:], indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            log.debug("Could not save behavior log: %s", e)
