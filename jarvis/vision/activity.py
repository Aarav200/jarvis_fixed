"""
vision/activity.py — Activity classification from detected objects.

Maps combinations of detected objects → user activity.
Returns structured activity data for brain injection.
"""

import time
from dataclasses import dataclass
from collections import Counter

from utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class ActivityResult:
    activity: str           # e.g. "coding", "gaming", "resting"
    confidence: float       # 0.0 - 1.0
    context: str            # Human readable description
    objects_seen: list      # What triggered this classification
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "activity": self.activity,
            "confidence": round(self.confidence, 2),
            "context": self.context,
            "objects_seen": self.objects_seen,
        }


# ── Activity rules ─────────────────────────────────────────────────────────────
# Each rule: (required_objects, optional_objects, activity, base_confidence)
# confidence increases with more matched objects

ACTIVITY_RULES = [
    # Coding / working — laptop or keyboard present = working
    {
        "activity": "coding",
        "required": ["laptop"],
        "boost": ["keyboard", "mouse", "monitor", "book", "cell phone"],
        "base_confidence": 0.75,
        "context": "You appear to be working on your laptop.",
    },
    # Also catch desktop setup (no laptop detected but keyboard+mouse visible)
    {
        "activity": "coding",
        "required": ["keyboard"],
        "boost": ["mouse", "monitor", "book"],
        "base_confidence": 0.70,
        "context": "You appear to be working at your desk.",
    },
    # Gaming — MUST have a game controller to count as gaming
    # Monitor alone does NOT mean gaming
    {
        "activity": "gaming",
        "required": ["remote"],   # game controller shows as "remote" in YOLO
        "boost": ["tv", "monitor"],
        "base_confidence": 0.72,
        "context": "Looks like you are gaming.",
    },
    # Phone usage
    {
        "activity": "on phone",
        "required": ["cell phone"],
        "boost": [],
        "base_confidence": 0.75,
        "context": "You're using your phone.",
    },
    # Reading
    {
        "activity": "reading",
        "required": ["book"],
        "boost": ["person"],
        "base_confidence": 0.70,
        "context": "You seem to be reading.",
    },
    # Eating — must have actual food context, not just a bottle nearby
    {
        "activity": "eating",
        "required": ["dining table"],
        "boost": ["cup", "bowl", "bottle", "fork", "spoon", "pizza", "sandwich"],
        "base_confidence": 0.65,
        "context": "Looks like you are having a meal.",
    },
    # Resting / idle — needs couch or bed to confirm, 
    # person alone = just present/unknown
    {
        "activity": "resting",
        "required": ["person"],
        "boost": ["couch", "bed", "pillow", "teddy bear"],
        "base_confidence": 0.35,   # Low confidence — needs boost to trigger
        "context": "You seem to be resting.",
    },
    # Standing / moving — person visible but no desk items
    {
        "activity": "present",
        "required": ["person"],
        "boost": [],
        "base_confidence": 0.40,
        "context": "I can see you.",
    },
    # No one present
    {
        "activity": "away",
        "required": [],
        "boost": [],
        "base_confidence": 0.90,
        "context": "I don't see anyone at the desk.",
        "requires_no_person": True,
    },
]


class ActivityClassifier:
    """
    Classifies user activity from detected objects.
    Maintains a short history to smooth out flickering.
    """

    HISTORY_SIZE = 5   # frames to keep in history

    def __init__(self) -> None:
        self._history: list[ActivityResult] = []
        self._last_activity: str = "unknown"

    def classify(self, detected_labels: list[str]) -> ActivityResult:
        """
        Classify activity from a list of detected object labels.
        Returns the most likely ActivityResult.
        """
        lower_labels = [l.lower() for l in detected_labels]
        has_person = "person" in lower_labels

        best: ActivityResult | None = None
        best_score = 0.0

        for rule in ACTIVITY_RULES:
            # Check "requires_no_person" rules
            if rule.get("requires_no_person") and has_person:
                continue
            if rule.get("requires_no_person") is None and not has_person:
                # Most activities require a person present
                if rule["activity"] != "away":
                    continue

            # Check required objects
            required = rule.get("required", [])
            if required and not all(r in lower_labels for r in required):
                continue

            # Calculate score
            score = rule["base_confidence"]
            boost_objects = rule.get("boost", [])
            matched_boosts = [b for b in boost_objects if b in lower_labels]
            score += len(matched_boosts) * 0.08
            score = min(score, 0.98)

            if score > best_score:
                best_score = score
                best = ActivityResult(
                    activity=rule["activity"],
                    confidence=score,
                    context=rule["context"],
                    objects_seen=lower_labels,
                )

        if best is None:
            best = ActivityResult(
                activity="present",
                confidence=0.40,
                context="I can see you but I'm not sure what you're doing.",
                objects_seen=lower_labels,
            )

        # Add to history and smooth
        self._history.append(best)
        if len(self._history) > self.HISTORY_SIZE:
            self._history.pop(0)

        smoothed = self._smooth_history()
        self._last_activity = smoothed.activity
        return smoothed

    def get_last_activity(self) -> str:
        return self._last_activity

    def _smooth_history(self) -> ActivityResult:
        """Return the most common activity from recent history."""
        if not self._history:
            return ActivityResult(
                activity="unknown",
                confidence=0.0,
                context="No data yet.",
                objects_seen=[],
            )
        # Vote on most common activity
        votes = Counter(r.activity for r in self._history)
        most_common = votes.most_common(1)[0][0]
        # Return the most recent result with that activity
        for r in reversed(self._history):
            if r.activity == most_common:
                return r
        return self._history[-1]
