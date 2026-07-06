"""
utils/audio_helpers.py — Low-level audio utilities.
"""

import audioop
import tempfile
import wave
from pathlib import Path

import numpy as np


def compute_rms(audio_bytes: bytes, sample_width: int = 2) -> float:
    """Return the RMS amplitude (0.0–1.0) of a raw PCM audio chunk."""
    try:
        rms = audioop.rms(audio_bytes, sample_width)
        return rms / 32768.0  # normalise 16-bit range to 0–1
    except Exception:
        return 0.0


def save_wav(
    frames: list[bytes],
    sample_rate: int,
    channels: int,
    sample_width: int = 2,
) -> Path:
    """
    Write raw PCM frames to a temporary WAV file.
    Returns the path to the file; caller is responsible for deletion.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp.name, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(frames))
    return Path(tmp.name)


def frames_to_numpy(frames: list[bytes]) -> np.ndarray:
    """Convert raw PCM byte frames to a normalised float32 NumPy array."""
    raw = b"".join(frames)
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    return samples / 32768.0
