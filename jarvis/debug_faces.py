"""Run this to diagnose why face_recognition loads 0 people."""
import cv2
import glob
import numpy as np
from pathlib import Path

FACES_DIR = Path("vision/faces/owner")
photos = list(FACES_DIR.glob("*.jpg"))
print(f"Photos found: {len(photos)}")

try:
    import face_recognition as fr
    print("face_recognition imported OK")
except ImportError:
    print("face_recognition NOT installed")
    exit()

ok = 0
for p in photos:
    img_bgr = cv2.imread(str(p))
    if img_bgr is None:
        print(f"  FAIL to read: {p.name}")
        continue
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    try:
        locs = fr.face_locations(img_rgb, model="hog")
        encs = fr.face_encodings(img_rgb, locs)
        print(f"  {p.name}: {len(locs)} face(s), {len(encs)} encoding(s)")
        if encs:
            ok += 1
    except Exception as e:
        print(f"  {p.name}: ERROR — {e}")

print(f"\nResult: {ok}/{len(photos)} photos have usable face encodings.")
if ok == 0:
    print("PROBLEM: No faces found in any photo.")
    print("Possible causes:")
    print("  1. Photos too dark or blurry")
    print("  2. Face too small in frame — sit closer to camera")
    print("  3. dlib HOG detector needs frontal face — look straight at camera")
