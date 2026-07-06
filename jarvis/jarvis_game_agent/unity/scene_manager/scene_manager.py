"""
SceneManager
============
Phase 3 — Builds Unity scenes from natural language descriptions.
Creates scene, sets up lighting, imports assets, places prefabs.
"""

import logging
from typing import Dict
from ...unity.editor_bridge.unity_bridge import UnityBridge

logger = logging.getLogger("jarvis.game_agent.unity.scene")


class SceneManager:
    def __init__(self):
        self._bridge = UnityBridge()

    def create_scene(self, description: str, context: Dict = None) -> Dict:
        context = context or {}
        desc    = description.lower()

        # Determine scene name
        words = [w for w in desc.split()
                 if w not in ["create", "build", "make", "a", "the", "scene", "setup"]]
        scene_name = "_".join(words[:3]) if words else "main_scene"
        scene_name = scene_name.replace(" ", "_")

        # Step 1: Setup folders
        self._bridge.create_folder_structure()

        # Step 2: Create scene
        result = self._bridge.create_scene(scene_name)

        # Step 3: Lighting based on description
        light_cfg = self._determine_lighting(desc)
        self._bridge.setup_lighting(**light_cfg)

        # Step 4: Terrain for open-world descriptions
        if any(w in desc for w in ["outdoor", "open world", "forest",
                                    "terrain", "landscape", "island"]):
            self._bridge.create_terrain(size=500, height=100)

        logger.info("[SceneManager] Scene ready: %s", scene_name)

        return {
            "scene_name": scene_name,
            "lighting":   light_cfg,
            "status":     result.get("status", "created")
        }

    def _determine_lighting(self, description: str) -> Dict:
        if any(w in description for w in ["night", "dark", "horror", "cave", "dungeon"]):
            return {"lighting_type": "directional", "intensity": 0.1, "color": "#1a1a3e"}
        if any(w in description for w in ["sunset", "dawn", "dusk", "orange"]):
            return {"lighting_type": "directional", "intensity": 0.8, "color": "#ff8c42"}
        if any(w in description for w in ["indoor", "room", "interior", "building"]):
            return {"lighting_type": "point", "intensity": 1.2, "color": "#ffe8c8"}
        if any(w in description for w in ["sci-fi", "scifi", "space", "neon"]):
            return {"lighting_type": "directional", "intensity": 0.6, "color": "#8888ff"}
        # Default: outdoor daylight
        return {"lighting_type": "directional", "intensity": 1.0, "color": "#fffce8"}
