"""
commands/app_commands.py — Open desktop applications.
Auto-discovers installed apps from Windows Start Menu and registry.
"""

import os
import glob
import shutil
import subprocess
import winreg
from pathlib import Path

import config
from commands import register_command
from utils.logger import get_logger

log = get_logger(__name__)

# ── Auto-discovery: scan Start Menu for .lnk shortcuts ───────────────────────

def _build_app_index() -> dict[str, str]:
    """
    Scan Windows Start Menu folders and return a dict of
    lowercase_app_name -> full_path_to_exe_or_lnk
    """
    index = {}

    start_menu_dirs = [
        os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
        r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
    ]

    for folder in start_menu_dirs:
        for lnk in glob.glob(os.path.join(folder, "**", "*.lnk"), recursive=True):
            name = Path(lnk).stem.lower()
            index[name] = lnk

    # Also add known executables from config.APP_MAP as fallback
    for key, candidates in config.APP_MAP.items():
        for exe in candidates:
            if os.path.exists(exe) or shutil.which(exe):
                index[key] = exe
                break

    log.info("App index built: %d apps found.", len(index))
    return index


# Build index once at import time
_APP_INDEX: dict[str, str] = _build_app_index()


def _find_best_match(query: str) -> str | None:
    """
    Find the best matching app path for a query string.
    Tries exact match first, then partial match.
    """
    query = query.lower().strip()

    # Exact match
    if query in _APP_INDEX:
        return _APP_INDEX[query]

    # Partial match — find all apps whose name contains the query
    matches = [(name, path) for name, path in _APP_INDEX.items()
               if query in name]

    if not matches:
        # Try reverse — query contains the app name
        matches = [(name, path) for name, path in _APP_INDEX.items()
                   if name in query]

    if matches:
        # Pick shortest name match (most specific)
        matches.sort(key=lambda x: len(x[0]))
        return matches[0][1]

    return None


def _launch(path: str) -> bool:
    """Launch an app by path (.lnk or .exe)."""
    try:
        os.startfile(path)
        return True
    except Exception as e:
        log.debug("os.startfile failed for '%s': %s", path, e)

    try:
        subprocess.Popen(
            [path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception as e:
        log.debug("Popen failed for '%s': %s", path, e)

    return False


@register_command("open_app")
def open_app(app_name: str) -> str:
    """
    Open any installed application by name.
    Auto-discovers from Start Menu — no manual config needed.
    """
    path = _find_best_match(app_name)

    if path and _launch(path):
        log.info("Opened: %s -> %s", app_name, path)
        return f"Opening {app_name}."

    # Last resort: try shutil.which
    exe = shutil.which(app_name.lower())
    if exe and _launch(exe):
        return f"Opening {app_name}."

    log.warning("Could not find application: %s", app_name)
    return (f"I couldn't find {app_name}. "
            f"Make sure it's installed and has a Start Menu shortcut.")