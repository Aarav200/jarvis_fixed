"""
main.py — Jarvis entry point and main controller loop.
"""

import signal
import sys

import config
from brain import Brain
from command_router import CommandRouter
from plugins import PluginLoader
from utils.logger import get_logger
from voice import VoiceEngine

log = get_logger(__name__)


class Jarvis:
    _STOP_PHRASES = {"stop", "goodbye", "exit", "quit", "shut down", "bye"}

    def __init__(self) -> None:
        log.info("Initialising Jarvis …")
        loader = PluginLoader(config.PLUGINS_DIR)
        n = loader.load_all()
        log.info("Loaded %d plugin(s).", n)
        self.voice = VoiceEngine()
        self.brain = Brain()
        self.router = CommandRouter()
        self.vision = None
        self._running = False
        self._last_seen_objects = []

    def start(self) -> None:
        self._running = True
        self.voice.start_listening()

        # ── Start vision system ───────────────────────────────────────────────
        self.visualizer = None
        try:
            from vision.context import VisionContext
            from vision.visualizer import VisionVisualizer
            from commands.vision_commands import set_vision

            self.vision = VisionContext(
                interval=10.0,
                mode="interval",
                on_unknown_object=self._on_unknown_object,
            )
            if self.vision.start():
                set_vision(self.vision)
                self.brain.set_vision(self.vision)
                # Start visualizer (hidden by default)
                self.visualizer = VisionVisualizer(self.vision)
                self.visualizer.start()
                # Set stranger detection callback
                self.vision.set_stranger_callback(self._on_stranger)
                log.info("Vision system started.")
            else:
                log.warning("Vision system failed to start — continuing without camera.")
                self.vision = None
        except Exception as e:
            log.warning("Vision system unavailable: %s", e)
            self.vision = None

        # ── Start call monitors ───────────────────────────────────────────────
        try:
            from commands.call_monitor import start_all_monitors
            start_all_monitors(self.voice)
            log.info("Call monitors started.")
        except Exception as e:
            log.warning("Call monitors could not start: %s", e)

        self.voice.speak("Jarvis at your service, sir.")
        log.info("Jarvis is running. Wake word: '%s'", config.WAKE_WORD)

        try:
            self._loop()
        except KeyboardInterrupt:
            log.info("KeyboardInterrupt received.")
        finally:
            self._shutdown()

    def _shutdown(self) -> None:
        log.info("Shutting down Jarvis …")
        if self.visualizer:
            self.visualizer.stop()
        if self.vision:
            self.vision.stop()
        self.voice.speak("Goodbye.")
        self.voice.stop()

    def _loop(self) -> None:
        while self._running:
            self.voice._waiting_for_response = False
            utterance = self.voice.get_utterance(timeout=1.0)
            if utterance is None:
                continue
            utterance = utterance.strip()
            if not utterance:
                continue
            log.info("User said: '%s'", utterance)
            if utterance.lower() in self._STOP_PHRASES:
                self._running = False
                continue
            self._handle_utterance(utterance)

    def _handle_utterance(self, utterance: str) -> None:
        # Small talk / praise — don't route to commands
        lower = utterance.lower().strip()

        # AI status check
        if any(p in lower for p in ["which ai are you using", "what ai are you using",
                                     "are you online", "are you offline",
                                     "what model are you using"]):
            status = self.brain.get_engine_status()
            self.voice.speak(f"Currently using: {status}, sir.")
            return

        # Switch to offline mode explicitly
        if any(p in lower for p in ["go offline", "use offline mode",
                                     "use local ai", "switch to offline"]):
            self.brain._engine._online = False
            self.voice.speak("Switched to offline mode. Using local Ollama model, sir.")
            return

        # Switch back online
        if any(p in lower for p in ["go online", "use online mode",
                                     "switch to online", "use groq"]):
            self.brain._engine._online = True
            self.brain._engine._init_groq()
            self.voice.speak("Switched to online mode. Using Groq API, sir.")
            return
        praise_phrases = ["good job", "well done", "great job", "nice", "thanks",
                         "thank you", "perfect", "awesome", "cool", "okay", "ok",
                         "good", "great", "excellent", "bravo", "brilliant"]
        if lower.strip(".,!") in praise_phrases or lower in praise_phrases:
            responses = [
                "Thank you, sir.",
                "Glad to help, sir.",
                "Of course, sir.",
                "Always at your service, sir.",
            ]
            import random
            self.voice.speak(random.choice(responses))
            return

        # Self-correction detection — "no jarvis I am coding/gaming/resting"
        correction = self._detect_correction(lower)
        if correction:
            if self.vision:
                self.vision._classifier._history.clear()  # Reset activity history
            self.voice.speak(
                f"Understood sir, I'll remember you're {correction}. "
                f"I'll improve my detection over time."
            )
            # Log correction for learning
            import json
            from pathlib import Path
            corrections_file = Path("memory/activity_corrections.json")
            corrections = []
            if corrections_file.exists():
                try:
                    corrections = json.loads(corrections_file.read_text())
                except Exception:
                    pass
            corrections.append({
                "corrected_to": correction,
                "timestamp": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
                "objects_seen": self.vision.get_state().objects_present if self.vision else []
            })
            corrections_file.write_text(json.dumps(corrections[-100:], indent=2))
            return

        # Direct vision shortcuts — bypass LLM for speed
        # Face learning — "this is Akshay" / "his name is Akshay"
        import re
        face_learn = re.search(
            r"(?:this is|his name is|her name is|they are|introduce|unknown person.*is|person you see is|that person is) ([a-zA-Z]+)",
            lower
        )
        if face_learn:
            name = face_learn.group(1).strip().capitalize()
            if self.vision:
                self.voice.speak(f"Let me look... capturing face now.")
                success = self.vision.learn_current_face(name)
                if success:
                    self.voice.speak(
                        f"Got it sir! I've learned {name}'s face. "
                        f"I'll recognize them next time."
                    )
                else:
                    self.voice.speak(
                        f"I couldn't clearly see a face. "
                        f"Please make sure {name} is looking at the camera."
                    )
            return

        # Who is there / who do you see
        if any(p in lower for p in ["who is there", "who do you see",
                                     "who is in the room", "who can you see"]):
            if self.vision:
                state = self.vision.capture_now()
                if state.faces_detected:
                    desc = self.vision._face_recognizer.describe_faces(
                        state.faces_detected
                    )
                    self.voice.speak(desc if desc else "I can see someone but can't identify them.")
                else:
                    self.voice.speak("I don't see anyone clearly right now.")
            return

        # Show/hide camera window
        if any(p in lower for p in ["show camera", "show me the camera",
                                     "open camera", "show vision",
                                     "show me what you see"]):
            if self.visualizer:
                self.visualizer.show()
                self.voice.speak("Camera window opened, sir.")
            else:
                self.voice.speak("Vision system not active.")
            return
        if any(p in lower for p in ["hide camera", "close camera",
                                     "hide vision", "close vision"]):
            if self.visualizer:
                self.visualizer.hide()
                self.voice.speak("Camera window hidden, sir.")
            else:
                self.voice.speak("Vision system not active.")
            return
        if any(p in lower for p in ["toggle camera", "toggle vision"]):
            if self.visualizer:
                shown = self.visualizer.toggle()
                self.voice.speak(
                    "Camera window opened." if shown else "Camera window hidden."
                )
            return

        if any(p in lower for p in ["what do you see", "what can you see",
                                     "what are you seeing", "look around"]):
            spoken = self.vision.describe_now() if self.vision else "Camera not active."
            self.voice.speak(spoken)
            return
        if any(p in lower for p in ["what is in my hand", "what am i holding",
                                     "what do i have in my hand", "what i am holding",
                                     "tell me what is in my hand",
                                     "can you tell me what i am holding",
                                     "can you tell me what is in my hand"]):
            if self.vision:
                state = self.vision.capture_now()
                items = [o for o in set(state.objects_present) if o != "person"]
                if items:
                    # Store last detected items for correction context
                    self._last_seen_objects = items
                    self.voice.speak(f"I can see {', '.join(items)}.")
                else:
                    self.voice.speak("I can't clearly see what's in your hand, sir.")
            else:
                self.voice.speak("Camera not active.")
            return

        # Object correction — "no it is a mouse" / "this is actually a X"
        import re as _re
        obj_correction = _re.search(
            r"(?:no )?(?:it is|this is|that is|its) (?:a |an )?([a-zA-Z _]+)",
            lower
        )
        if obj_correction and hasattr(self, "_last_seen_objects") and self._last_seen_objects:
            correct_name = obj_correction.group(1).strip()
            # Override the last detected object
            wrong_label = self._last_seen_objects[0]
            if self.vision:
                self.vision._detector.learn_object(
                    correct_name, yolo_label=wrong_label
                )
            self.voice.speak(
                f"Got it sir! I'll remember that {wrong_label} is actually "
                f"a {correct_name} from now on."
            )
            self._last_seen_objects = []
            return
        if any(p in lower for p in ["am i happy", "am i sad", "how do i look",
                                     "what is my mood", "can you tell my emotion",
                                     "am i smiling"]):
            if self.vision:
                frame = self.vision._camera.capture_now()
                if frame is not None:
                    emotion = self._detect_emotion(frame)
                    self.voice.speak(emotion)
                else:
                    self.voice.speak("I can't get a clear view right now, sir.")
            else:
                self.voice.speak("Camera not active.")
            return
        if any(p in lower for p in ["what am i doing", "what am i working on",
                                     "what i am doing", "what am i currently doing",
                                     "can you tell me what i am doing",
                                     "can you tell me what i'm doing"]):
            if self.vision:
                state = self.vision.capture_now()
                if state and state.activity != "unknown":
                    spoken = state.activity_context  # Just one sentence, no duplicate
                else:
                    spoken = "I can see you but I'm not sure what you're doing."
            else:
                spoken = "Camera not active."
            self.voice.speak(spoken)
            return
        if any(p in lower for p in ["am i productive", "am i being productive",
                                     "am i focused"]):
            if self.vision:
                state = self.vision.get_state()
                productive = ["coding", "reading", "working"]
                if state.activity in productive:
                    spoken = f"Yes sir, you're being productive — you're {state.activity}!"
                elif state.activity in ["gaming", "resting", "away", "on phone"]:
                    spoken = f"Honestly sir, you're {state.activity}. Maybe get back to work?"
                else:
                    spoken = "I can see you but I'm not sure if you're being productive."
            else:
                spoken = "Camera not active."
            self.voice.speak(spoken)
            return

        # ── Game Agent interception (BEFORE LLM) ─────────────────────────────
        # These must be caught here — LLM will misroute them to open_app/web_search
        _GAME_FULL = [
            "create a game", "make a game", "build a game",
            "create game", "make game", "build game",
        ]
        _GAME_ASSET = [
            "create a low poly", "create a high poly",
            "create a 3d", "make a 3d",
            "create an asset", "make an asset",
            "model a ", "generate asset",
            "create a sword", "make a sword",
            "create a tree", "make a tree",
            "create a car", "make a car",
            "create a house", "make a house",
            "create a character", "make a character",
            "create a chest", "make a chest",
            "create a rock", "make a rock",
            "create a weapon", "make a weapon",
            "create a building", "make a building",
            "create pine tree", "create fantasy",
            "create low poly", "create high poly",
            "blender create", "blender make",
        ]
        _GAME_SCRIPT = [
            "write a unity script", "create a unity script",
            "write a c# script", "generate unity script",
            "write player controller", "write enemy ai",
            "write inventory system", "write save system",
            "write a game script", "create game script",
        ]
        _GAME_GDD = [
            "game design document", "create a gdd",
            "design document for", "game design for",
        ]
        _GAME_STATUS = [
            "game project status", "game progress",
            "what have you built", "show game project",
        ]
        _GAME_LESSONS = [
            "what did you learn from", "lessons learned",
            "game agent lessons", "past game mistakes",
        ]

        _is_game_full   = any(t in lower for t in _GAME_FULL)
        _is_game_asset  = any(t in lower for t in _GAME_ASSET)
        _is_game_script = any(t in lower for t in _GAME_SCRIPT)
        _is_game_gdd    = any(t in lower for t in _GAME_GDD)
        _is_game_status = any(t in lower for t in _GAME_STATUS)
        _is_game_lesson = any(t in lower for t in _GAME_LESSONS)

        if any([_is_game_full, _is_game_asset, _is_game_script,
                _is_game_gdd, _is_game_status, _is_game_lesson]):
            try:
                import sys, os
                sys.path.insert(0, os.getcwd())
                from jarvis_game_agent import GameAgent
                if not hasattr(self, "_game_agent") or self._game_agent is None:
                    self._game_agent = GameAgent(voice=self.voice)
                    log.info("Game Agent initialised.")

                if _is_game_status:
                    result = self._game_agent._show_status()
                elif _is_game_lesson:
                    result = self._game_agent._show_lessons()
                else:
                    # Run in background so voice stays responsive
                    import threading
                    def _run():
                        self._game_agent.handle(utterance)
                    threading.Thread(target=_run, daemon=True,
                                     name="jarvis-game-agent").start()
                    if _is_game_full:
                        result = "Starting game development pipeline, sir. This will take a few minutes."
                    elif _is_game_asset:
                        result = "Creating the asset now, sir. I will let you know when it is ready."
                    elif _is_game_script:
                        result = "Writing the script now, sir."
                    elif _is_game_gdd:
                        result = "Generating the game design document, sir."
                    else:
                        result = "On it, sir."
                self.voice.speak(result)
                return
            except Exception as e:
                log.error("Game Agent error: %s", e)
                import traceback; traceback.print_exc()
                self.voice.speak(f"Game agent error, sir: {e}")
                return
        # ── End Game Agent interception ────────────────────────────────────────

        response = self.brain.think(utterance)
        spoken = response.spoken_text

        if response.action:
            result = self.router.dispatch(response.action)
            if result == CommandRouter.SIGNAL_STOP:
                self._running = False
                spoken = "Shutting down. Goodbye."
            elif result == CommandRouter.SIGNAL_CLEAR_MEMORY:
                self.brain.clear_short_term()
                spoken = "Conversation memory cleared."
            else:
                spoken = result

        log.info("Speaking: '%s'", spoken)
        if spoken:
            self.voice.speak(spoken)
        self.voice._waiting_for_response = False

    def _detect_emotion(self, frame) -> str:
        """Basic emotion detection using MediaPipe face mesh."""
        try:
            import mediapipe as mp
            import numpy as np
            import cv2

            mp_face = mp.solutions.face_mesh
            with mp_face.FaceMesh(
                static_image_mode=True,
                max_num_faces=1,
                refine_landmarks=True,
            ) as face_mesh:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = face_mesh.process(rgb)

                if not results.multi_face_landmarks:
                    return "I can see you but can't read your expression clearly, sir."

                landmarks = results.multi_face_landmarks[0].landmark
                h, w = frame.shape[:2]

                # Mouth corners for smile detection
                # Landmark 61 = left mouth corner, 291 = right mouth corner
                # Landmark 0 = nose tip (reference)
                left_mouth = landmarks[61]
                right_mouth = landmarks[291]
                nose = landmarks[1]

                # If mouth corners are higher than nose center = smiling
                mouth_avg_y = (left_mouth.y + right_mouth.y) / 2
                mouth_width = abs(right_mouth.x - left_mouth.x)

                # Wider mouth relative to face = smiling
                # Eyebrow landmarks: 70 (left), 300 (right)
                left_brow = landmarks[70]
                right_brow = landmarks[300]
                left_eye = landmarks[159]
                right_eye = landmarks[386]

                brow_to_eye_left = left_eye.y - left_brow.y
                brow_to_eye_right = right_eye.y - right_brow.y
                avg_brow_raise = (brow_to_eye_left + brow_to_eye_right) / 2

                if mouth_width > 0.45:
                    emotion = "happy and smiling"
                elif avg_brow_raise < 0.025:
                    emotion = "a bit tense or concentrated"
                elif avg_brow_raise > 0.055:
                    emotion = "surprised or curious"
                else:
                    emotion = "focused and neutral"

                return f"You look {emotion}, sir."

        except Exception as e:
            return "I can see your face but can't read your emotion right now, sir."

    def _detect_correction(self, text: str) -> str:
        """Detect if user is correcting Jarvis about their activity."""
        activities = {
            "working": ["coding", "programming", "working", "developing", "studying"],
            "gaming": ["gaming", "playing games", "playing"],
            "reading": ["reading"],
            "resting": ["resting", "relaxing", "sleeping", "lying down"],
            "eating": ["eating", "having a meal", "having food"],
            "on phone": ["on my phone", "using my phone"],
            "standing": ["standing", "standing up", "walking", "moving"],
        }
        # First check for negation — "I am NOT resting" should not match resting
        negation_patterns = ["not resting", "not gaming", "not eating", 
                             "not coding", "not working", "not reading",
                             "not sleeping", "not lying"]
        for neg in negation_patterns:
            if neg in text:
                # User is denying an activity — look for what they ARE doing
                # Find the positive statement after "I am" following the negation
                pass

        # Look for positive corrections only
        # Pattern: "I am [activity]" or "I'm [activity]" 
        # But skip if preceded by "not"
        import re
        # Find all "I am X" or "I'm X" patterns
        matches = re.findall(r"i(?:'m| am) (\w+(?:\s\w+)?)", text)
        
        for match in matches:
            match = match.strip()
            # Skip negated ones
            if f"not {match}" in text or f"no {match}" in text:
                continue
            # Check against activity keywords
            for activity, keywords in activities.items():
                if any(kw in match for kw in keywords):
                    return activity
        return ""

    def _on_stranger(self, count: int) -> None:
        """Called when an unknown person appears in camera."""
        msg = (
            f"Sir, there {'is' if count == 1 else 'are'} "
            f"{'someone' if count == 1 else str(count) + ' people'} "
            f"I don't recognize in view. "
            f"Would you like to introduce them?"
        )
        self.voice.expect_response()
        self.voice.speak(msg)
        response = self.voice.get_utterance(timeout=8)
        if response and any(w in response.lower() for w in ["yes", "sure", "okay","no"]):
            self.voice.speak("What is their name?")
            self.voice.expect_response()
            name_response = self.voice.get_utterance(timeout=8)
            if name_response:
                name = name_response.strip().capitalize()
                if self.vision:
                    success = self.vision.learn_current_face(name)
                    if success:
                        self.voice.speak(f"Got it! I've learned {name}'s face.")
                    else:
                        self.voice.speak("Couldn't capture the face clearly.")

    def _on_unknown_object(self, obj_label: str) -> None:
        """Called when vision detects something it can't identify."""
        self.voice.expect_response()
        self.voice.speak(
            f"Sir, I can see something but I don't recognize it. "
            f"May I ask what that is?"
        )
        response = self.voice.get_utterance(timeout=15)
        if response and len(response.strip()) > 1:
            name = response.strip()
            if self.vision:
                # Pass the YOLO label so we override it next time
                self.vision._detector.learn_object(
                    name, yolo_label=obj_label
                )
            self.voice.speak(
                f"Got it sir, I'll remember that's a {name} from now on."
            )


def _handle_sigterm(signum, frame):
    log.info("SIGTERM received.")
    sys.exit(0)


def main() -> None:
    signal.signal(signal.SIGTERM, _handle_sigterm)
    jarvis = Jarvis()
    jarvis.start()


if __name__ == "__main__":
    main()
