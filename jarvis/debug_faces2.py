"""Deep debug — check exactly what's in the photos."""
import cv2
import numpy as np
from pathlib import Path

FACES_DIR = Path("vision/faces/owner")
photos = list(FACES_DIR.glob("*.jpg"))[:3]  # check first 3 only

for p in photos:
    img = cv2.imread(str(p))
    if img is None:
        print(f"{p.name}: cv2.imread returned None")
        continue
    print(f"{p.name}: shape={img.shape} dtype={img.dtype} min={img.min()} max={img.max()}")
    rgb = np.ascontiguousarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB), dtype=np.uint8)
    print(f"  after conversion: shape={rgb.shape} dtype={rgb.dtype} flags={rgb.flags['C_CONTIGUOUS']}")
    
    try:
        import face_recognition as fr
        locs = fr.face_locations(rgb, model="hog")
        print(f"  HOG face_locations: {locs}")
        locs2 = fr.face_locations(rgb, model="cnn")
        print(f"  CNN face_locations: {locs2}")
    except Exception as e:
        print(f"  face_recognition error: {e}")
