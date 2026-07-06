"""
llm_engine.py — Multi-tier LLM engine for Jarvis.

Priority order:
  1. Groq API      — fastest, online
  2. Ollama local  — offline, GPU-accelerated
  3. Ollama tiny   — offline, instant responses
  4. Rule-based    — always works, no model needed

Automatically falls back through tiers based on availability.
"""

import time
import threading
from dataclasses import dataclass
from typing import Optional
from utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class LLMResponse:
    text: str
    model: str          # which model responded
    tier: int           # 1=groq, 2=ollama, 3=tiny, 4=rules
    latency: float      # seconds


class LLMEngine:
    """
    Multi-tier LLM engine with automatic fallback.
    
    Usage:
        engine = LLMEngine()
        response = engine.ask("What time is it?", context="...")
    """

    # Quick commands that don't need a full LLM
    RULE_BASED = {
        "hello": "Hello sir, how can I help?",
        "hi": "Hi sir, what can I do for you?",
        "hey": "Yes sir?",
        "thanks": "You're welcome, sir.",
        "thank you": "Happy to help, sir.",
        "good morning": "Good morning sir! Ready to assist.",
        "good night": "Good night sir. Have a restful sleep.",
        "bye": "Goodbye sir.",
        "stop": "__STOP__",
    }

    def __init__(self, api_key: str = "", groq_model: str = "llama-3.3-70b-versatile") -> None:
        self._api_key = api_key
        self._groq_model = groq_model
        self._ollama_model = "llama3.2"
        self._ollama_tiny = "llama3.2:1b"
        self._online = True           # track connectivity
        self._groq_client = None
        self._ollama_client = None
        self._lock = threading.Lock()

        self._init_groq()
        self._init_ollama()

    # ── Public API ─────────────────────────────────────────────────────────────

    def ask(self, prompt: str, system: str = "", context: str = "") -> LLMResponse:
        """
        Ask the LLM a question. Tries tiers in order until one succeeds.
        """
        # Tier 4: Rule-based for simple inputs
        rule = self._check_rules(prompt)
        if rule:
            return LLMResponse(text=rule, model="rules", tier=4, latency=0.0)

        full_system = system
        if context:
            full_system = f"{system} {context}".strip()

        messages = [{"role": "user", "content": prompt}]

        # Tier 1: Groq (online)
        if self._online and self._groq_client and self._api_key:
            try:
                t = time.time()
                response = self._ask_groq(messages, full_system)
                latency = time.time() - t
                log.info("Groq response in %.2fs", latency)
                return LLMResponse(
                    text=response, model=f"groq/{self._groq_model}",
                    tier=1, latency=latency
                )
            except Exception as e:
                log.warning("Groq failed: %s — trying Ollama", e)
                if "401" in str(e) or "403" in str(e):
                    self._online = False  # Bad API key, don't retry

        # Tier 2: Ollama full model (offline)
        if self._ollama_client:
            try:
                t = time.time()
                response = self._ask_ollama(messages, full_system, self._ollama_model)
                latency = time.time() - t
                log.info("Ollama (%s) response in %.2fs", self._ollama_model, latency)
                return LLMResponse(
                    text=response, model=f"ollama/{self._ollama_model}",
                    tier=2, latency=latency
                )
            except Exception as e:
                log.warning("Ollama full failed: %s — trying tiny", e)

        # Tier 3: Ollama tiny (offline, fast)
        if self._ollama_client:
            try:
                t = time.time()
                response = self._ask_ollama(messages, full_system, self._ollama_tiny)
                latency = time.time() - t
                log.info("Ollama tiny response in %.2fs", latency)
                return LLMResponse(
                    text=response, model=f"ollama/{self._ollama_tiny}",
                    tier=3, latency=latency
                )
            except Exception as e:
                log.warning("Ollama tiny failed: %s", e)

        # Tier 4: Rule-based fallback
        return LLMResponse(
            text="I'm having trouble connecting to my AI backend right now, sir.",
            model="fallback", tier=4, latency=0.0
        )

    def ask_quick(self, prompt: str, system: str = "") -> LLMResponse:
        """
        Use the tiny model for speed — good for simple commands.
        Falls back to full model if tiny isn't available.
        """
        rule = self._check_rules(prompt)
        if rule:
            return LLMResponse(text=rule, model="rules", tier=4, latency=0.0)

        messages = [{"role": "user", "content": prompt}]

        if self._ollama_client:
            try:
                t = time.time()
                response = self._ask_ollama(messages, system, self._ollama_tiny)
                latency = time.time() - t
                return LLMResponse(
                    text=response, model=f"ollama/{self._ollama_tiny}",
                    tier=3, latency=latency
                )
            except Exception as e:
                log.debug("Quick model failed: %s", e)

        return self.ask(prompt, system)

    def is_online(self) -> bool:
        return self._online

    def is_ollama_available(self) -> bool:
        return self._ollama_client is not None

    def get_status(self) -> dict:
        return {
            "groq": bool(self._groq_client and self._api_key and self._online),
            "ollama": self.is_ollama_available(),
            "models": {
                "groq": self._groq_model,
                "ollama": self._ollama_model,
                "tiny": self._ollama_tiny,
            }
        }

    # ── Private: backends ──────────────────────────────────────────────────────

    def _init_groq(self) -> None:
        if not self._api_key:
            return
        try:
            from groq import Groq
            self._groq_client = Groq(api_key=self._api_key)
            log.info("Groq client initialized.")
        except ImportError:
            log.warning("groq package not installed.")

    def _init_ollama(self) -> None:
        try:
            import ollama
            # Test connection
            ollama.list()
            self._ollama_client = ollama
            log.info("Ollama connected. Models: %s, %s",
                     self._ollama_model, self._ollama_tiny)
        except Exception as e:
            log.warning("Ollama not available: %s", e)
            self._ollama_client = None

    def _ask_groq(self, messages: list, system: str) -> str:
        response = self._groq_client.chat.completions.create(
            model=self._groq_model,
            messages=[{"role": "system", "content": system}] + messages
            if system else messages,
            max_tokens=512,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()

    def _ask_ollama(self, messages: list, system: str, model: str) -> str:
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        response = self._ollama_client.chat(
            model=model,
            messages=full_messages,
            options={"temperature": 0.7, "num_predict": 256},
        )
        return response["message"]["content"].strip()

    def _check_rules(self, prompt: str) -> Optional[str]:
        """Check if prompt matches a simple rule-based response."""
        lower = prompt.lower().strip().rstrip(".,!?")
        return self.RULE_BASED.get(lower)
TIME_QUERIES = [
    "what time is it", "what is the time", "tell me the time",
    "what time it is", "can you tell me the time", "current time",
    "what's the time", "time please", "the time", "tell me time",
    "whats the time", "what the time", "give me the time",
]