"""
MemoryManager
=============
Persistent memory for the entire Game Agent.
Stores: projects, lessons learned, user preferences, art/code styles.
All data is saved as JSON — survives restarts.
"""

import json
import os
import pathlib
import datetime
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.game_agent.memory")

BASE = pathlib.Path(__file__).parent  # memory/


class MemoryManager:
    def __init__(self):
        self._projects_dir    = BASE / "projects"
        self._lessons_dir     = BASE / "lessons"
        self._prefs_file      = BASE / "preferences" / "user_preferences.json"
        self._styles_file     = BASE / "styles" / "style_memory.json"
        self._knowledge_file  = BASE / "lessons" / "knowledge_base.json"

        # Ensure dirs exist
        for d in [self._projects_dir, self._lessons_dir,
                  BASE / "preferences", BASE / "styles"]:
            d.mkdir(parents=True, exist_ok=True)

        # In-memory caches
        self._prefs     = self._load_json(self._prefs_file, {})
        self._styles    = self._load_json(self._styles_file, {})
        self._knowledge = self._load_json(self._knowledge_file, {"lessons": [], "patterns": {}})

    # ─────────────────────────────────────────
    # USER PREFERENCES
    # ─────────────────────────────────────────

    def set_preference(self, key: str, value: Any):
        """e.g. set_preference('art_style', 'low_poly')"""
        self._prefs[key] = value
        self._save_json(self._prefs_file, self._prefs)
        logger.info("[Memory] Preference saved: %s = %s", key, value)

    def get_preference(self, key: str, default=None) -> Any:
        return self._prefs.get(key, default)

    def get_all_preferences(self) -> Dict:
        return dict(self._prefs)

    # ─────────────────────────────────────────
    # PROJECT MEMORY
    # ─────────────────────────────────────────

    def save_project(self, project_id: str, data: Dict):
        """Save full project state."""
        path = self._projects_dir / f"{project_id}.json"
        data["_last_updated"] = datetime.datetime.utcnow().isoformat()
        self._save_json(path, data)
        logger.info("[Memory] Project saved: %s", project_id)

    def load_project(self, project_id: str) -> Optional[Dict]:
        path = self._projects_dir / f"{project_id}.json"
        return self._load_json(path, None)

    def list_projects(self) -> List[str]:
        return [f.stem for f in self._projects_dir.glob("*.json")]

    def update_project(self, project_id: str, updates: Dict):
        data = self.load_project(project_id) or {}
        data.update(updates)
        self.save_project(project_id, data)

    # ─────────────────────────────────────────
    # LESSONS LEARNED
    # ─────────────────────────────────────────

    def add_lesson(self, category: str, what_worked: str,
                   what_failed: str, notes: str = ""):
        lesson = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "category": category,
            "what_worked": what_worked,
            "what_failed": what_failed,
            "notes": notes
        }
        self._knowledge["lessons"].append(lesson)
        self._save_json(self._knowledge_file, self._knowledge)
        logger.info("[Memory] Lesson added: [%s] %s", category, what_worked[:60])

    def get_lessons(self, category: str = None) -> List[Dict]:
        lessons = self._knowledge["lessons"]
        if category:
            lessons = [l for l in lessons if l.get("category") == category]
        return lessons

    def add_pattern(self, pattern_name: str, pattern_data: Dict):
        """Store a reusable pattern (e.g. 'inventory_system_template')."""
        self._knowledge["patterns"][pattern_name] = {
            "data": pattern_data,
            "used_count": self._knowledge["patterns"].get(pattern_name, {}).get("used_count", 0) + 1,
            "last_used": datetime.datetime.utcnow().isoformat()
        }
        self._save_json(self._knowledge_file, self._knowledge)

    def get_pattern(self, pattern_name: str) -> Optional[Dict]:
        return self._knowledge["patterns"].get(pattern_name)

    # ─────────────────────────────────────────
    # STYLE MEMORY
    # ─────────────────────────────────────────

    def set_style(self, style_type: str, style_value: str):
        """e.g. set_style('art', 'low_poly_stylized')"""
        self._styles[style_type] = {
            "value": style_value,
            "set_at": datetime.datetime.utcnow().isoformat()
        }
        self._save_json(self._styles_file, self._styles)

    def get_style(self, style_type: str, default: str = "") -> str:
        entry = self._styles.get(style_type, {})
        return entry.get("value", default)

    # ─────────────────────────────────────────
    # CONTEXT BUILDER (for agents)
    # ─────────────────────────────────────────

    def build_context_summary(self) -> str:
        """Returns a natural language summary for LLM prompts."""
        lines = []
        if self._prefs:
            lines.append("User preferences:")
            for k, v in self._prefs.items():
                lines.append(f"  - {k}: {v}")
        art = self.get_style("art")
        code = self.get_style("code")
        if art:
            lines.append(f"Preferred art style: {art}")
        if code:
            lines.append(f"Preferred code style: {code}")
        recent = self.get_lessons()[-3:] if self.get_lessons() else []
        if recent:
            lines.append("Recent lessons learned:")
            for l in recent:
                lines.append(f"  - [{l['category']}] {l['what_worked']}")
        return "\n".join(lines) if lines else "No preferences stored yet."

    # ─────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────

    @staticmethod
    def _load_json(path, default):
        try:
            with open(path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return default

    @staticmethod
    def _save_json(path, data):
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
