"""
command_router.py — Dispatches parsed actions to handlers.
Includes aliases for common LLM mistakes.
"""

from commands import get_handler
from utils.logger import get_logger
from utils.text_helpers import ParsedAction

log = get_logger(__name__)

# LLMs often generate wrong command names — map them to correct ones
COMMAND_ALIASES = {
    # Time/date
    "display_time":     "get_time",
    "show_time":        "get_time",
    "current_time":     "get_time",
    "tell_time":        "get_time",
    "time":             "get_time",
    "show_date":        "get_date",
    "current_date":     "get_date",
    "display_date":     "get_date",

    # WhatsApp
    "send_message":         "whatsapp_message",
    "send_whatsapp":        "whatsapp_message",
    "whatsapp_send":        "whatsapp_message",
    "send_text":            "whatsapp_message",
    "text_message":         "whatsapp_message",
    "send_whatsapp_message":"whatsapp_message",
    "make_call":            "whatsapp_call",
    "call":                 "whatsapp_call",
    "voice_call":           "whatsapp_call",
    "video_call":           "whatsapp_video",

    # Discord
    "send_discord":         "discord_message",
    "discord_send":         "discord_message",
    "discord_dm":           "discord_message",

    # Apps
    "launch_app":       "open_app",
    "start_app":        "open_app",
    "run_app":          "open_app",
    "open":             "open_app",

    # Search
    "search":           "web_search",
    "google":           "web_search",
    "search_web":       "web_search",
    "google_search":    "web_search",

    # Music
    "play":             "play_music",
    "play_song":        "play_music",
    "music":            "play_music",

    # Vision
    "what_do_i_see":    "what_do_you_see",
    "look":             "what_do_you_see",
    "see":              "what_do_you_see",
    "camera_view":      "what_do_you_see",

    # Volume
    "volume":           "set_volume",
    "change_volume":    "set_volume",

    # Wikipedia
    "wiki":             "wikipedia",
    "search_wiki":      "wikipedia",
    "lookup":           "wikipedia",
}


class CommandRouter:
    SIGNAL_STOP = "__STOP__"
    SIGNAL_CLEAR_MEMORY = "__CLEAR_MEMORY__"

    def dispatch(self, action: ParsedAction) -> str:
        command = action.command.strip()

        # Resolve alias if needed
        resolved = COMMAND_ALIASES.get(command, command)
        if resolved != command:
            log.info("Command alias: '%s' -> '%s'", command, resolved)
            command = resolved

        handler = get_handler(command)
        if handler is None:
            log.warning("Unknown command: '%s'", command)
            return f"I don't know how to execute the command '{action.command}' yet."

        try:
            log.info("Dispatching command '%s' with param '%s'",
                     command, action.param)
            result: str = handler(action.param)
            return result
        except Exception as exc:
            log.error("Command '%s' raised an exception: %s",
                      command, exc, exc_info=True)
            return f"Something went wrong while running '{command}'."
