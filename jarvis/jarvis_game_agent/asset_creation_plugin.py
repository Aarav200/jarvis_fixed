"""
asset_creation_plugin.py
========================
Drop this file into:  jarvis/plugins/asset_creation_plugin.py

Jarvis's PluginLoader will find and register it automatically.
No changes to main.py, brain.py, or command_router.py required
IF your PluginLoader calls plugin.can_handle(command) + plugin.handle(command).

If your PluginLoader uses a different interface, see the
MANUAL HOOK section at the bottom of this file.
"""

import logging
import pathlib
import sys

log = logging.getLogger("jarvis.plugin.asset_creation")

# ── Make sure our voice_integration folder is importable ──────
_PLUGIN_DIR  = pathlib.Path(__file__).resolve().parent          # jarvis/plugins/
_JARVIS_ROOT = _PLUGIN_DIR.parent                               # jarvis/
_VI_PATH     = _JARVIS_ROOT / "jarvis_game_agent" / "blender" / "scripts"  # agent scripts
_ALT_VI_PATH = _JARVIS_ROOT / "jarvis_game_agent" / "voice_integration"    # our new files

for p in [str(_VI_PATH), str(_ALT_VI_PATH)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Lazy imports — only loaded when first voice command hits
_intent_detector = None
_handler         = None


def _lazy_init(jarvis_instance=None):
    global _intent_detector, _handler
    if _intent_detector is not None:
        return  # already initialised

    from asset_intent import detect_asset_intent
    from asset_command_handler import AssetCommandHandler

    _intent_detector = detect_asset_intent

    # Try to grab TTS function from Jarvis instance
    tts_fn = None
    if jarvis_instance:
        for attr in ["speak", "say", "tts", "voice_say", "respond"]:
            fn = getattr(jarvis_instance, attr, None)
            if callable(fn):
                tts_fn = fn
                log.info("[AssetPlugin] TTS hooked: jarvis.%s", attr)
                break

    # Try to get blender path from Jarvis config
    blender_exe = r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"
    try:
        import config as jarvis_config
        blender_exe = getattr(jarvis_config, "BLENDER_PATH", "blender")
    except ImportError:
        pass

    _handler = AssetCommandHandler(blender_exe=blender_exe, tts_fn=tts_fn)
    log.info("[AssetPlugin] Initialised. Blender: %s", blender_exe)


# ═══════════════════════════════════════════════════════════════
# PLUGIN INTERFACE
# Jarvis PluginLoader calls these two methods.
# ═══════════════════════════════════════════════════════════════

# Plugin metadata (some loaders read these)
NAME        = "asset_creation"
DESCRIPTION = "Creates 3D game assets via Blender from voice commands"
VERSION     = "1.0.0"
PRIORITY    = 10   # higher = checked before lower-priority plugins


def can_handle(command: str) -> bool:
    """Return True if this plugin should handle the command."""
    _lazy_init()
    is_asset, _ = _intent_detector(command)
    return is_asset


def handle(command: str, jarvis=None) -> str:
    """
    Handle the command. Called by PluginLoader after can_handle() == True.
    Returns spoken response string.
    """
    _lazy_init(jarvis)
    _, spec_name = _intent_detector(command)

    if spec_name is None:
        return "I understood you want to create something, but I'm not sure what asset."

    return _handler.handle(spec_name)


# ═══════════════════════════════════════════════════════════════
# MANUAL HOOK  (use this if PluginLoader doesn't call can_handle)
# ═══════════════════════════════════════════════════════════════
#
# In brain.py → think(), add BEFORE the LLM call:
#
#   from plugins.asset_creation_plugin import try_handle_asset
#   result = try_handle_asset(user_input)
#   if result:
#       return BrainResponse(spoken_text=result, raw_text=result, action=None)
#
# ─────────────────────────────────────────────────────────────

def try_handle_asset(command: str, jarvis=None) -> str | None:
    """
    Convenience function for manual brain.py hook.
    Returns spoken string if command is an asset command, else None.
    """
    if can_handle(command):
        return handle(command, jarvis)
    return None
