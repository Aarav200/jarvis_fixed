"""
asset_intent.py
===============
Detects "create asset" intents from voice commands.
No LLM call — pure keyword matching for speed.

Used by: command_router.py  OR  brain.py think()
"""

import re
from typing import Optional, Tuple

# ── Canonical name → spec file stem ──────────────────────────
ASSET_MAP = {
    # trees
    "pine tree":      "pine_tree",
    "pine":           "pine_tree",
    "fir tree":       "pine_tree",
    "fir":            "pine_tree",
    "oak tree":       "oak_tree",
    "oak":            "oak_tree",
    "tree":           "pine_tree",   # default tree = pine
    # rocks
    "rock":           "small_rock",
    "small rock":     "small_rock",
    "stone":          "small_rock",
    "boulder":        "large_boulder",
    "large boulder":  "large_boulder",
    "big rock":       "large_boulder",
    # weapons
    "fantasy sword":  "fantasy_sword",
    "magic sword":    "fantasy_sword",
    "enchanted sword":"fantasy_sword",
    "medieval sword": "medieval_sword",
    "sword":          "medieval_sword",  # default sword = medieval
    "blade":          "medieval_sword",
    # vehicles
    "car":            "compact_car",
    "compact car":    "compact_car",
    "vehicle":        "compact_car",
    # buildings
    "house":          "small_house",
    "small house":    "small_house",
    "cottage":        "small_house",
    "building":       "small_house",
    "home":           "small_house",
    "cabin":          "small_house",
}

# ── Trigger verbs that signal creation intent ─────────────────
CREATE_VERBS = [
    "create", "make", "generate", "build",
    "spawn", "add", "model", "give me"
]

# ── Precompiled pattern ───────────────────────────────────────
_VERB_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(v) for v in CREATE_VERBS) + r")\b",
    re.IGNORECASE
)


def detect_asset_intent(command: str) -> Tuple[bool, Optional[str]]:
    """
    Returns (is_asset_command, spec_name_or_None).

    Examples:
        "Jarvis create a pine tree"    → (True, "pine_tree")
        "create an oak"                → (True, "oak_tree")
        "make a fantasy sword"         → (True, "fantasy_sword")
        "what is the weather"          → (False, None)
    """
    text = command.lower().strip()

    # Must contain a creation verb
    if not _VERB_PATTERN.search(text):
        return False, None

    # Try longest match first so "large boulder" beats "boulder"
    sorted_assets = sorted(ASSET_MAP.keys(), key=len, reverse=True)
    for asset_phrase in sorted_assets:
        if asset_phrase in text:
            return True, ASSET_MAP[asset_phrase]

    return False, None


def spoken_name(spec_name: str) -> str:
    """Convert spec name to readable spoken form."""
    return spec_name.replace("_", " ")
