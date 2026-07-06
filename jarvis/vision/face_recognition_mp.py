"""
vision/face_recognition_mp.py — Face recognition using deep embeddings + OpenCV.

Uses:
  - OpenCV DNN face detector (more accurate than Haar cascade)
  - 128-d face embeddings via face_recognition lib (dlib deep net) if available,
    falls back to LBPH with better guards if not
  - Cosine similarity matching — much more reliable than LBPH confidence scores
  - Outfit/colour analysis for "what am I wearing" queries

Persons:
  - owner: registered via capture_face.py
  - known: friends taught by voice ("this is Akshay")
  - unknown: anyone not recognized
"""

import json
import time
import threading
import numpy as np
from pathlib import Path
from typing import Optional

import cv2

from utils.logger import get_logger

log = get_logger(__name__)

FACES_DIR       = Path("vision/faces")
KNOWN_PEOPLE_FILE = Path("memory/known_people.json")

# ── Colour name lookup (HSV-based) ────────────────────────────────────────────
COLOUR_RANGES = [
    ("red",     (0,   100, 70),  (10,  255, 255)),
    ("red",     (165, 100, 70),  (180, 255, 255)),
    ("orange",  (10,  100, 100), (18,  255, 255)),
    ("brown",   (8,   60,  30),  (22,  220, 160)),   # key: low V, medium S
    ("brown",   (5,   50,  40),  (20,  180, 130)),   # darker browns
    ("yellow",  (22,  100, 100), (35,  255, 255)),
    ("green",   (35,  50,  40),  (85,  255, 255)),
    ("cyan",    (85,  50,  40),  (100, 255, 255)),
    ("blue",    (100, 50,  40),  (130, 255, 255)),
    ("navy",    (100, 50,  20),  (130, 255, 80)),
    ("purple",  (130, 50,  40),  (160, 255, 255)),
    ("pink",    (145, 30,  150), (175, 150, 255)),   # tightened — less false pink
    ("white",   (0,   0,   180), (180, 40,  255)),
    ("black",   (0,   0,   0),   (180, 255, 45)),
    ("grey",    (0,   0,   46),  (180, 40,  180)),
]


def _dominant_colour(region: np.ndarray) -> str:
    """
    Return dominant colour using HSV histogram voting.
    Works in dim lighting by using CLAHE instead of simple equalisation.
    """
    if region is None or region.size == 0:
        return "unknown"

    # Use center 60% of region to avoid edge artefacts
    h, w = region.shape[:2]
    cy1, cy2 = int(h * 0.2), int(h * 0.8)
    cx1, cx2 = int(w * 0.2), int(w * 0.8)
    center = region[cy1:cy2, cx1:cx2]
    if center.size == 0:
        center = region

    # CLAHE on LAB — much better for dim/side-lit rooms than simple equalise
    lab = cv2.cvtColor(center, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
    l = clahe.apply(l)
    center = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)

    hsv = cv2.cvtColor(center, cv2.COLOR_BGR2HSV)
    total = center.shape[0] * center.shape[1]
    counts = {}
    for name, lo, hi in COLOUR_RANGES:
        mask  = cv2.inRange(hsv, np.array(lo), np.array(hi))
        count = int(cv2.countNonZero(mask))
        counts[name] = counts.get(name, 0) + count

    best_colour = max(counts, key=counts.get) if counts else "unknown"
    best_count  = counts.get(best_colour, 0)

    # Reject weak matches
    if best_count < total * 0.08:
        return "unknown"
    return best_colour


def _shirt_colour(frame: np.ndarray, face_bbox: tuple) -> str:
    """
    Estimate shirt colour by sampling the torso region below the face.
    Uses center strip only to avoid background bleed.
    face_bbox: (x, y, w, h)
    """
    h_frame, w_frame = frame.shape[:2]
    x, y, w, h = face_bbox
    # Center strip of torso — narrow width to stay away from background
    cx = x + w // 2
    strip_w = max(30, w // 3)
    tx1 = max(0, cx - strip_w)
    tx2 = min(w_frame, cx + strip_w)
    # Start below chin, sample a good chunk of chest
    ty1 = min(h_frame, y + h + 10)
    ty2 = min(h_frame, ty1 + int(h * 0.9))
    if ty2 <= ty1 or tx2 <= tx1 or (ty2 - ty1) < 10:
        return "unknown"
    torso = frame[ty1:ty2, tx1:tx2]
    return _dominant_colour(torso)


# ── Embedding backend selection ───────────────────────────────────────────────

_USE_DEEP = False
_fr_lib   = None

try:
    import face_recognition as _fr_lib
    _USE_DEEP = True
    log.info("face_recognition (dlib) available — using deep embeddings.")
except ImportError:
    log.warning("face_recognition not installed — using LBPH fallback. "
                "Install with: pip install face_recognition")


class FaceRecognizer:
    """
    Face recognizer with two backends:
      • Deep (face_recognition/dlib) — 128-d embeddings, cosine similarity
      • LBPH fallback — classic OpenCV, less accurate but no dlib needed

    API is identical regardless of backend.
    """

    # Deep backend: max cosine distance to call someone "known"
    DEEP_THRESHOLD  = 0.45   # lower = stricter. 0.45 is a safe starting point
    # LBPH backend: max confidence (lower = more similar in LBPH)
    LBPH_THRESHOLD  = 85     # tightened from 100 — reduces false positives

    def __init__(self) -> None:
        self._lock          = threading.Lock()
        self._known_people: dict = {}
        # Deep backend state
        self._embeddings: dict[str, list] = {}   # name -> list of 128-d arrays
        # LBPH backend state
        self._recognizer    = None
        self._labels: dict[int, str] = {}
        self._names:  dict[str, int] = {}
        self._trained       = False

        FACES_DIR.mkdir(parents=True, exist_ok=True)
        KNOWN_PEOPLE_FILE.parent.mkdir(exist_ok=True)

        if not _USE_DEEP:
            self._recognizer = cv2.face.LBPHFaceRecognizer_create()
            self._face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )

        self._load_known_people()
        self._train()

    # ── Public API ────────────────────────────────────────────────────────────

    def recognize(self, frame: np.ndarray) -> list[dict]:
        """
        Detect + recognise all faces in frame.
        Returns list of {name, confidence, bbox, is_owner, is_known, shirt_colour}
        """
        if _USE_DEEP:
            return self._recognize_deep(frame)
        else:
            return self._recognize_lbph(frame)

    def learn_face(self, frame: np.ndarray, name: str) -> bool:
        """Learn a new face from frame. Returns True on success."""
        # Safety: ensure frame is valid
        if frame is None or frame.size == 0:
            log.warning("learn_face: empty frame")
            return False

        if _USE_DEEP:
            return self._learn_deep(frame, name)
        else:
            return self._learn_lbph(frame, name)

    # Alias used by VisionContext.learn_current_face → context calls this
    def learn_face_from_frame(self, frame: np.ndarray, name: str) -> tuple[bool, str]:
        ok = self.learn_face(frame, name)
        msg = f"Learned {name}." if ok else "Could not detect a face clearly."
        return ok, msg

    def get_known_people(self) -> list[str]:
        return list(self._known_people.keys())

    def describe_faces(self, faces: list[dict]) -> str:
        if not faces:
            return ""
        owner_present  = any(f["is_owner"] for f in faces)
        known          = [f["name"] for f in faces if f["is_known"] and not f["is_owner"]]
        unknown_count  = sum(1 for f in faces if not f["is_known"])
        parts = []
        if owner_present:
            parts.append("I can see you, sir")
        if known:
            parts.append(f"I can also see {', '.join(known)}")
        if unknown_count:
            word = "someone" if unknown_count == 1 else f"{unknown_count} people"
            parts.append(f"and {word} I don't recognise")
        return ". ".join(parts) + "." if parts else ""

    def describe_outfit(self, frame: np.ndarray, query: str = "") -> str:
        """
        Describe outfit and give context-aware suggestions based on query.
        query: what the user asked (tie, pants, shoes, etc.)
        """
        faces = self.recognize(frame)
        if not faces:
            return "I can't see anyone clearly right now."
        target = next((f for f in faces if f["is_owner"]), faces[0])
        colour = target.get("shirt_colour", "unknown")
        if colour == "unknown":
            return "I can see you but I'm having trouble reading your shirt colour."
        # Outfit suggestions — casual vs formal aware
        casual_suggestions = {
            "red":    ("dark jeans or black chinos", "white, grey, or black"),
            "orange": ("dark blue jeans or olive chinos", "white or navy"),
            "yellow": ("grey or dark blue jeans", "white or navy"),
            "brown":  ("beige or dark olive chinos, or dark jeans", "cream, white, or olive"),
            "green":  ("beige chinos or dark jeans", "white or khaki"),
            "cyan":   ("white or grey chinos", "white or light grey"),
            "blue":   ("grey or beige chinos", "white or cream"),
            "navy":   ("beige or grey chinos", "white or light blue"),
            "purple": ("dark jeans or grey chinos", "white or light grey"),
            "pink":   ("grey or navy chinos", "white or grey"),
            "white":  ("any colour — navy, black, or khaki jeans look great", "any colour"),
            "black":  ("dark jeans, grey or olive chinos", "white, grey, or red"),
            "grey":   ("navy or black jeans", "white, navy, or burgundy"),
        }
        formal_suggestions = {
            "red":    "navy blue or charcoal grey",
            "orange": "navy or dark brown",
            "yellow": "navy, grey, or dark green",
            "brown":  "cream, beige, or dark olive",
            "green":  "white, beige, or brown",
            "cyan":   "white or dark grey",
            "blue":   "white, grey, or light yellow",
            "navy":   "white, silver, or light blue",
            "purple": "grey, white, or light blue",
            "pink":   "grey, navy, or white",
            "white":  "navy, burgundy, or black",
            "black":  "silver, white, or a bold colour like red",
            "grey":   "navy, burgundy, or white",
        }

        query_lower = query.lower() if query else ""
        if any(w in query_lower for w in ["tie", "formal", "shirt", "blazer", "suit"]):
            suggestion = formal_suggestions.get(colour, "navy or grey")
            return (f"You're wearing a {colour} top. "
                    f"For a matching tie I'd suggest {suggestion}.")
        elif any(w in query_lower for w in ["pant", "trouser", "jeans", "chino", "bottom"]):
            bottoms, _ = casual_suggestions.get(colour, ("dark jeans", "white"))
            return (f"You're wearing a {colour} top. "
                    f"I'd suggest {bottoms}.")
        elif any(w in query_lower for w in ["shoes", "sneakers", "footwear"]):
            _, accessories = casual_suggestions.get(colour, ("dark jeans", "white or black"))
            return (f"You're wearing a {colour} top. "
                    f"For shoes I'd suggest {accessories} or white sneakers.")
        else:
            # Generic — suggest bottoms for casual top
            bottoms, _ = casual_suggestions.get(colour, ("dark jeans", "white"))
            return (f"You're wearing a {colour} top. "
                    f"I'd suggest pairing it with {bottoms}.")

    # ── Deep backend ──────────────────────────────────────────────────────────

    def _recognize_deep(self, frame: np.ndarray) -> list[dict]:
        if not self._embeddings:
            return []
        try:
            from PIL import Image as _PIL_Image
            pil_img = _PIL_Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            rgb = np.array(pil_img)
            locations = _fr_lib.face_locations(rgb, model="hog")
            encodings = _fr_lib.face_encodings(rgb, locations)
        except Exception as e:
            log.debug("Deep face detection error: %s", e)
            return []

        results = []
        for enc, (top, right, bottom, left) in zip(encodings, locations):
            best_name  = "unknown"
            best_dist  = self.DEEP_THRESHOLD
            with self._lock:
                for name, stored_encs in self._embeddings.items():
                    dists = _fr_lib.face_distance(stored_encs, enc)
                    min_dist = float(np.min(dists))
                    if min_dist < best_dist:
                        best_dist = min_dist
                        best_name = name

            w = right - left
            h = bottom - top
            shirt = _shirt_colour(frame, (left, top, w, h))
            results.append({
                "name":         best_name,
                "confidence":   round(1.0 - best_dist, 3),
                "bbox":         (left, top, w, h),
                "is_owner":     best_name == "owner",
                "is_known":     best_name != "unknown",
                "shirt_colour": shirt,
            })
        return results

    def _learn_deep(self, frame: np.ndarray, name: str) -> bool:
        try:
            from PIL import Image as _PIL_Image
            pil_img = _PIL_Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            rgb = np.array(pil_img)
            locs = _fr_lib.face_locations(rgb, model="hog")
            encs = _fr_lib.face_encodings(rgb, locs)
        except Exception as e:
            log.warning("Deep face encode error: %s", e)
            return False

        if not encs:
            log.warning("learn_deep: no face found in frame")
            return False

        enc = encs[0]
        key = name.lower()

        # Save raw frame for retraining later
        person_dir = FACES_DIR / key
        person_dir.mkdir(exist_ok=True)
        existing = len(list(person_dir.glob("*.jpg")))
        # Save 3 slight variations
        for i, arr in enumerate([frame, cv2.flip(frame, 1),
                                  cv2.convertScaleAbs(frame, alpha=1.1, beta=10)]):
            cv2.imwrite(str(person_dir / f"photo_{existing+i}.jpg"), arr)

        with self._lock:
            if key not in self._embeddings:
                self._embeddings[key] = []
            self._embeddings[key].append(enc)

        self._known_people[key] = {
            "name": name,
            "learned_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "photo_count": existing + 3,
        }
        self._save_known_people()
        log.info("Deep: learned face '%s' (%d total embeddings)",
                 name, len(self._embeddings[key]))
        return True

    # ── LBPH fallback backend ─────────────────────────────────────────────────

    def _recognize_lbph(self, frame: np.ndarray) -> list[dict]:
        if not self._trained:
            return []
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # equalise histogram — helps with lighting variation
        gray  = cv2.equalizeHist(gray)
        faces = self._face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
        )
        results = []
        for (x, y, w, h) in faces:
            face_roi = gray[y:y+h, x:x+w]
            # Guard: skip tiny/empty crops
            if face_roi.size == 0 or w < 20 or h < 20:
                continue
            face_roi = cv2.resize(face_roi, (200, 200))
            try:
                with self._lock:
                    label_id, confidence = self._recognizer.predict(face_roi)
                if confidence < self.LBPH_THRESHOLD:
                    name = self._labels.get(label_id, "unknown")
                else:
                    name = "unknown"
                shirt = _shirt_colour(frame, (x, y, w, h))
                results.append({
                    "name":         name,
                    "confidence":   round(confidence, 1),
                    "bbox":         (x, y, w, h),
                    "is_owner":     name == "owner",
                    "is_known":     name != "unknown",
                    "shirt_colour": shirt,
                })
            except Exception as e:
                log.debug("LBPH predict error: %s", e)
        return results

    def _learn_lbph(self, frame: np.ndarray, name: str) -> bool:
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray  = cv2.equalizeHist(gray)
        faces = self._face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
        )
        if len(faces) == 0:
            log.warning("learn_lbph: no face detected")
            return False

        person_dir = FACES_DIR / name.lower()
        person_dir.mkdir(exist_ok=True)
        existing = len(list(person_dir.glob("*.jpg")))

        x, y, w, h = faces[0]
        if w < 20 or h < 20:
            log.warning("learn_lbph: face too small")
            return False

        face_roi = cv2.resize(gray[y:y+h, x:x+w], (200, 200))
        for i in range(5):
            path = person_dir / f"photo_{existing+i}.jpg"
            if i == 0:
                cv2.imwrite(str(path), face_roi)
            elif i == 1:
                cv2.imwrite(str(path), cv2.flip(face_roi, 1))
            else:
                factor = 0.85 + (i * 0.1)
                varied = np.clip(face_roi * factor, 0, 255).astype(np.uint8)
                cv2.imwrite(str(path), varied)

        self._known_people[name.lower()] = {
            "name": name,
            "learned_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "photo_count": existing + 5,
        }
        self._save_known_people()
        self._train()
        log.info("LBPH: learned face '%s'", name)
        return True

    # ── Training ──────────────────────────────────────────────────────────────

    def _train(self) -> None:
        if _USE_DEEP:
            self._train_deep()
        else:
            self._train_lbph()

    def _train_deep(self) -> None:
        """Load stored face images and compute embeddings for all."""
        new_embeddings: dict[str, list] = {}
        for person_dir in sorted(FACES_DIR.iterdir()):
            if not person_dir.is_dir():
                continue
            name = person_dir.name
            encs = []
            for photo_path in person_dir.glob("*.jpg"):
                try:
                    img = _fr_lib.load_image_file(str(photo_path))
                    locs = _fr_lib.face_locations(img, model="hog")
                    enc  = _fr_lib.face_encodings(img, locs)
                    if enc:
                        encs.append(enc[0])
                except Exception:
                    pass
            if encs:
                new_embeddings[name] = encs
                log.debug("Deep trained '%s' with %d embeddings", name, len(encs))

        with self._lock:
            self._embeddings = new_embeddings
        self._trained = bool(new_embeddings)
        log.info("Deep face recogniser: %d people loaded.", len(new_embeddings))

    def _train_lbph(self) -> None:
        faces_data, labels_data = [], []
        label_id = 0
        self._labels, self._names = {}, {}

        for person_dir in sorted(FACES_DIR.iterdir()):
            if not person_dir.is_dir():
                continue
            name   = person_dir.name
            photos = list(person_dir.glob("*.jpg"))
            if not photos:
                continue
            self._labels[label_id] = name
            self._names[name]      = label_id
            for photo_path in photos:
                img = cv2.imread(str(photo_path), cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue
                img = cv2.resize(img, (200, 200))
                faces_data.append(img)
                labels_data.append(label_id)
            label_id += 1

        if not faces_data:
            self._trained = False
            return

        with self._lock:
            self._recognizer.train(faces_data, np.array(labels_data))
        self._trained = True
        log.info("LBPH trained on %d people, %d photos.",
                 len(self._labels), len(faces_data))

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load_known_people(self) -> None:
        if KNOWN_PEOPLE_FILE.exists():
            try:
                self._known_people = json.loads(
                    KNOWN_PEOPLE_FILE.read_text(encoding="utf-8")
                )
            except Exception:
                self._known_people = {}

    def _save_known_people(self) -> None:
        KNOWN_PEOPLE_FILE.write_text(
            json.dumps(self._known_people, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )