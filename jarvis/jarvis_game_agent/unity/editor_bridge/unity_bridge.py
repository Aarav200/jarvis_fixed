"""
UnityBridge
===========
Phase 3 — Controls Unity Editor autonomously.
Communicates via WebSocket (live) and HTTP fallback.
Requires JarvisUnityBridge.cs installed in the Unity project.
"""

import json
import logging
import pathlib
import shutil
import os
from typing import Dict, Optional

from ...config.settings import Settings

logger = logging.getLogger("jarvis.game_agent.unity")


class UnityBridge:
    """
    Sends commands to Unity Editor.
    Falls back to file-based communication if WebSocket unavailable.
    """

    COMMANDS_DIR = None   # set at init

    def __init__(self):
        self._ws   = None
        self._http = None
        self.COMMANDS_DIR = pathlib.Path(Settings.PROJECTS_DIR) / "_unity_commands"
        self.COMMANDS_DIR.mkdir(parents=True, exist_ok=True)

        self._try_connect_ws()

    # ─────────────────────────────────────────
    # CONNECTION
    # ─────────────────────────────────────────

    def _try_connect_ws(self):
        try:
            import websocket
            ws_url = f"ws://localhost:{Settings.UNITY_WS_PORT}"
            self._ws = websocket.WebSocket()
            self._ws.connect(ws_url, timeout=2)
            logger.info("[Unity] ✅ WebSocket connected: %s", ws_url)
        except Exception:
            logger.info("[Unity] WebSocket not available — using file bridge")
            self._ws = None

    def _send(self, command: Dict) -> Dict:
        """Send command to Unity. Returns response."""
        payload = json.dumps(command)

        # Try WebSocket first
        if self._ws:
            try:
                self._ws.send(payload)
                response = self._ws.recv()
                return json.loads(response)
            except Exception as e:
                logger.warning("[Unity] WS send failed: %s", e)
                self._ws = None

        # Try HTTP
        try:
            import urllib.request
            req = urllib.request.Request(
                f"http://localhost:{Settings.UNITY_HTTP_PORT}/command",
                data=payload.encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read())
        except Exception:
            pass

        # File-based fallback (Unity polls this folder)
        return self._file_bridge(command)

    def _file_bridge(self, command: Dict) -> Dict:
        import time
        cmd_id    = str(int(time.time() * 1000))
        cmd_file  = self.COMMANDS_DIR / f"cmd_{cmd_id}.json"
        resp_file = self.COMMANDS_DIR / f"resp_{cmd_id}.json"

        with open(cmd_file, "w") as f:
            json.dump({"id": cmd_id, **command}, f)

        # Wait for Unity to process (max 10s)
        for _ in range(20):
            time.sleep(0.5)
            if resp_file.exists():
                with open(resp_file) as f:
                    result = json.load(f)
                resp_file.unlink()
                cmd_file.unlink()
                return result

        # Unity not running — return simulated response
        logger.warning("[Unity] No response from Unity — offline mode")
        return {"status": "queued", "note": "Unity offline. Command queued.", **command}

    # ─────────────────────────────────────────
    # ASSET IMPORT
    # ─────────────────────────────────────────

    def import_asset(self, asset_path: str, target_folder: str = "Assets/JarvisAssets") -> Dict:
        if not asset_path or not os.path.exists(asset_path):
            logger.warning("[Unity] Asset path not found: %s", asset_path)
            return {"status": "failed", "error": "File not found", "path": asset_path}

        # Copy to Unity project Assets folder if path is configured
        if Settings.UNITY_PROJECT_PATH:
            dest_dir = pathlib.Path(Settings.UNITY_PROJECT_PATH) / target_folder
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / pathlib.Path(asset_path).name
            shutil.copy2(asset_path, dest_path)
            logger.info("[Unity] Copied asset to: %s", dest_path)

        return self._send({
            "action": "import_asset",
            "path": asset_path,
            "target_folder": target_folder
        })

    # ─────────────────────────────────────────
    # SCENE CREATION
    # ─────────────────────────────────────────

    def create_scene(self, scene_name: str, config: Dict = None) -> Dict:
        return self._send({
            "action": "create_scene",
            "scene_name": scene_name,
            "config": config or {}
        })

    def setup_lighting(self, lighting_type: str = "directional",
                       intensity: float = 1.0, color: str = "#fffce8") -> Dict:
        return self._send({
            "action": "setup_lighting",
            "type": lighting_type,
            "intensity": intensity,
            "color": color
        })

    def create_terrain(self, size: int = 500, height: int = 100) -> Dict:
        return self._send({
            "action": "create_terrain",
            "size": size,
            "height": height
        })

    # ─────────────────────────────────────────
    # PREFAB
    # ─────────────────────────────────────────

    def create_prefab(self, name: str, components: list,
                      folder: str = "Assets/Prefabs") -> Dict:
        return self._send({
            "action": "create_prefab",
            "name": name,
            "components": components,
            "folder": folder
        })

    # ─────────────────────────────────────────
    # FOLDER ORGANIZATION
    # ─────────────────────────────────────────

    def create_folder_structure(self) -> Dict:
        return self._send({
            "action": "create_folders",
            "folders": [
                "Assets/JarvisGenerated",
                "Assets/JarvisGenerated/Scripts",
                "Assets/JarvisGenerated/Assets",
                "Assets/JarvisGenerated/Prefabs",
                "Assets/JarvisGenerated/Scenes",
                "Assets/JarvisGenerated/UI",
                "Assets/JarvisGenerated/Materials",
            ]
        })

    # ─────────────────────────────────────────
    # BUILD
    # ─────────────────────────────────────────

    def build_game(self, platform: str = "StandaloneWindows64",
                   output_path: str = "") -> Dict:
        if not output_path:
            output_path = str(pathlib.Path(Settings.PROJECTS_DIR) / "builds" / platform)
        return self._send({
            "action": "build",
            "platform": platform,
            "output_path": output_path
        })
