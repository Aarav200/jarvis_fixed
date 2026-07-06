"""
capture_face.py — Capture owner face photos for Jarvis face recognition.
Run this once to register yourself as Jarvis's owner.
"""

import cv2
import os

# Create folder for owner photos
os.makedirs("vision/faces/owner", exist_ok=True)

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

    # Draw guide overlay
    display = frame.copy()
    h, w = display.shape[:2]

    # Draw face guide circle
    cx, cy = w // 2, h // 2
    cv2.ellipse(display, (cx, cy), (100, 130), 0, 0, 360, (0, 255, 0), 2)

    # Instructions
    cv2.putText(display, f"Photos: {count}/{needed}",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    cv2.putText(display, "SPACE = capture | Q = quit",
                (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)

    if count == 0:
        cv2.putText(display, "Face camera directly",
                    (cx - 100, cy + 160), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
    elif count == 1:
        cv2.putText(display, "Tilt slightly left",
                    (cx - 80, cy + 160), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
    elif count == 2:
        cv2.putText(display, "Tilt slightly right",
                    (cx - 80, cy + 160), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
    elif count == 3:
        cv2.putText(display, "Look slightly up",
                    (cx - 80, cy + 160), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
    elif count == 4:
        cv2.putText(display, "Look slightly down",
                    (cx - 80, cy + 160), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)

    cv2.imshow("Jarvis - Face Registration", display)

    key = cv2.waitKey(1) & 0xFF
    if key == 32:  # SPACE
        path = f"vision/faces/owner/photo_{count}.jpg"
        cv2.imwrite(path, frame)
        print(f"✓ Captured photo {count + 1}/{needed} → {path}")
        count += 1

        # Flash effect
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
    print("\n✓ All 5 photos captured!")
    print("✓ Owner face registered successfully.")
    print("\nYou can now restart Jarvis — it will recognize you as its owner.")
else:
    print(f"\nOnly {count}/{needed} photos captured. Run again to complete registration.")
