"""
tests/test_core.py — Unit tests for Jarvis core modules.

Run: pytest tests/
"""

import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ─── Text helpers ─────────────────────────────────────────────────────────────

from utils.text_helpers import extract_action, sanitise_for_tts


def test_extract_action_present():
    text = "Sure, opening Chrome for you. [ACTION:open_app|chrome]"
    action, clean = extract_action(text)
    assert action is not None
    assert action.command == "open_app"
    assert action.param == "chrome"
    assert "[ACTION:" not in clean


def test_extract_action_absent():
    text = "The capital of France is Paris."
    action, clean = extract_action(text)
    assert action is None
    assert clean == text


def test_extract_action_no_param():
    text = "[ACTION:get_time|]"
    action, clean = extract_action(text)
    assert action is not None
    assert action.command == "get_time"
    assert action.param == ""


def test_sanitise_markdown():
    text = "Here is **bold** and `code` and https://example.com"
    result = sanitise_for_tts(text)
    assert "**" not in result
    assert "`" not in result
    assert "https" not in result
    assert "bold" in result
    assert "code" in result


# ─── Command registry ─────────────────────────────────────────────────────────

import commands


def test_commands_registered():
    cmds = commands.list_commands()
    assert "open_app" in cmds
    assert "web_search" in cmds
    assert "wikipedia" in cmds
    assert "set_volume" in cmds
    assert "play_music" in cmds
    assert "get_time" in cmds
    assert "get_date" in cmds


def test_get_handler_known():
    handler = commands.get_handler("get_time")
    assert callable(handler)


def test_get_handler_unknown():
    handler = commands.get_handler("nonexistent_xyz")
    assert handler is None


# ─── System commands (no hardware required) ───────────────────────────────────

from commands.system_commands import get_time, get_date


def test_get_time_returns_string():
    result = get_time("")
    assert isinstance(result, str)
    assert len(result) > 0


def test_get_date_returns_string():
    result = get_date("")
    assert isinstance(result, str)
    assert len(result) > 0


# ─── CommandRouter ────────────────────────────────────────────────────────────

from command_router import CommandRouter
from utils.text_helpers import ParsedAction


def test_router_known_command():
    router = CommandRouter()
    action = ParsedAction(command="get_time", param="", original_tag="[ACTION:get_time|]")
    result = router.dispatch(action)
    assert isinstance(result, str)
    assert len(result) > 0


def test_router_unknown_command():
    router = CommandRouter()
    action = ParsedAction(command="__unknown__", param="", original_tag="")
    result = router.dispatch(action)
    assert "don't know" in result.lower() or "unknown" in result.lower() or "__unknown__" in result


# ─── Brain (offline / no API key) ─────────────────────────────────────────────

import config

_orig_key = config.OPENAI_API_KEY


def test_brain_offline_fallback(monkeypatch):
    """Brain should return a graceful response when API key is missing."""
    monkeypatch.setattr(config, "OPENAI_API_KEY", "")
    from brain import Brain
    brain = Brain()
    resp = brain.think("hello")
    assert isinstance(resp.spoken_text, str)
    assert len(resp.spoken_text) > 0


def test_brain_empty_input(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_API_KEY", "")
    from brain import Brain
    brain = Brain()
    resp = brain.think("   ")
    assert resp.action is None
    assert resp.spoken_text


# ─── Plugin loader ────────────────────────────────────────────────────────────

from plugins import PluginLoader
from pathlib import Path
import tempfile


def test_plugin_loader_missing_dir():
    loader = PluginLoader(Path("/nonexistent/dir"))
    count = loader.load_all()
    assert count == 0


def test_plugin_loader_loads_plugin():
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_path = Path(tmpdir) / "test_plugin.py"
        plugin_path.write_text(
            "from commands import register_command\n"
            "@register_command('__test_plugin_cmd__')\n"
            "def _handler(p): return 'ok'\n"
        )
        loader = PluginLoader(Path(tmpdir))
        count = loader.load_all()
        assert count == 1
        handler = commands.get_handler("__test_plugin_cmd__")
        assert callable(handler)
        assert handler("") == "ok"
