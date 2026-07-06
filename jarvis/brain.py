"""
brain.py — AI reasoning core for Jarvis.

Now uses multi-tier LLMEngine:
  Tier 1: Groq API (online, fastest)
  Tier 2: Ollama llama3.2 (offline, GPU)
  Tier 3: Ollama llama3.2:1b (offline, fast)
  Tier 4: Rule-based fallback
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import config
from llm_engine import LLMEngine, LLMResponse
from utils.logger import get_logger
from utils.text_helpers import extract_action, ParsedAction, sanitise_for_tts

log = get_logger(__name__)


@dataclass
class Message:
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


@dataclass
class BrainResponse:
    spoken_text: str
    raw_text: str
    action: ParsedAction | None
    model_used: str = ""
    tier: int = 0


class Brain:
    """
    Conversational AI core using multi-tier LLM engine.
    """

    def __init__(self) -> None:
        self._history: list[Message] = []
        self._preferences: dict = {}
        self._vision = None

        # Initialize multi-tier LLM engine
        self._engine = LLMEngine(
            api_key=config.OPENAI_API_KEY,
            groq_model="llama-3.3-70b-versatile",
        )

        status = self._engine.get_status()
        log.info("LLM Engine status: Groq=%s, Ollama=%s",
                 status["groq"], status["ollama"])

        self._load_preferences()

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_vision(self, vision) -> None:
        self._vision = vision
        log.info("Vision context connected to brain.")

        
    def think(self, user_input: str) -> BrainResponse:
        """Process input and return a response."""
        if not user_input.strip():
            return BrainResponse(
                spoken_text="I didn't catch that. Could you repeat?",
                raw_text="",
                action=None,
            )

        # --- GAME AGENT HOOK ---
        print("BRAIN HOOK REACHED")
        from jarvis_game_agent import GameAgentPlugin

        if GameAgentPlugin.is_relevant(user_input):
            print("\n[GAME AGENT ACTIVATED]\n")
            result = GameAgentPlugin.handle(user_input)
            return BrainResponse(
                spoken_text=result,
                raw_text=result,
                action=None,
            )

        self._history.append(Message(role="user", content=user_input))
        self._trim_history()
        # Build system prompt with vision context
        system = config.SYSTEM_PROMPT
        if self._vision:
            try:
                visual_ctx = self._vision.get_prompt_context()
                if visual_ctx:
                    system = f"{system} Current visual context: {visual_ctx}"
            except Exception:
                pass

        # Build conversation for LLM
        prompt = self._build_prompt(user_input)

        # Notify widget — thinking
        try:
            from jarvis_widget import notify
            notify("thinking")
        except Exception:
            pass

        # Ask LLM engine (auto-selects best available tier)
        llm_response: LLMResponse = self._engine.ask(prompt, system=system)

        # Notify widget — done thinking
        try:
            from jarvis_widget import notify
            notify("idle")
        except Exception:
            pass
        raw = llm_response.text

        log.info("Response from %s (tier %d) in %.2fs",
                 llm_response.model, llm_response.tier, llm_response.latency)

        action, clean_text = extract_action(raw)
        spoken = sanitise_for_tts(clean_text) if clean_text else (
            "I'll take care of that." if action else
            "I'm not sure how to help with that."
        )

        self._history.append(Message(role="assistant", content=raw))
        self._save_conversation_log()

        return BrainResponse(
            spoken_text=spoken,
            raw_text=raw,
            action=action,
            model_used=llm_response.model,
            tier=llm_response.tier,
        )

    def think_quick(self, user_input: str) -> BrainResponse:
        """Use fast tiny model for simple commands."""
        system = config.SYSTEM_PROMPT
        llm_response = self._engine.ask_quick(user_input, system=system)
        raw = llm_response.text
        action, clean_text = extract_action(raw)
        spoken = sanitise_for_tts(clean_text) if clean_text else raw

        return BrainResponse(
            spoken_text=spoken, raw_text=raw,
            action=action, model_used=llm_response.model,
            tier=llm_response.tier,
        )

    def get_engine_status(self) -> str:
        """Return a human-readable status of LLM tiers."""
        status = self._engine.get_status()
        parts = []
        if status["groq"]:
            parts.append("Groq online")
        if status["ollama"]:
            parts.append(f"Ollama local ({status['models']['ollama']})")
        if not parts:
            parts.append("fallback mode only")
        return ", ".join(parts)

    def remember(self, key: str, value) -> None:
        self._preferences[key] = value
        self._save_preferences()

    def recall(self, key: str, default=None):
        return self._preferences.get(key, default)

    def clear_short_term(self) -> None:
        self._history.clear()
        log.info("Short-term memory cleared.")

    # ── Private ────────────────────────────────────────────────────────────────

    def _build_prompt(self, current_input: str) -> str:
        """Build prompt with recent conversation history."""
        if len(self._history) <= 1:
            return current_input

        # Include last few turns for context
        history_text = ""
        for msg in self._history[-6:-1]:  # Last 3 exchanges
            prefix = "User" if msg.role == "user" else "Jarvis"
            history_text += f"{prefix}: {msg.content}\n"

        return f"{history_text}User: {current_input}"

    def _trim_history(self) -> None:
        if len(self._history) > config.MAX_HISTORY_TURNS * 2:
            self._history = self._history[-(config.MAX_HISTORY_TURNS * 2):]

    def _load_preferences(self) -> None:
        path: Path = config.LONG_TERM_MEMORY_FILE
        if path.exists():
            try:
                self._preferences = json.loads(
                    path.read_text(encoding="utf-8")
                )
                log.info("Loaded %d user preferences.", len(self._preferences))
            except json.JSONDecodeError:
                self._preferences = {}

    def _save_preferences(self) -> None:
        config.LONG_TERM_MEMORY_FILE.write_text(
            json.dumps(self._preferences, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _save_conversation_log(self) -> None:
        try:
            log_data = [
                {"role": m.role, "content": m.content, "ts": m.timestamp}
                for m in self._history[-20:]
            ]
            config.CONVERSATION_LOG_FILE.write_text(
                json.dumps(log_data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            log.debug("Could not save conversation log: %s", exc)
