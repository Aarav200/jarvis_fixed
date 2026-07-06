"""
PlannerAgent
============
Phase 4 — Game Design Agent
Creates full Game Design Documents and task breakdowns.
"""

import uuid
import datetime
from typing import Dict, List
from ..base_agent import BaseAgent


class PlannerAgent(BaseAgent):
    NAME = "planner"
    ROLE = "Creates Game Design Documents and breaks down development tasks"

    GDD_SYSTEM_PROMPT = """
You are a senior game designer. Create a detailed Game Design Document.
Return ONLY valid JSON with this exact structure:
{
  "title": "game title",
  "genre": "genre",
  "concept": "one paragraph concept",
  "mechanics": ["mechanic1", "mechanic2", "mechanic3"],
  "progression": {"type": "...", "stages": ["..."]},
  "resources": ["resource1", "resource2"],
  "inventory": {"slots": 20, "type": "grid"},
  "ui_flow": ["main_menu", "hud", "inventory", "pause"],
  "assets": [
    {"name": "player_character", "type": "character", "style": "low_poly"},
    {"name": "environment_tiles", "type": "environment", "style": "low_poly"}
  ],
  "systems": [
    {"name": "PlayerController", "type": "movement", "language": "csharp"},
    {"name": "InventorySystem", "type": "inventory", "language": "csharp"},
    {"name": "SaveSystem", "type": "persistence", "language": "csharp"}
  ],
  "art_style": "low_poly",
  "target_platform": "PC",
  "estimated_scope": "medium"
}
"""

    def run(self, command: str, context: Dict = None) -> Dict:
        context = context or {}
        memory_ctx = self.get_memory_context()

        prompt = (
            f"{memory_ctx}\n\n"
            f"Create a Game Design Document for: {command}\n"
            f"User art style preference: "
            f"{self.memory.get_style('art', 'low_poly') if self.memory else 'low_poly'}"
        )

        gdd = self.ask_llm(prompt, system=self.GDD_SYSTEM_PROMPT, expect_json=True)

        # Ensure required fields
        gdd.setdefault("title",    self._extract_title(command))
        gdd.setdefault("mechanics", [])
        gdd.setdefault("systems",   [])
        gdd.setdefault("assets",    [])

        project_id = f"{gdd['title'].lower().replace(' ', '_')}_{uuid.uuid4().hex[:6]}"

        task_list = self._build_task_list(gdd)

        result = {
            "project_id": project_id,
            "gdd":        gdd,
            "tasks":      task_list,
            "created_at": datetime.datetime.utcnow().isoformat()
        }

        self.save_log(command, result)
        self.log.info("[Planner] GDD created: %s (%d tasks)", gdd["title"], len(task_list))
        return result

    def _build_task_list(self, gdd: Dict) -> List[Dict]:
        tasks = []
        # Asset tasks
        for asset in gdd.get("assets", []):
            tasks.append({"type": "asset", "name": asset["name"],
                          "agent": "asset", "priority": 1})
        # Code tasks
        for system in gdd.get("systems", []):
            tasks.append({"type": "code", "name": system["name"],
                          "agent": "programming", "priority": 2})
        # Scene task
        tasks.append({"type": "scene", "name": "main_scene",
                      "agent": "scene", "priority": 3})
        # Test task
        tasks.append({"type": "test", "name": "gameplay_test",
                      "agent": "testing", "priority": 4})
        return tasks

    def _extract_title(self, command: str) -> str:
        words = command.lower().replace("create a", "").replace("make a", "").strip()
        return words[:40].title()
