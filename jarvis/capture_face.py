"""
capture_face.py — Capture owner face photos for Jarvis face recognition.
Saves both full frame AND face-cropped versions for deep embedding training.
"""

import cv2
import os
import numpy as np

os.makedirs("vision/faces/owner", exist_ok=True)

# Clear old photos first
import glob
for f in glob.glob("vision/faces/owner/*.jpg"):
    os.remove(f)
print("Cleared old photos.")

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("ERROR: Could not open camera!")
    exit()

print("=" * 50)
print("JARVIS FACE REGISTRATION")
print("=" * 50)
print("Look at the camera.")
print("Press SPACE to capture (need 5 photos)")
print("Try slightly different angles between shots")
print("Press Q to quit")
print("=" * 50)

count = 0
needed = 5

while count < needed:
    ret, frame = cap.read()
    if not ret:
        continue

    display = frame.copy()
    h, w = display.shape[:2]
    cx, cy = w // 2, h // 2

    # Show face detection live
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))
    face_detected = len(faces) > 0
    for (fx, fy, fw, fh) in faces:
        cv2.rectangle(display, (fx, fy), (fx+fw, fy+fh), (0, 255, 0), 2)

    # Guide ellipse
    color = (0, 255, 0) if face_detected else (0, 0, 255)
    cv2.ellipse(display, (cx, cy), (100, 130), 0, 0, 360, color, 2)

    status = "Face detected! Press SPACE" if face_detected else "No face — move closer"
    cv2.putText(display, status, (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    cv2.putText(display, f"Photos: {count}/{needed}",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    cv2.putText(display, "SPACE = capture | Q = quit",
                (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)

    hints = ["Face camera directly", "Tilt slightly left",
             "Tilt slightly right", "Look slightly up", "Look slightly down"]
    if count < len(hints):
        cv2.putText(display, hints[count], (cx - 100, cy + 160),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)

    cv2.imshow("Jarvis - Face Registration", display)

    key = cv2.waitKey(1) & 0xFF
    if key == 32:  # SPACE
        if not face_detected:
            print(f"No face detected — please move closer and try again.")
            continue

        # Save full frame (face_recognition can find face in it)
        path = f"vision/faces/owner/photo_{count}.jpg"
        cv2.imwrite(path, frame)

        # Also save flipped and brightness variants
        cv2.imwrite(f"vision/faces/owner/photo_{count}_flip.jpg", cv2.flip(frame, 1))
        bright = cv2.convertScaleAbs(frame, alpha=1.15, beta=15)
        cv2.imwrite(f"vision/faces/owner/photo_{count}_bright.jpg", bright)

        print(f"✓ Captured photo {count + 1}/{needed} → {path}")
        count += 1

        # Flash
        white = frame.copy()
        white[:] = (255, 255, 255)
        cv2.imshow("Jarvis - Face Registration", white)
        cv2.waitKey(150)

    elif key == ord('q') or key == ord('Q'):
        print("Cancelled.")
        break

cap.release()
cv2.destroyAllWindows()

if count == needed:
    print(f"\n✓ All {needed} photos captured ({needed*3} total with variants)!")
    print("✓ Owner face registered successfully.")

    # Verify face_recognition can find faces in the saved photos
    try:
        import face_recognition
        found = 0
        for f in glob.glob("vision/faces/owner/*.jpg"):
            img = face_recognition.load_image_file(f)
            locs = face_recognition.face_locations(img)
            if locs:
                found += 1
        print(f"✓ Verification: face_recognition found faces in {found}/{count*3} photos.")
        if found == 0:
            print("⚠ WARNING: face_recognition could not find faces in any photo!")
            print("  Try better lighting or move closer to the camera.")
        else:
            print("✓ Ready! Restart Jarvis — it will recognize you as owner.")
    except ImportError:
        print("✓ Ready! Restart Jarvis.")
else:
    print(f"\nOnly {count}/{needed} photos captured. Run again to complete.")