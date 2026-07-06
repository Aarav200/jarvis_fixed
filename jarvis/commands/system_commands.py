"""
commands/system_commands.py — OS-level controls.

Volume and brightness control is OS-specific:
  • Linux  : amixer (audio), xrandr or brightnessctl (brightness)
  • macOS  : osascript (audio), brightness CLI (brightness)
  • Windows: pycaw (audio), wmi/screen_brightness_control (brightness)

Install optional dependencies for full support:
  pip install pycaw screen-brightness-control   # Windows
  brew install brightness                        # macOS
  apt install amixer brightnessctl               # Linux
"""

import platform
import subprocess
import time

from commands import register_command
from utils.logger import get_logger

log = get_logger(__name__)

_SYSTEM = platform.system()  # "Linux" | "Darwin" | "Windows"


# ─── Volume ───────────────────────────────────────────────────────────────────

def _set_volume_linux(level: int) -> bool:
    try:
        subprocess.run(
            ["amixer", "-q", "sset", "Master", f"{level}%"],
            check=True, capture_output=True,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def _set_volume_mac(level: int) -> bool:
    try:
        subprocess.run(
            ["osascript", "-e", f"set volume output volume {level}"],
            check=True, capture_output=True,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def _set_volume_windows(level: int) -> bool:
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMasterVolumeLevelScalar(level / 100.0, None)
        return True
    except Exception as e:
        log.debug("Windows volume error: %s", e)
        return False


@register_command("set_volume")
def set_volume(param: str) -> str:
    """
    Set system volume.
    param: integer 0–100, or "mute" / "unmute"
    """
    if param.lower() in ("mute", "unmute"):
        if _SYSTEM == "Linux":
            subprocess.run(["amixer", "-q", "sset", "Master", param.lower()],
                           capture_output=True)
        elif _SYSTEM == "Darwin":
            val = "0" if param.lower() == "mute" else "50"
            subprocess.run(["osascript", "-e", f"set volume output muted {'true' if param=='mute' else 'false'}"],
                           capture_output=True)
        return f"Volume {param}d."

    try:
        level = max(0, min(100, int(param)))
    except ValueError:
        return "Please give a volume level between 0 and 100."

    success = False
    if _SYSTEM == "Linux":
        success = _set_volume_linux(level)
    elif _SYSTEM == "Darwin":
        success = _set_volume_mac(level)
    elif _SYSTEM == "Windows":
        success = _set_volume_windows(level)

    if success:
        log.info("Volume set to %d%%", level)
        return f"Volume set to {level} percent."
    return "I couldn't adjust the volume on this system."


@register_command("volume_up")
def volume_up(_: str) -> str:
    if _SYSTEM == "Linux":
        subprocess.run(["amixer", "-q", "sset", "Master", "10%+"], capture_output=True)
        return "Volume increased."
    if _SYSTEM == "Darwin":
        subprocess.run(["osascript", "-e", "set volume output volume (output volume of (get volume settings) + 10)"],
                       capture_output=True)
        return "Volume increased."
    return "Volume up is not supported on this platform yet."


@register_command("volume_down")
def volume_down(_: str) -> str:
    if _SYSTEM == "Linux":
        subprocess.run(["amixer", "-q", "sset", "Master", "10%-"], capture_output=True)
        return "Volume decreased."
    if _SYSTEM == "Darwin":
        subprocess.run(["osascript", "-e", "set volume output volume (output volume of (get volume settings) - 10)"],
                       capture_output=True)
        return "Volume decreased."
    return "Volume down is not supported on this platform yet."


# ─── Brightness ────────────────────────────────────────────────────────────────

@register_command("set_brightness")
def set_brightness(param: str) -> str:
    """Set screen brightness. param: 0–100."""
    try:
        level = max(0, min(100, int(param)))
    except ValueError:
        return "Please provide a brightness level between 0 and 100."

    try:
        import screen_brightness_control as sbc
        sbc.set_brightness(level)
        log.info("Brightness set to %d%%", level)
        return f"Brightness set to {level} percent."
    except ImportError:
        pass

    if _SYSTEM == "Linux":
        try:
            subprocess.run(["brightnessctl", "s", f"{level}%"],
                           check=True, capture_output=True)
            return f"Brightness set to {level} percent."
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass

    return "Brightness control is not available. Install 'screen-brightness-control'."


# ─── Misc system commands ─────────────────────────────────────────────────────

@register_command("get_time")
def get_time(_: str) -> str:
    return f"The time is {time.strftime('%I:%M %p')}."


@register_command("get_date")
def get_date(_: str) -> str:
    return f"Today is {time.strftime('%A, %B %d, %Y')}."


@register_command("screenshot")
def take_screenshot(_: str) -> str:
    """Take a screenshot using available system tools."""
    try:
        import PIL.ImageGrab  # type: ignore
        import os
        path = os.path.expanduser("~/Desktop/screenshot.png")
        img = PIL.ImageGrab.grab()
        img.save(path)
        return f"Screenshot saved to {path}."
    except ImportError:
        if _SYSTEM == "Linux":
            subprocess.Popen(["scrot", "~/Desktop/screenshot.png"])
            return "Screenshot taken."
    return "Screenshot functionality requires 'Pillow' or 'scrot'."
