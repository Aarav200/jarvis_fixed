"""
GameAgentPlugin
===============
Registers all game-agent voice commands into Jarvis.
Call GameAgentPlugin.register(jarvis) once at startup.
"""

import logging
from .agents.manager.manager_agent import ManagerAgent
from .memory.memory_manager import MemoryManager
from .config.settings import Settings

logger = logging.getLogger("jarvis.game_agent")

class GameAgentPlugin:
    """
    Connects the entire Game Agent module to Jarvis.
    Jarvis calls handle(command, image=None) for every voice/text input.
    """

    TRIGGER_PHRASES = [
        "create a game",
        "make a game",
        "build a game",
        "create this",
        "build this",
        "model this",
        "create a scene",
        "build a scene",
        "write a script",
        "write an inventory",
        "write a combat",
        "create in unity",
        "import to unity",
        "add to unity",
        "create in blender",
        "model in blender",
        "test the game",
        "test game",
        "find bugs",
        "game design",
        "design document",
        "gdd",
        "low poly",
        "3d model",
        "asset",
    ]

    _manager: ManagerAgent = None
    _memory: MemoryManager = None

    @classmethod
    def register(cls, jarvis_instance):
        cls._memory = MemoryManager()
        cls._manager = ManagerAgent(cls._memory)
        Settings.load()

        if hasattr(jarvis_instance, "register_plugin"):
            jarvis_instance.register_plugin(cls)
            logger.info("[GameAgent] Registered via register_plugin()")

        elif hasattr(jarvis_instance, "on_command"):
            for phrase in cls.TRIGGER_PHRASES:
                jarvis_instance.on_command(phrase, cls.handle)
            logger.info(
                "[GameAgent] Registered %d trigger phrases",
                len(cls.TRIGGER_PHRASES),
            )

        else:
            logger.warning(
                "[GameAgent] Could not auto-register. "
                "Call GameAgentPlugin.handle(command, image) manually."
            )

        logger.info("[GameAgent] Game Agent Plugin ready (v1.0.0)")
        return cls

    @classmethod
    def handle(cls, command: str, image=None, context: dict = None) -> str:
        print("=== NEW HANDLE CODE LOADED ===", flush=True)
        if not cls._manager:
            print("[PLUGIN] Creating ManagerAgent")
            cls._manager = ManagerAgent(MemoryManager())
            print("[PLUGIN] ManagerAgent created")


        logger.info("[GameAgent] Command received: %s", command)
        print("[PLUGIN] Entering ManagerAgent", flush=True)
        print("[PLUGIN] Manager type:", type(cls._manager), flush=True)
        print("[PLUGIN] Manager object:", cls._manager, flush=True)
        print("[PLUGIN] Manager type:", type(cls._manager))
        print("[PLUGIN] Manager object:", cls._manager)

        result = cls._manager.run(
    command,
    image=image,
    context=context or {}
)
        print("[PLUGIN] ManagerAgent returned:", result)

        return result.get("response", "Task complete.")

    @classmethod
    def is_relevant(cls, command: str) -> bool:
        cmd = command.lower()

        game_keywords = [
            "game",
            "unity",
            "blender",
            "asset",
            "3d model",
            "low poly",
            "enemy",
            "level",
            "scene",
            "player",
            "inventory",
            "horror",
            "fps",
            "rpg",
            "character",
            "zombie",
            "hospital",
            "tree",
        ]

        return any(keyword in cmd for keyword in game_keywords)