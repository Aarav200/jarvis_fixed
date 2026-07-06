# Jarvis — Production-Ready Voice Assistant

A modular, extensible Python voice assistant with wake-word detection,
Whisper STT, GPT-4o reasoning, and a command plugin architecture.

---

## Project Structure

```
jarvis/
├── main.py                  # Controller loop (headless)
├── gui.py                   # Optional Tkinter dashboard
├── voice.py                 # Microphone capture, Whisper STT, TTS
├── brain.py                 # LLM integration + memory
├── command_router.py        # Dispatches actions to handlers
├── config.py                # All settings and API keys
│
├── commands/
│   ├── __init__.py          # Registry + auto-import
│   ├── app_commands.py      # Open applications
│   ├── web_commands.py      # Web search, open URL
│   ├── music_commands.py    # YouTube Music / YouTube
│   ├── knowledge_commands.py# Wikipedia lookups
│   ├── system_commands.py   # Volume, brightness, time/date
│   └── custom_commands.py   # User-defined commands
│
├── plugins/
│   ├── __init__.py          # Plugin loader
│   └── weather_plugin.py    # Example: weather command
│
├── utils/
│   ├── __init__.py
│   ├── logger.py            # Rotating file + console logger
│   ├── audio_helpers.py     # RMS, WAV, NumPy conversions
│   └── text_helpers.py      # Action tag parser, TTS sanitiser
│
├── memory/                  # Auto-created at runtime
│   ├── user_preferences.json
│   └── conversation_history.json
│
├── logs/                    # Auto-created at runtime
│   └── jarvis.log
│
├── tests/
│   └── test_core.py
│
├── requirements.txt
├── setup.py
└── .env.example
```

---

## Installation

### 1. Prerequisites

- Python 3.10+
- PortAudio (required by PyAudio)

```bash
# Ubuntu / Debian
sudo apt install portaudio19-dev python3-dev

# macOS
brew install portaudio

# Windows
# PyAudio wheel includes PortAudio; no separate install needed
```

### 2. Clone and create a virtual environment

```bash
git clone <repo-url> jarvis
cd jarvis
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

> Whisper also requires `ffmpeg` on your PATH:
> ```bash
> # Ubuntu
> sudo apt install ffmpeg
> # macOS
> brew install ffmpeg
> # Windows: download from https://ffmpeg.org/download.html
> ```

### 4. Set your API key

```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
export $(cat .env | xargs)
```

Or set it directly:
```bash
export OPENAI_API_KEY="sk-..."
```

---

## Running Jarvis

### Headless (terminal only)

```bash
python main.py
```

### With GUI dashboard

```bash
python gui.py
```

### Run tests

```bash
pip install pytest
pytest tests/ -v
```

---

## Usage

1. Wait for: **"Jarvis online. Say 'Hey Jarvis' followed by your command."**
2. Say **"Hey Jarvis"** followed by your request:

| Say | What happens |
|-----|-------------|
| Hey Jarvis, what time is it? | Tells you the time |
| Hey Jarvis, open Chrome | Launches Chrome |
| Hey Jarvis, search for Python tutorials | Opens Google search |
| Hey Jarvis, play Daft Punk | Opens YouTube Music search |
| Hey Jarvis, what is quantum computing? | Wikipedia summary |
| Hey Jarvis, set volume to 60 | Adjusts system volume |
| Hey Jarvis, good morning | Morning routine |
| Hey Jarvis, stop | Shuts down |

---

## Adding Custom Commands

### Option A: Edit `commands/custom_commands.py`

```python
from commands import register_command

@register_command("my_command")
def my_command(param: str) -> str:
    # Your logic here
    return "Done!"
```

### Option B: Drop a plugin file in `plugins/`

```python
# plugins/my_plugin.py
from commands import register_command

@register_command("weather")
def weather(city: str) -> str:
    ...
```

Plugins are auto-loaded at startup — no other changes needed.

---

## Configuration

All settings are in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `WAKE_WORD` | `"hey jarvis"` | Trigger phrase |
| `WHISPER_MODEL` | `"base"` | STT model size (tiny/base/small/medium/large) |
| `LLM_MODEL` | `"gpt-4o-mini"` | OpenAI model |
| `TTS_ENGINE` | `"pyttsx3"` | TTS backend |
| `MAX_HISTORY_TURNS` | `20` | Conversation context length |
| `SILENCE_THRESHOLD` | `0.02` | Mic sensitivity |

---

## Architecture Notes

### How commands work

The LLM is prompted to embed action tags in its response:

```
[ACTION:command_name|parameter]
```

For example, when you ask *"open Chrome"*, the LLM replies:

```
Sure, I'll open Chrome for you. [ACTION:open_app|chrome]
```

`brain.py` extracts this tag, `command_router.py` dispatches it to
`commands/app_commands.py`, and the result is spoken aloud.

### Memory

- **Short-term**: Last N conversation turns kept in RAM, sent with each API request for context.
- **Long-term**: Key/value preferences persisted to `memory/user_preferences.json` via `brain.remember(key, value)`.

### Plugin system

Any `.py` file in `plugins/` is auto-imported at startup. If it calls
`@register_command(...)`, the command becomes available immediately —
no changes to the core codebase required.

---

## Troubleshooting

**No audio input detected**
- Check microphone permissions
- Verify PortAudio installation: `python -c "import pyaudio; print('ok')"`
- Increase `SILENCE_THRESHOLD` in config.py if the mic is noisy

**Whisper is slow**
- Use `WHISPER_MODEL = "tiny"` for faster (less accurate) transcription
- On Mac with Apple Silicon, Whisper uses Metal acceleration automatically

**API errors**
- Verify `OPENAI_API_KEY` is set and valid
- Jarvis falls back to offline responses automatically

**TTS not working**
- On Linux, install: `sudo apt install espeak` (pyttsx3 backend)
- Alternatively switch to `TTS_ENGINE = "gtts"` and `pip install gTTS pygame`
