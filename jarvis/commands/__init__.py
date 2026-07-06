from __future__ import annotations
from typing import Callable

_registry: dict[str, Callable[[str], str]] = {}

def register_command(name: str):
    def decorator(fn: Callable[[str], str]):
        _registry[name] = fn
        return fn
    return decorator

def get_handler(name: str) -> Callable[[str], str] | None:
    return _registry.get(name)

def list_commands() -> list[str]:
    return sorted(_registry.keys())

from . import (  # noqa: E402, F401
    app_commands,
    web_commands,
    music_commands,
    knowledge_commands,
    system_commands,
    custom_commands,
    whatsapp_commands,
    discord_commands,
    vision_commands,
    
)
