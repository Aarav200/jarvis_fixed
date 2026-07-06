"""
call_monitor.py — Monitor incoming calls from Discord and WhatsApp.
Uses window title detection + pixel color detection.
"""

import threading
import time

import pyautogui
import pygetwindow as gw
from PIL import ImageGrab
import numpy as np

from utils.logger import get_logger

log = get_logger(__name__)

_CHECK_INTERVAL = 1.0


def _get_discord_win():
    wins = [w for w in gw.getAllWindows()
            if "Discord" in w.title and w.width > 400]
    return wins[0] if wins else None


def _detect_discord_call() -> str:
    """
    Detect incoming Discord call by looking for the call popup.
    Discord shows a centered popup with caller name + red/green buttons.
    We detect the popup by scanning for the green accept button color.
    Returns caller name or empty string.
    """
    try:
        win = _get_discord_win()
        if not win:
            return ""

        # Screenshot the center area where Discord call popup appears
        # Based on screenshot: popup is roughly center of screen
        cx = win.left + win.width // 2
        cy = win.top + win.height // 2

        # Capture area around center (where popup appears)
        x1 = cx - 200
        y1 = cy - 150
        x2 = cx + 200
        y2 = cy + 150

        img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        img_np = np.array(img)

        # Look for the specific green color of Discord's accept button
        # Discord green: roughly RGB(87, 242, 135)
        green_mask = (
            (img_np[:,:,1] > 180) &   # high green
            (img_np[:,:,0] < 150) &   # lower red
            (img_np[:,:,2] < 180)     # lower blue
        )
        green_pixels = green_mask.sum()

        if green_pixels > 300:
            # Call popup detected! Now read the caller name via OCR
            try:
                import pytesseract
                # Capture just the name area (above center)
                name_img = ImageGrab.grab(bbox=(cx-150, cy-150, cx+150, cy-50))
                text = pytesseract.image_to_string(name_img).strip()
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                for line in lines:
                    if (len(line) > 1 and
                        not any(w in line.lower() for w in
                                ["incoming", "call", "discord", "cancel"])):
                        return line
            except Exception:
                pass
            return "someone"

    except Exception as e:
        log.debug("Discord call detection error: %s", e)
    return ""


def _detect_whatsapp_call() -> tuple[str, str]:
    """
    Detect incoming WhatsApp call popup.
    WhatsApp shows a small separate window with caller name.
    Window title is just "WhatsApp" but it's small (~460px wide).
    Returns (caller_name, call_type).
    """
    try:
        all_wins = gw.getAllWindows()
        for w in all_wins:
            if ("WhatsApp" in w.title and
                100 < w.width < 520 and
                100 < w.height < 520):

                # This looks like the call popup!
                # Read caller name via OCR from the window
                try:
                    import pytesseract
                    img = ImageGrab.grab(bbox=(
                        w.left, w.top, w.right, w.bottom
                    ))
                    img_np = np.array(img)
                    text = pytesseract.image_to_string(img).strip()
                    lines = [l.strip() for l in text.split('\n') if l.strip()]

                    caller = ""
                    call_type = "voice"

                    for line in lines:
                        if "video" in line.lower():
                            call_type = "video"
                        if (len(line) > 1 and
                            not any(w2 in line.lower() for w2 in
                                    ["whatsapp", "voice", "video", "call",
                                     "accept", "decline", "cancel", "...",
                                     "incoming"])):
                            caller = line
                            break

                    return caller or "someone", call_type
                except Exception:
                    return "someone", "voice"

    except Exception as e:
        log.debug("WhatsApp call detection: %s", e)
    return "", ""


def _accept_discord_call(win):
    """Click the green accept button in Discord call popup."""
    try:
        cx = win.left + win.width // 2
        cy = win.top + win.height // 2
        # Green button is slightly right of center based on screenshot
        pyautogui.click(cx + 35, cy + 30)
        log.info("Clicked Discord accept button")
    except Exception as e:
        log.error("Discord accept failed: %s", e)


def _decline_discord_call(win):
    """Click the red decline button in Discord call popup."""
    try:
        cx = win.left + win.width // 2
        cy = win.top + win.height // 2
        # Red button is left of center based on screenshot
        pyautogui.click(cx - 35, cy + 30)
        log.info("Clicked Discord decline button")
    except Exception as e:
        log.error("Discord decline failed: %s", e)


def _accept_whatsapp_call():
    """Click Accept button on WhatsApp call popup."""
    try:
        all_wins = gw.getAllWindows()
        for w in all_wins:
            if "WhatsApp" in w.title and 100 < w.width < 520:
                w.activate()
                time.sleep(0.3)
                # Accept button is green, at bottom center of popup
                accept_x = w.left + w.width // 2
                accept_y = w.top + int(w.height * 0.85)
                pyautogui.click(accept_x, accept_y)
                log.info("Clicked WhatsApp accept button")
                return
    except Exception as e:
        log.error("WhatsApp accept failed: %s", e)


def _decline_whatsapp_call():
    """Click Decline button on WhatsApp call popup."""
    try:
        all_wins = gw.getAllWindows()
        for w in all_wins:
            if "WhatsApp" in w.title and 100 < w.width < 520:
                w.activate()
                time.sleep(0.3)
                # Decline is red button, right side of bottom
                decline_x = w.left + int(w.width * 0.85)
                decline_y = w.top + int(w.height * 0.85)
                pyautogui.click(decline_x, decline_y)
                log.info("Clicked WhatsApp decline button")
                return
    except Exception as e:
        log.error("WhatsApp decline failed: %s", e)


def _monitor_discord_calls(voice_engine) -> None:
    log.info("Discord call monitor running.")
    call_active = False
    last_alert = 0
    detections = 0

    while True:
        try:
            caller = _detect_discord_call()

            if caller:
                detections += 1
            else:
                detections = 0
                call_active = False

            # Require 2 consecutive detections to avoid false positives
            if detections >= 2 and not call_active and (time.time() - last_alert) > 20:
                call_active = True
                last_alert = time.time()
                detections = 0
                log.info("Incoming Discord call from: %s", caller)

                # Tell Jarvis to expect direct response (no wake word)
                voice_engine.expect_response()
                voice_engine.speak(
                    f"Sir, {caller} is calling on Discord. Say accept or decline."
                )

                response = voice_engine.get_utterance(timeout=15)
                log.info("Response: '%s'", response)

                win = _get_discord_win()
                if response and any(w in response.lower() for w in
                                   ["accept", "yes", "sure", "okay",
                                    "pick", "answer", "take"]):
                    if win:
                        win.activate()
                        time.sleep(0.3)
                        _accept_discord_call(win)
                    voice_engine.speak("Call accepted.")
                else:
                    if win:
                        win.activate()
                        time.sleep(0.3)
                        _decline_discord_call(win)
                    voice_engine.speak("Call declined.")

                call_active = False

            time.sleep(_CHECK_INTERVAL)

        except Exception as e:
            log.debug("Discord monitor: %s", e)
            time.sleep(3)


def _monitor_whatsapp_calls(voice_engine) -> None:
    log.info("WhatsApp call monitor running.")
    call_active = False
    last_alert = 0
    detections = 0

    while True:
        try:
            caller, call_type = _detect_whatsapp_call()

            if caller:
                detections += 1
            else:
                detections = 0
                call_active = False

            if detections >= 2 and not call_active and (time.time() - last_alert) > 20:
                call_active = True
                last_alert = time.time()
                detections = 0
                log.info("Incoming WhatsApp %s call from: %s", call_type, caller)

                voice_engine.expect_response()
                voice_engine.speak(
                    f"Sir, {caller} is {call_type} calling on WhatsApp. "
                    f"Say accept or decline."
                )

                response = voice_engine.get_utterance(timeout=15)
                log.info("Response: '%s'", response)

                if response and any(w in response.lower() for w in
                                   ["accept", "yes", "sure", "okay",
                                    "pick", "answer", "take"]):
                    _accept_whatsapp_call()
                    voice_engine.speak("Call accepted.")
                else:
                    _decline_whatsapp_call()
                    voice_engine.speak("Call declined.")

                call_active = False

            time.sleep(_CHECK_INTERVAL)

        except Exception as e:
            log.debug("WhatsApp monitor: %s", e)
            time.sleep(3)


def start_all_monitors(voice_engine) -> None:
    threading.Thread(
        target=_monitor_discord_calls,
        args=(voice_engine,),
        daemon=True,
        name="discord-monitor"
    ).start()
    log.info("Discord call monitor started.")

    threading.Thread(
        target=_monitor_whatsapp_calls,
        args=(voice_engine,),
        daemon=True,
        name="whatsapp-monitor"
    ).start()
    log.info("WhatsApp call monitor started.")
