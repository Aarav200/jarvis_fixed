"""
voice.py — All audio I/O for Jarvis.
"""

import queue
import threading
import tempfile
import time
from pathlib import Path

import numpy as np
import pyaudio
import whisper
import pyttsx3

import config
from utils.audio_helpers import compute_rms
from utils.logger import get_logger

log = get_logger(__name__)


class VoiceEngine:
    def __init__(self) -> None:
        self._pa = pyaudio.PyAudio()
        self._utterance_queue: queue.Queue[str] = queue.Queue()
        self._stop_event = threading.Event()
        self._listen_thread = None
        self._speaking = threading.Event()
        self._waiting_for_response = False  # True = no wake word needed

        log.info("Loading Whisper model '%s' …", config.WHISPER_MODEL)
        self._whisper = whisper.load_model(config.WHISPER_MODEL)
        log.info("Whisper ready.")

    def start_listening(self) -> None:
        if self._listen_thread and self._listen_thread.is_alive():
            return
        self._stop_event.clear()
        self._listen_thread = threading.Thread(
            target=self._mic_loop, daemon=True, name="jarvis-mic"
        )
        self._listen_thread.start()
        log.info("Listening thread started.")

    def get_utterance(self, timeout=None):
        try:
            result = self._utterance_queue.get(timeout=timeout)
            self._waiting_for_response = False  # Reset after getting response
            return result
        except queue.Empty:
            self._waiting_for_response = False
            return None

    def expect_response(self) -> None:
        """Call this before speak() when you expect a direct response."""
        self._waiting_for_response = True

    def speak(self, text: str) -> None:
        if not text:
            return
        log.info("Speaking: '%s'", text)
        self._speaking.set()
        try:
            from jarvis_widget import notify
            notify("speaking", {"text": text})
        except Exception:
            pass
        try:
            self._speak_edge(text)
        except Exception as e:
            log.warning("Edge TTS failed (%s), falling back to pyttsx3", e)
            self._speak_pyttsx3(text)
        finally:
            time.sleep(0.3)
            self._speaking.clear()
            try:
                from jarvis_widget import notify
                notify("idle")
            except Exception:
                pass

    def _speak_edge(self, text: str) -> None:
        """Use edge-tts via subprocess to avoid asyncio conflicts."""
        import subprocess
        import sys
        import pygame

        tmp_path = Path(tempfile.mktemp(suffix=".mp3"))
        script = (
            "import asyncio, edge_tts\n"
            "async def run():\n"
            f"    c = edge_tts.Communicate({repr(text)}, 'en-GB-RyanNeural')\n"
            f"    await c.save({repr(str(tmp_path))})\n"
            "asyncio.run(run())"
        )
        log.debug("Edge TTS script: %s", script)
        result = subprocess.run(
            [sys.executable, "-c", script],
            timeout=15,
            capture_output=True,
        )
        log.debug("Edge TTS return code: %d", result.returncode)
        if result.stderr:
            log.debug("Edge TTS stderr: %s", result.stderr.decode())
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode())
        if not tmp_path.exists():
            raise RuntimeError(f"MP3 file not created at {tmp_path}")

        try:
            pygame.mixer.init()
            pygame.mixer.music.load(str(tmp_path))
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.05)
            pygame.mixer.music.unload()
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _speak_pyttsx3(self, text: str) -> None:
        """Fallback TTS using pyttsx3."""
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty('rate', config.TTS_RATE)
            engine.setProperty('volume', config.TTS_VOLUME)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            log.error("pyttsx3 also failed: %s", e)
            print(f"[JARVIS] {text}")

    def stop(self) -> None:
        self._stop_event.set()
        if self._listen_thread:
            self._listen_thread.join(timeout=3)
        self._pa.terminate()
        log.info("VoiceEngine stopped.")

    def _mic_loop(self) -> None:
        stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=config.RECORD_CHANNELS,
            rate=config.RECORD_SAMPLE_RATE,
            input=True,
            frames_per_buffer=1024,
        )

        chunk_duration = 1024 / config.RECORD_SAMPLE_RATE
        silence_chunks = int(config.SILENCE_DURATION / chunk_duration)

        log.info("Calibrating microphone noise floor ...")
        noise_samples = []
        for _ in range(int(config.RECORD_SAMPLE_RATE / 1024)):
            chunk = stream.read(1024, exception_on_overflow=False)
            noise_samples.append(compute_rms(chunk))
        noise_floor = sum(noise_samples) / len(noise_samples)
        dynamic_threshold = max(noise_floor * 4, 0.001)
        log.info("Noise floor: %.4f  Trigger threshold: %.4f",
                 noise_floor, dynamic_threshold)

        try:
            while not self._stop_event.is_set():
                if self._speaking.is_set():
                    time.sleep(0.05)
                    continue

                frames = []
                silent_count = 0
                recording = False

                while not self._stop_event.is_set():
                    chunk = stream.read(1024, exception_on_overflow=False)
                    rms = compute_rms(chunk)

                    if rms > dynamic_threshold:
                        recording = True
                        silent_count = 0
                        frames.append(chunk)
                    elif recording:
                        frames.append(chunk)
                        silent_count += 1
                        if silent_count >= silence_chunks:
                            break

                    if len(frames) * chunk_duration > config.MAX_RECORD_SECONDS:
                        log.warning("Max recording length reached; truncating.")
                        break

                if not frames or self._stop_event.is_set():
                    continue

                self._process_audio(frames)

        except Exception as exc:
            log.error("Mic loop error: %s", exc, exc_info=True)
        finally:
            stream.stop_stream()
            stream.close()

    def _process_audio(self, frames) -> None:
        try:
            raw = b"".join(frames)
            audio_np = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

            if config.RECORD_CHANNELS == 2:
                audio_np = audio_np.reshape(-1, 2).mean(axis=1)

            if config.RECORD_SAMPLE_RATE != 16000:
                import scipy.signal
                num_samples = int(len(audio_np) * 16000 / config.RECORD_SAMPLE_RATE)
                audio_np = scipy.signal.resample(audio_np, num_samples)

            result = self._whisper.transcribe(
                audio_np, language=config.WHISPER_LANGUAGE, fp16=False
            )
            transcript: str = result.get("text", "").strip()
            log.info("Transcript: '%s'", transcript)

            if not transcript:
                return

            lower = transcript.lower()
            wake = config.WAKE_WORD.lower()

            if wake in lower or "jarvis" in lower:
                # Wake word detected — strip it and queue utterance
                if wake in lower:
                    idx = lower.find(wake) + len(wake)
                else:
                    idx = lower.find("jarvis") + len("jarvis")
                utterance = transcript[idx:].strip(" ,.")
                log.info("Wake word detected. Utterance: '%s'", utterance)
                self._waiting_for_response = False
                self._utterance_queue.put(utterance or "")

            elif self._waiting_for_response:
                # No wake word needed — direct response expected
                log.info("Direct response: '%s'", transcript)
                self._utterance_queue.put(transcript)

        except Exception as exc:
            log.error("Transcription failed: %s", exc, exc_info=True)
