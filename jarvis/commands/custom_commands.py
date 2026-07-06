"""
commands/custom_commands.py — User-defined shortcut commands.

Add your own commands here using the @register_command decorator.
Each function receives a string param and must return a string result.

Example:
    @register_command("morning_routine")
    def morning_routine(_: str) -> str:
        open_app("chrome")
        web_search("today's news")
        return "Good morning! Starting your routine."
"""

import time
import webbrowser

from commands import register_command
from utils.logger import get_logger

log = get_logger(__name__)


@register_command("good_morning")
def good_morning(_: str) -> str:
    """Kick off a morning routine."""
    hour = int(time.strftime("%H"))
    if hour < 12:
        greeting = "Good morning"
    elif hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    webbrowser.open("https://www.worldmonitor.app/?lat=20.1437&lon=0.0000&zoom=1.57&view=global&timeRange=7d&layers=conflicts%2Cbases%2Chotspots%2Cnuclear%2Csanctions%2Cweather%2Ceconomic%2Cwaterways%2Coutages%2Cmilitary%2Cnatural%2CiranAttacks")
    log.info("Morning routine triggered at hour %d", hour)
    return f"{greeting}! I've opened today's news for you."


@register_command("focus_mode")
def focus_mode(_: str) -> str:
    """Open a focus timer in the browser."""
    webbrowser.open("https://pomofocus.io")
    return "Focus mode activated. Pomodoro timer opened in your browser."


@register_command("clear_memory")
def clear_memory_command(_: str) -> str:
    """Placeholder — actual memory clearing is handled in main.py."""
    return "__CLEAR_MEMORY__"   # Signal handled by CommandRouter


@register_command("stop")
def stop_jarvis(_: str) -> str:
    """Signal Jarvis to shut down gracefully."""
    return "__STOP__"           # Signal handled by main.py


@register_command("help")
def show_help(_: str) -> str:
    """List available commands."""
    from commands import list_commands
    cmds = ", ".join(list_commands())
    return f"Available commands: {cmds}."
