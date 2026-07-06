"""
BaseAgent
=========
All 7 agents inherit from this.
Provides: LLM calling, logging, memory access, structured output.
"""

import json
import logging
import re
import datetime
import pathlib
from typing import Any, Dict, Optional


class BaseAgent:
    NAME = "base"
    ROLE = "Generic agent"

    def __init__(self, memory_manager=None, llm_caller=None):
        self.memory = memory_manager
        self._llm   = llm_caller   # injected by ManagerAgent
        self.log    = logging.getLogger(f"jarvis.game_agent.{self.NAME}")
        self._log_dir = pathlib.Path(__file__).parent.parent / "logs"
        self._log_dir.mkdir(exist_ok=True)

    # ─────────────────────────────────────────
    # LLM
    # ─────────────────────────────────────────

    def ask_llm(self, prompt: str, system: str = None,
                expect_json: bool = False) -> Any:
        """
        Call the LLM through whatever provider Jarvis uses.
        Falls back to a stub if no LLM is connected.
        """
        if self._llm:
            response = self._llm(prompt, system=system)
        else:
            self.log.warning("[%s] No LLM connected — using stub response", self.NAME)
            response = self._stub_response(prompt)

        if expect_json:
            return self._parse_json(response)
        return response

    def _stub_response(self, prompt: str) -> str:
        """Placeholder when no LLM is connected (for testing)."""
        return json.dumps({
            "status": "stub",
            "note": "Connect an LLM to get real responses.",
            "prompt_preview": prompt[:100]
        })

    def _parse_json(self, text: str) -> Dict:
        # Strip markdown fences if present
        text = re.sub(r"```json|```", "", text).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            self.log.warning("[%s] Could not parse JSON from LLM response", self.NAME)
            return {"raw": text}

    # ─────────────────────────────────────────
    # LOGGING
    # ─────────────────────────────────────────

    def save_log(self, task: str, result: Dict):
        ts    = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        fname = self._log_dir / f"{self.NAME}_{ts}.json"
        entry = {
            "agent":  self.NAME,
            "task":   task,
            "result": result,
            "time":   ts
        }
        with open(fname, "w") as f:
            json.dump(entry, f, indent=2)

    # ─────────────────────────────────────────
    # OVERRIDE IN SUBCLASSES
    # ─────────────────────────────────────────

    def run(self, task: str, context: Dict = None) -> Dict:
        raise NotImplementedError(f"{self.NAME}.run() not implemented")

    def get_memory_context(self) -> str:
        if self.memory:
            return self.memory.build_context_summary()
        return ""
