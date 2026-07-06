"""
Settings — loads config/game_agent_config.json
All paths, API keys, feature flags in one place.
"""

import json
import os
import pathlib

BASE_DIR = pathlib.Path(__file__).parent.parent  # jarvis_game_agent/


class Settings:
    # Paths
    BLENDER_EXECUTABLE = r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"
    UNITY_PROJECT_PATH   = "C:/Users/achaw/My project (8)"
    PROJECTS_DIR         = str(BASE_DIR / "projects")
    MEMORY_DIR           = str(BASE_DIR / "memory")
    LOGS_DIR             = str(BASE_DIR / "logs")

    # Unity Bridge
    UNITY_WS_PORT        = 6400
    UNITY_HTTP_PORT      = 6401

    # Blender
    BLENDER_TIMEOUT      = 120   # seconds

    # LLM (uses Jarvis's LLM by default — override here for standalone)
    LLM_PROVIDER         = "jarvis"   # "jarvis" | "openai" | "ollama"
    LLM_MODEL            = "gpt-4o"

    # Feature flags
    AUTO_IMPORT_UNITY    = True
    AUTO_FIX_CODE        = True
    MAX_FIX_RETRIES      = 5
    ENABLE_TESTING_AGENT = True

    # Art style defaults
    DEFAULT_ART_STYLE    = "low_poly"   # low_poly | realistic | stylized | pixel

    _loaded = False

    @classmethod
    def load(cls, path: str = None):
        config_path = path or str(BASE_DIR / "config" / "game_agent_config.json")
        if os.path.exists(config_path):
            with open(config_path) as f:
                data = json.load(f)
            for k, v in data.items():
                if hasattr(cls, k):
                    setattr(cls, k, v)
        cls._loaded = True

    @classmethod
    def save(cls):
        config_path = str(BASE_DIR / "config" / "game_agent_config.json")
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        data = {k: v for k, v in vars(cls).items()
                if not k.startswith("_") and not callable(v)}
        with open(config_path, "w") as f:
            json.dump(data, f, indent=2)
