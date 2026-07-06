"""
utils/text_helpers.py — Text parsing and sanitisation utilities.
"""

import re
from dataclasses import dataclass


# Matches [ACTION:command_name|param] as embedded in LLM replies
_ACTION_PATTERN = re.compile(r"\[ACTION:([a-zA-Z_]+)\|?([^\]]*)\]")


@dataclass
class ParsedAction:
    command: str
    param: str
    original_tag: str


def extract_action(text: str) -> tuple[ParsedAction | None, str]:
    """
    Find the first [ACTION:...] tag in *text*.
    Returns (ParsedAction, clean_text_without_tag) or (None, original_text).
    """
    match = _ACTION_PATTERN.search(text)
    if not match:
        return None, text

    action = ParsedAction(
        command=match.group(1).strip(),
        param=match.group(2).strip(),
        original_tag=match.group(0),
    )
    clean = text.replace(match.group(0), "").strip()
    return action, clean


def sanitise_for_tts(text: str) -> str:
    """Remove markdown, URLs, and symbols that sound bad when spoken."""
    # Strip markdown bold/italic
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text)
    # Strip inline code
    text = re.sub(r"`(.+?)`", r"\1", text)
    # Strip URLs
    text = re.sub(r"https?://\S+", "a link", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text
