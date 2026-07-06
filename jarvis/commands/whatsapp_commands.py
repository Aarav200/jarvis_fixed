"""
commands/whatsapp_commands.py — WhatsApp via pyautogui.
Uses absolute coordinates + contacts file for accuracy.
"""

import json
import subprocess
import threading
import time

import pyautogui
import pygetwindow as gw

import config
from commands import register_command
from utils.logger import get_logger

log = get_logger(__name__)

pyautogui.PAUSE = 0.4
pyautogui.FAILSAFE = True

CONTACTS_FILE = config.MEMORY_DIR / "whatsapp_contacts.json"

# Absolute coordinates (from your screen measurements)
_SEARCH   = (160, 125)
_MSG_BOX  = (1462, 1042)
_SEND     = (1875, 1038)
_CALL_BTN = (1686, 79)
_VOICE    = (1455, 215)
_VIDEO    = (1642, 215)


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


def _resolve_contact(name: str) -> str:
    contacts = _load_contacts()
    key = name.lower().strip()
    if key in contacts:
        return contacts[key]
    for k, v in contacts.items():
        if key in k or k in key:
            return v
    return name


def _open_whatsapp() -> bool:
    try:
        wins = [w for w in gw.getAllWindows()
                if "WhatsApp" in w.title and w.width > 200]
        if wins:
            wins[0].activate()
            time.sleep(0.8)
            return True
        subprocess.Popen([
            "explorer.exe",
            "shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"
        ])
        time.sleep(5)
        wins = [w for w in gw.getAllWindows()
                if "WhatsApp" in w.title and w.width > 200]
        if wins:
            wins[0].activate()
            time.sleep(0.8)
            return True
    except Exception as e:
        log.error("Could not open WhatsApp: %s", e)
    return False


def _open_chat(contact: str) -> bool:
    exact = _resolve_contact(contact)
    log.info("Opening WhatsApp chat: '%s' (from '%s')", exact, contact)

    if not _open_whatsapp():
        return False

    # Click search bar
    pyautogui.click(_SEARCH)
    time.sleep(0.8)

    # Clear search box properly — triple click to select all text in search box
    # then delete, instead of Ctrl+A which selects all chats
    pyautogui.tripleClick(_SEARCH)
    time.sleep(0.3)
    pyautogui.press("delete")
    time.sleep(0.3)
    pyautogui.press("backspace")
    time.sleep(0.3)

    # Type contact name character by character
    for ch in exact:
        pyautogui.typewrite(ch, interval=0.06)
    time.sleep(2.0)

    # Press Enter to open first result
    pyautogui.press("enter")
    time.sleep(1.2)
    return True


def _send_whatsapp_message(contact: str, message: str) -> None:
    try:
        if not _open_chat(contact):
            return
        pyautogui.click(_MSG_BOX)
        time.sleep(0.5)
        pyautogui.typewrite(message, interval=0.05)
        time.sleep(0.4)
        pyautogui.click(_SEND)
        log.info("WhatsApp message sent to %s: %s", contact, message)
    except Exception as e:
        log.error("WhatsApp message failed: %s", e)


def _make_whatsapp_call(contact: str, video: bool = False) -> None:
    try:
        if not _open_chat(contact):
            return
        pyautogui.click(_CALL_BTN)
        time.sleep(1.5)
        if video:
            pyautogui.click(_VIDEO)
        else:
            pyautogui.click(_VOICE)
        log.info("WhatsApp %s call with %s",
                 "video" if video else "voice", contact)
    except Exception as e:
        log.error("WhatsApp call failed: %s", e)


@register_command("whatsapp_message")
def whatsapp_message(param: str) -> str:
    if "|" not in param:
        return "Please say who to message and what to say."
    contact, message = param.split("|", 1)
    contact = contact.strip()
    message = message.strip()
    threading.Thread(
        target=_send_whatsapp_message,
        args=(contact, message),
        daemon=True
    ).start()
    return f"Sending message to {_resolve_contact(contact)} on WhatsApp."


@register_command("whatsapp_call")
def whatsapp_call(contact: str) -> str:
    if not contact:
        return "Who would you like to call?"
    threading.Thread(
        target=_make_whatsapp_call,
        args=(contact.strip(), False),
        daemon=True
    ).start()
    return f"Calling {_resolve_contact(contact.strip())} on WhatsApp."


@register_command("whatsapp_video")
def whatsapp_video(contact: str) -> str:
    if not contact:
        return "Who would you like to video call?"
    threading.Thread(
        target=_make_whatsapp_call,
        args=(contact.strip(), True),
        daemon=True
    ).start()
    return f"Starting video call with {_resolve_contact(contact.strip())} on WhatsApp."


@register_command("whatsapp_add_contact")
def whatsapp_add_contact(param: str) -> str:
    if "|" not in param:
        return "Please provide the name and exact WhatsApp name."
    name, exact = param.split("|", 1)
    contacts = _load_contacts()
    contacts[name.strip().lower()] = exact.strip()
    _save_contacts(contacts)
    return f"Saved {exact.strip()} as a WhatsApp contact."
