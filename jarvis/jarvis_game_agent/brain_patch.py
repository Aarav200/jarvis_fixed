"""
brain_patch.py
==============
This file shows EXACTLY what to add to brain.py.
It is NOT a replacement — it is a surgical patch guide.

WHAT TO ADD: 8 lines inside think(), before the LLM call.
WHERE:       After the empty-input guard, before self._history.append(...)
"""


# ══════════════════════════════════════════════════════════════
# STEP 1 — Find this block in your brain.py (around line 71-78):
# ══════════════════════════════════════════════════════════════

FIND_THIS = """
    def think(self, user_input: str) -> BrainResponse:
        \"\"\"Process input and return a response.\"\"\"
        if not user_input.strip():
            return BrainResponse(
                spoken_text="I didn't catch that. Could you repeat?",
                raw_text="", action=None,
            )

        self._history.append(Message(role="user", content=user_input))
"""

# ══════════════════════════════════════════════════════════════
# STEP 2 — Replace with this (adds 8 lines, nothing else changes):
# ══════════════════════════════════════════════════════════════

REPLACE_WITH = """
    def think(self, user_input: str) -> BrainResponse:
        \"\"\"Process input and return a response.\"\"\"
        if not user_input.strip():
            return BrainResponse(
                spoken_text="I didn't catch that. Could you repeat?",
                raw_text="", action=None,
            )

        # ── ASSET CREATION HOOK (8 lines) ────────────────────
        try:
            from plugins.asset_creation_plugin import try_handle_asset
            asset_response = try_handle_asset(user_input, self)
            if asset_response:
                return BrainResponse(
                    spoken_text=asset_response,
                    raw_text=asset_response,
                    action=None,
                )
        except Exception as _ae:
            pass  # never break existing Jarvis on import failure
        # ─────────────────────────────────────────────────────

        self._history.append(Message(role="user", content=user_input))
"""

# ══════════════════════════════════════════════════════════════
# STEP 3 (OPTIONAL) — Auto-apply the patch programmatically
# Run:  python brain_patch.py path/to/brain.py
# ══════════════════════════════════════════════════════════════

import sys
import pathlib
import re


HOOK_CODE = """\
        # ── ASSET CREATION HOOK (8 lines) ────────────────────
        try:
            from plugins.asset_creation_plugin import try_handle_asset
            asset_response = try_handle_asset(user_input, self)
            if asset_response:
                return BrainResponse(
                    spoken_text=asset_response,
                    raw_text=asset_response,
                    action=None,
                )
        except Exception as _ae:
            pass  # never break existing Jarvis on import failure
        # ─────────────────────────────────────────────────────\n"""

# Marker so we never double-patch
ALREADY_PATCHED_MARKER = "ASSET CREATION HOOK"

# The line we insert BEFORE
INSERT_BEFORE = "self._history.append(Message(role="


def patch_brain(brain_path: str):
    path = pathlib.Path(brain_path)
    if not path.exists():
        print(f"[PATCH] File not found: {brain_path}")
        sys.exit(1)

    original = path.read_text(encoding="utf-8")

    if ALREADY_PATCHED_MARKER in original:
        print("[PATCH] brain.py is already patched. Nothing to do.")
        return

    # Find the insertion point inside think()
    lines = original.splitlines(keepends=True)
    insert_at = None

    for i, line in enumerate(lines):
        if INSERT_BEFORE in line and "user_input" in line:
            # Make sure we're inside think() — look back for def think
            context = "".join(lines[max(0, i-20):i])
            if "def think" in context:
                insert_at = i
                break

    if insert_at is None:
        print("[PATCH] Could not locate insertion point in brain.py.")
        print(f"        Looking for:  {INSERT_BEFORE!r}  inside think()")
        print("        Add the hook manually — see REPLACE_WITH in this file.")
        sys.exit(1)

    # Detect indentation of the target line
    target_line = lines[insert_at]
    indent = len(target_line) - len(target_line.lstrip())
    hook   = "\n".join(" " * indent + l if l.strip() else l
                        for l in HOOK_CODE.splitlines()) + "\n"

    lines.insert(insert_at, hook)
    patched = "".join(lines)

    # Write backup then patch
    backup = path.with_suffix(".py.bak")
    backup.write_text(original, encoding="utf-8")
    path.write_text(patched, encoding="utf-8")

    print(f"[PATCH] ✅ brain.py patched successfully.")
    print(f"[PATCH]    Backup saved to: {backup}")
    print(f"[PATCH]    Hook inserted at line {insert_at + 1}.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:  python brain_patch.py path/to/brain.py")
        print()
        print("This script auto-patches brain.py to add the asset creation hook.")
        print("A backup is saved as brain.py.bak before any changes.")
        sys.exit(0)

    patch_brain(sys.argv[1])
