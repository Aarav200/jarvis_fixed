"""
╔══════════════════════════════════════════════════════════╗
║         JARVIS GAME AGENT — Autonomous Game Studio       ║
║                     v1.0 Final Phase                     ║
╚══════════════════════════════════════════════════════════╝

Self-contained module. Zero changes to main.py or brain.py.

HOW TO CONNECT TO JARVIS (one line in main.py):
─────────────────────────────────────────────
    from jarvis_game_agent import GameAgentPlugin
    GameAgentPlugin.register(jarvis)

VOICE COMMANDS AUTOMATICALLY HANDLED:
─────────────────────────────────────
    "Jarvis, create a horror game in an abandoned hospital"
    "Jarvis, create this car in Unity"  [+ image]
    "Jarvis, write an inventory system"
    "Jarvis, test the game and report bugs"
    "Jarvis, create a low poly tree in Blender"
"""

from .plugin import GameAgentPlugin
from .agents.manager.manager_agent import ManagerAgent
from .memory.memory_manager import MemoryManager

__version__ = "1.0.0"
__all__ = ["GameAgentPlugin", "ManagerAgent", "MemoryManager"]
