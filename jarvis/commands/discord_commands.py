"""
commands/discord_commands.py — Control Discord desktop app via pyautogui.
Uses window-relative coordinates and a smart contacts system.
"""

import json
import subprocess
import threading
import time
from pathlib import Path

import pyautogui
import pygetwindow as gw

import config
from commands import register_command
from utils.logger import get_logger

log = get_logger(__name__)

pyautogui.PAUSE = 0.4
pyautogui.FAILSAFE = True

# ── Contacts system ───────────────────────────────────────────────────────────
CONTACTS_FILE = config.MEMORY_DIR / "discord_contacts.json"


def _load_contacts() -> dict:
    if CONTACTS_FILE.exists():
        try:
            return json.loads(CONTACTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_contacts(contacts: dict) -> None:
    CONTACTS_FILE.write_text(
        json.dumps(contacts, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def _resolve_contact(name: str) -> tuple[str, str]:
    """
    Resolve a spoken name to (display_name, exact_username).
    Returns (name, name) if not found in contacts.
    """
    contacts = _load_contacts()
    key = name.lower().strip()

    # Exact match
    if key in contacts:
        c = contacts[key]
        return c["display_name"], c["username"]

    # Partial match — find contact whose key starts with query
    for k, c in contacts.items():
        if k.startswith(key) or key.startswith(k):
            return c["display_name"], c["username"]

    # Not found — use as-is
    return name, name


# ── Window management ─────────────────────────────────────────────────────────

def _get_discord_window():
    """Find, maximize and activate Discord window."""
    try:
        windows = gw.getWindowsWithTitle("Discord")
        if not windows:
            subprocess.Popen(["explorer.exe",
                              "shell:AppsFolder\\Discord Inc.Discord"])
            time.sleep(4)
            windows = gw.getWindowsWithTitle("Discord")

        if windows:
            win = windows[0]
            win.maximize()
            win.activate()
            time.sleep(0.8)
            return win
    except Exception as e:
        log.error("Could not get Discord window: %s", e)
    return None


def _click_relative(win, rel_x: float, rel_y: float):
    """Click at position relative to window (0.0-1.0 fractions)."""
    x = win.left + int(win.width * rel_x)
    y = win.top + int(win.height * rel_y)
    pyautogui.click(x, y)
    return x, y


# ── Core actions ──────────────────────────────────────────────────────────────

def _open_dm(name: str) -> tuple[bool, str]:
    """
    Search for contact by exact username and open their DM.
    Returns (success, display_name).
    """
    display_name, username = _resolve_contact(name)
    log.info("Opening DM with %s (username: %s)", display_name, username)

    win = _get_discord_window()
    if not win:
        return False, display_name

    # Use Ctrl+K quick switcher with exact username
    pyautogui.hotkey("ctrl", "k")
    time.sleep(1.5)

    # Clear any existing text and type exact username
    pyautogui.hotkey("ctrl", "a")
    pyautogui.press("delete")
    time.sleep(0.3)

    # Type username character by character for accuracy
    for char in username:
        pyautogui.typewrite(char, interval=0.06)
    time.sleep(2.5)  # Wait for search results

    # Press Enter to select first result
    pyautogui.press("enter")
    time.sleep(1)
    return True, display_name


def _send_discord_message(name: str, message: str) -> None:
    try:
        success, display_name = _open_dm(name)
        if not success:
            return

        win = _get_discord_window()
        if not win:
            return

        # Click message box at bottom
        _click_relative(win, 0.55, 0.96)
        time.sleep(0.5)

        # Type message
        pyautogui.typewrite(message, interval=0.04)
        time.sleep(0.3)

        # Send
        pyautogui.press("enter")
        log.info("Discord message sent to %s: %s", display_name, message)

    except Exception as e:
        log.error("Discord message failed: %s", e)


def _make_discord_call(name: str, video: bool = False) -> None:
    try:
        success, display_name = _open_dm(name)
        if not success:
            return

        win = _get_discord_window()
        if not win:
            return

        # Voice = phone icon, Video = camera icon (top right of DM)
        if video:
            _click_relative(win, 0.915, 0.090)
        else:
            _click_relative(win, 0.885, 0.088)

        log.info("Discord %s call with %s",
                 "video" if video else "voice", display_name)

    except Exception as e:
        log.error("Discord call failed: %s", e)


def _add_contact(name: str, username: str) -> None:
    contacts = _load_contacts()
    contacts[name.lower()] = {
        "username": username,
        "display_name": name,
        "platform": "discord"
    }
    _save_contacts(contacts)
    log.info("Saved Discord contact: %s -> %s", name, username)


# ── Incoming call monitor ─────────────────────────────────────────────────────

def _monitor_incoming_calls(voice_engine) -> None:
    log.info("Discord call monitor running.")
    notified = set()

    while True:
        try:
            for title in gw.getAllTitles():
                lower = title.lower()
                if "incoming" in lower and title not in notified:
                    notified.add(title)
                    caller = (title.replace("Incoming call", "")
                              .replace("incoming call", "")
                              .replace("-", "").strip())
                    name = caller if caller else "someone"

                    voice_engine.speak(
                        f"Sir, {name} is calling you on Discord. "
                        f"Should I accept or decline?"
                    )

                    response = voice_engine.get_utterance(timeout=12)
                    if response:
                        if any(w in response.lower()
                               for w in ("accept", "yes", "sure", "okay")):
                            pyautogui.press("enter")
                            voice_engine.speak("Call accepted, sir.")
                        else:
                            pyautogui.press("esc")
                            voice_engine.speak("Call declined.")
                    notified.discard(title)

            time.sleep(1)

        except Exception as e:
            log.debug("Call monitor: %s", e)
            time.sleep(2)


def start_call_monitor(voice_engine, brain=None) -> None:
    threading.Thread(
        target=_monitor_incoming_calls,
        args=(voice_engine,),
        daemon=True,
        name="discord-monitor"
    ).start()


# ── Registered commands ───────────────────────────────────────────────────────

@register_command("discord_message")
def discord_message(param: str) -> str:
    if "|" not in param:
        return "Please say: send Discord message to [name] saying [message]"
    contact, message = param.split("|", 1)
    threading.Thread(
        target=_send_discord_message,
        args=(contact.strip(), message.strip()),
        daemon=True
    ).start()
    display, _ = _resolve_contact(contact.strip())
    return f"Sending Discord message to {display}."


@register_command("discord_call")
def discord_call(contact: str) -> str:
    if not contact:
        return "Who would you like to call on Discord?"
    threading.Thread(
        target=_make_discord_call,
        args=(contact.strip(), False),
        daemon=True
    ).start()
    display, _ = _resolve_contact(contact.strip())
    return f"Calling {display} on Discord."


@register_command("discord_video")
def discord_video(contact: str) -> str:
    if not contact:
        return "Who would you like to video call on Discord?"
    threading.Thread(
        target=_make_discord_call,
        args=(contact.strip(), True),
        daemon=True
    ).start()
    display, _ = _resolve_contact(contact.strip())
    return f"Starting video call with {display} on Discord."


@register_command("discord_add_contact")
def discord_add_contact(param: str) -> str:
    """Add a contact. param: name|username"""
    if "|" not in param:
        return "Please say: add [name] to Discord contacts with username [username]"
    name, username = param.split("|", 1)
    _add_contact(name.strip(), username.strip())
    return f"Got it! I've saved {name.strip()} as a Discord contact."
