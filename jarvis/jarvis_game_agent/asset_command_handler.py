"""
asset_command_handler.py
========================
Handles "create asset" voice commands.

- Starts generation in a background thread immediately.
- Returns spoken confirmation right away (doesn't block voice).
- Calls optional callback when export finishes.
- Integrates with Jarvis TTS if available.

Used by: command_router.py
"""

import threading
import logging
import time
import os
import sys
import pathlib
from typing import Optional, Callable

log = logging.getLogger("jarvis.asset_handler")

# ── Resolve ProceduralAssetAgent import path ──────────────────
# Works whether you run from jarvis/ root or any subdirectory.
_HERE = pathlib.Path(__file__).resolve().parent
_JARVIS_ROOT = _HERE.parent.parent          # jarvis/
_AGENT_PATH  = _JARVIS_ROOT / "jarvis_game_agent" / "blender" / "scripts"

if str(_AGENT_PATH) not in sys.path:
    sys.path.insert(0, str(_AGENT_PATH))

# Fallback: check sibling folder (standalone testing)
_ALT_PATH = _HERE.parent / "blender_scripts"
if str(_ALT_PATH) not in sys.path:
    sys.path.insert(0, str(_ALT_PATH))


class AssetCommandHandler:
    """
    Handles a single 'create <asset>' command.
    Call handle() — it returns immediately with a spoken string,
    then generates the asset in a background thread.
    """

    def __init__(self,
                 blender_exe = r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
                 tts_fn: Optional[Callable[[str], None]] = None):
        """
        blender_exe : path to blender executable (or just "blender" if in PATH)
        tts_fn      : optional function(text) that speaks the text aloud
                      e.g. tts_fn = jarvis.speak  or  tts_fn = voice_engine.say
        """
        self.blender_exe = blender_exe
        self.tts_fn      = tts_fn
        self._active_jobs: dict[str, threading.Thread] = {}

    # ─────────────────────────────────────────
    # PUBLIC
    # ─────────────────────────────────────────

    def handle(self, spec_name: str) -> str:
        """
        Start asset generation in background.
        Returns an immediate spoken confirmation string.
        """
        from asset_intent import spoken_name
        readable = spoken_name(spec_name)

        # Don't double-launch same asset
        if spec_name in self._active_jobs and self._active_jobs[spec_name].is_alive():
            return f"I'm already generating the {readable}. Give me a moment."

        # Kick off background thread
        t = threading.Thread(
            target=self._generate,
            args=(spec_name, readable),
            daemon=True,
            name=f"asset-{spec_name}"
        )
        self._active_jobs[spec_name] = t
        t.start()

        return (
            f"On it. Generating {readable} in Blender now. "
            f"I'll let you know when it's ready."
        )

    def is_busy(self, spec_name: str) -> bool:
        t = self._active_jobs.get(spec_name)
        return t is not None and t.is_alive()

    # ─────────────────────────────────────────
    # INTERNAL
    # ─────────────────────────────────────────

    def _generate(self, spec_name: str, readable: str):
        """Runs in background thread."""
        try:
            from jarvis_game_agent.blender.scripts.procedural_asset_agent import ProceduralAssetAgent
        except ImportError as e:
            msg = f"Could not import ProceduralAssetAgent: {e}"
            log.error("[AssetHandler] %s", msg)
            self._speak(f"Sorry, I couldn't start the asset generator. {msg}")
            return

        log.info("[AssetHandler] Starting generation: %s", spec_name)
        start = time.time()

        agent  = ProceduralAssetAgent(blender_exe=self.blender_exe)
        result = agent.create(spec_name)
        elapsed = round(time.time() - start, 1)

        if result.get("status") == "success":
            export_path = result.get("export_path", "unknown path")
            size_kb     = result.get("size_kb", 0)
            short_path  = self._shorten_path(export_path)

            log.info("[AssetHandler] ✅ %s done in %.1fs → %s", spec_name, elapsed, export_path)

            self._speak(
                f"{readable.title()} is ready. "
                f"Exported in {elapsed} seconds. "
                f"File saved to {short_path}."
            )
            # Also print to console so user can see full path
            print(f"\n[AssetHandler] ✅ {readable.title()} → {export_path}  ({size_kb} KB)\n")

        else:
            error = result.get("error", "unknown error")
            log.error("[AssetHandler] ❌ %s failed: %s", spec_name, error)
            self._speak(
                f"Sorry, I couldn't generate the {readable}. "
                f"The error was: {error}"
            )

    def _speak(self, text: str):
        """Speak via TTS if available, otherwise just log."""
        log.info("[AssetHandler] SPEAK: %s", text)
        if self.tts_fn:
            try:
                self.tts_fn(text)
            except Exception as e:
                log.warning("[AssetHandler] TTS failed: %s", e)

    @staticmethod
    def _shorten_path(path: str) -> str:
        """Return just the last two path segments for speech."""
        parts = pathlib.Path(path).parts
        if len(parts) >= 2:
            return str(pathlib.Path(*parts[-2:]))
        return path
