import face_recognition
import numpy as np
from PIL import Image

img = face_recognition.load_image_file("vision/faces/owner/photo_0.jpg")
print(f"shape: {img.shape}, dtype: {img.dtype}")

# Force exactly 3 channels
if img.ndim == 3 and img.shape[2] == 4:
    img = img[:, :, :3]
    print("Stripped alpha channel")

img = np.ascontiguousarray(img[:, :, :3])
print(f"final shape: {img.shape}")
print(face_recognition.face_locations(img))
