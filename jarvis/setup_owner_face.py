"""
setup_owner_face.py — Convert captured photos to grayscale training format.
Run this once after capture_face.py to prepare owner face data.
"""

import cv2
import os
from pathlib import Path

# Check existing photos
owner_dir = Path("vision/faces/owner")
if not owner_dir.exists() or not list(owner_dir.glob("*.jpg")):
    print("ERROR: No owner photos found!")
    print("Run capture_face.py first.")
    exit()

photos = list(owner_dir.glob("*.jpg"))
print(f"Found {len(photos)} owner photos.")

# Process each photo — add grayscale + augmented versions
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

processed = 0
for i, photo_path in enumerate(photos):
    img = cv2.imread(str(photo_path))
    if img is None:
        continue

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Try to find face in photo
    faces = face_cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=3, minSize=(50, 50)
    )

    if len(faces) > 0:
        x, y, w, h = faces[0]
        face_roi = gray[y:y+h, x:x+w]
        face_roi = cv2.resize(face_roi, (200, 200))

        # Save original
        cv2.imwrite(str(owner_dir / f"trained_{i}_orig.jpg"), face_roi)

        # Save flipped
        cv2.imwrite(str(owner_dir / f"trained_{i}_flip.jpg"),
                    cv2.flip(face_roi, 1))

        # Save brightened
        bright = cv2.convertScaleAbs(face_roi, alpha=1.2, beta=20)
        cv2.imwrite(str(owner_dir / f"trained_{i}_bright.jpg"), bright)

        # Save darkened
        dark = cv2.convertScaleAbs(face_roi, alpha=0.8, beta=-20)
        cv2.imwrite(str(owner_dir / f"trained_{i}_dark.jpg"), dark)

        processed += 1
        print(f"✓ Processed photo {i+1}/{len(photos)}")
    else:
        print(f"⚠ No face detected in photo {i+1} — try retaking")

print(f"\n✓ Owner face setup complete! {processed}/{len(photos)} photos processed.")
print("✓ Jarvis will now recognize you as its owner.")
print("\nRestart Jarvis to activate face recognition.")
