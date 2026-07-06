"""
config.py — Central configuration for Jarvis.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
LOGS_DIR = BASE_DIR / "logs"
MEMORY_DIR = BASE_DIR / "memory"
PLUGINS_DIR = BASE_DIR / "plugins"

LOGS_DIR.mkdir(exist_ok=True)
MEMORY_DIR.mkdir(exist_ok=True)

# API Keys
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

# Wake Word
WAKE_WORD: str = "hey jarvis"
WAKE_WORD_SENSITIVITY: float = 0.5

# Whisper
WHISPER_MODEL: str = "medium"
WHISPER_LANGUAGE: str = "en"
RECORD_SAMPLE_RATE: int = 44100
RECORD_CHANNELS: int = 1
SILENCE_THRESHOLD: float = 0.001
SILENCE_DURATION: float = 1.5
MAX_RECORD_SECONDS: int = 30

# TTS
TTS_ENGINE: str = "edge"
TTS_RATE: int = 175
TTS_VOLUME: float = 0.9
TTS_VOICE_INDEX: int = 0

# LLM
LLM_MODEL: str = "llama-3.3-70b-versatile"
LLM_TEMPERATURE: float = 0.7
LLM_MAX_TOKENS: int = 512

SYSTEM_PROMPT: str = (
    "You are Jarvis, a concise AI voice assistant. "
    "Respond in 1-2 sentences max. "
    "For actions, use ONLY these EXACT command tags — do not invent new command names: "
    "[ACTION:open_app|appname] "
    "[ACTION:web_search|query] "
    "[ACTION:play_music|song] "
    "[ACTION:get_time|] "
    "[ACTION:get_date|] "
    "[ACTION:set_volume|0-100] "
    "[ACTION:wikipedia|topic] "
    "[ACTION:whatsapp_message|contact|message] "
    "[ACTION:whatsapp_call|contact] "
    "[ACTION:whatsapp_video|contact] "
    "[ACTION:discord_message|contact|message] "
    "[ACTION:discord_call|contact] "
    "[ACTION:discord_video|contact] "
    "[ACTION:what_do_you_see|] "
    "[ACTION:what_am_i_doing|] "
    "[ACTION:am_i_productive|] "
    "[ACTION:show_news|] — show world news map. "
    "CRITICAL RULES: "
    "1. For time ALWAYS use [ACTION:get_time|] — never display_time, show_time, current_time. "
    "2. For WhatsApp messages ALWAYS use [ACTION:whatsapp_message|name|message] — never send_message. "
    "3. For opening apps ALWAYS use [ACTION:open_app|name] — never launch_app or start_app. "
    "4. Never invent command names not listed above. "
    "Otherwise reply naturally."
)

# Memory
MAX_HISTORY_TURNS: int = 20
LONG_TERM_MEMORY_FILE: Path = MEMORY_DIR / "user_preferences.json"
CONVERSATION_LOG_FILE: Path = MEMORY_DIR / "conversation_history.json"

# Commands
DEFAULT_BROWSER: str = "chrome"
DEFAULT_EDITOR: str = "code"
MUSIC_PLAYER: str = "youtube"

APP_MAP: dict[str, list[str]] = {
    "chrome":    ["chrome", "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"],
    "firefox":   ["firefox"],
    "code":      ["code"],
    "vscode":    ["code"],
    "terminal":  ["cmd"],
    "notepad":   ["notepad"],
    "spotify":   ["spotify", "C:\\Users\\achaw\\AppData\\Roaming\\Spotify\\Spotify.exe"],
    "valorant":  ["C:\\Riot Games\\VALORANT\\live\\VALORANT.exe"],
    "vlc":       ["vlc"],
    "explorer":  ["explorer"],
}

# Logging
LOG_LEVEL: str = "INFO"
LOG_FILE: Path = LOGS_DIR / "jarvis.log"
LOG_MAX_BYTES: int = 5 * 1024 * 1024
LOG_BACKUP_COUNT: int = 3
