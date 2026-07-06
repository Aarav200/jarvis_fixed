"""
LearningSystem
==============
Phase 9 — Post-project evaluation and knowledge base.
After every project Jarvis evaluates what worked, what failed, and stores lessons.
Over time builds patterns for faster, better generation.
"""

import json
import datetime
import pathlib
import logging
from typing import Dict, List, Optional

logger = logging.getLogger("jarvis.game_agent.learning")

BASE = pathlib.Path(__file__).parent


class LearningSystem:
    def __init__(self, memory_manager=None):
        self.memory   = memory_manager
        self._kb_path = BASE / "knowledge_base.json"
        self._kb      = self._load_kb()

    # ─────────────────────────────────────────
    # POST-PROJECT EVALUATION
    # ─────────────────────────────────────────

    def evaluate_project(self, project_id: str, project_data: Dict) -> Dict:
        """Called after every project completes."""
        evaluation = self._analyze_project(project_data)

        # Store in knowledge base
        self._kb["evaluations"].append({
            "project_id":  project_id,
            "timestamp":   datetime.datetime.utcnow().isoformat(),
            "evaluation":  evaluation
        })

        # Extract and store patterns
        self._extract_patterns(project_data, evaluation)

        # Update success metrics
        self._update_metrics(evaluation)

        self._save_kb()

        if self.memory:
            self.memory.add_lesson(
                category="project_complete",
                what_worked=evaluation.get("what_worked", ""),
                what_failed=evaluation.get("what_failed", ""),
                notes=evaluation.get("improvements", "")
            )

        logger.info("[Learning] Project evaluated: %s (score: %s)",
                    project_id, evaluation.get("score", "N/A"))
        return evaluation

    def _analyze_project(self, project_data: Dict) -> Dict:
        code    = project_data.get("code", {})
        assets  = project_data.get("assets", {})
        tests   = project_data.get("tests", {})
        review  = project_data.get("review", {})

        scripts_count = len(code.get("scripts", []))
        failed_code   = len(code.get("failed", []))
        assets_count  = len(assets.get("created", []))
        failed_assets = len(assets.get("failed", []))
        bugs          = len(tests.get("bugs", []))
        score         = review.get("score", 5)

        what_worked = []
        what_failed = []

        if scripts_count > 0 and failed_code == 0:
            what_worked.append(f"All {scripts_count} scripts generated successfully")
        if failed_code > 0:
            what_failed.append(f"{failed_code} scripts failed to generate")
        if assets_count > 0:
            what_worked.append(f"{assets_count} assets created")
        if failed_assets > 0:
            what_failed.append(f"{failed_assets} assets failed")
        if bugs == 0:
            what_worked.append("No bugs found in testing")
        if bugs > 3:
            what_failed.append(f"{bugs} bugs found — improve code generation")

        return {
            "score":        score,
            "what_worked":  "; ".join(what_worked) or "N/A",
            "what_failed":  "; ".join(what_failed) or "None",
            "improvements": "; ".join(review.get("improvements", [])),
            "scripts_success_rate": (
                round(scripts_count / max(scripts_count + failed_code, 1) * 100)
            ),
            "assets_success_rate": (
                round(assets_count / max(assets_count + failed_assets, 1) * 100)
            ),
        }

    def _extract_patterns(self, project_data: Dict, evaluation: Dict):
        """Store reusable patterns from successful projects."""
        if evaluation.get("score", 0) >= 7:
            gdd = project_data.get("plan", {}).get("gdd", {})
            genre = gdd.get("genre", "unknown")

            # Store GDD pattern for this genre
            if genre != "unknown" and self.memory:
                self.memory.add_pattern(
                    f"gdd_template_{genre}",
                    {
                        "mechanics": gdd.get("mechanics", []),
                        "systems":   [s["name"] for s in gdd.get("systems", [])],
                        "art_style": gdd.get("art_style", "low_poly"),
                        "score":     evaluation.get("score")
                    }
                )
                logger.info("[Learning] Pattern stored: gdd_template_%s", genre)

    def _update_metrics(self, evaluation: Dict):
        metrics = self._kb.setdefault("metrics", {
            "total_projects": 0,
            "average_score":  0,
            "total_scripts":  0,
            "total_bugs":     0,
        })
        n = metrics["total_projects"]
        metrics["total_projects"] += 1
        # Running average
        metrics["average_score"] = round(
            (metrics["average_score"] * n + evaluation.get("score", 5))
            / metrics["total_projects"], 2
        )

    # ─────────────────────────────────────────
    # KNOWLEDGE RETRIEVAL
    # ─────────────────────────────────────────

    def get_best_practices(self, category: str = None) -> List[str]:
        practices = []
        for ev in self._kb.get("evaluations", [])[-20:]:
            e = ev.get("evaluation", {})
            if e.get("score", 0) >= 8:
                ww = e.get("what_worked", "")
                if ww and ww != "N/A":
                    practices.append(ww)
        return list(set(practices))[:10]

    def get_metrics_summary(self) -> str:
        m = self._kb.get("metrics", {})
        return (
            f"Total projects: {m.get('total_projects', 0)}\n"
            f"Average score: {m.get('average_score', 0)}/10\n"
            f"Best practices: {len(self.get_best_practices())}"
        )

    # ─────────────────────────────────────────
    # PERSISTENCE
    # ─────────────────────────────────────────

    def _load_kb(self) -> Dict:
        try:
            with open(self._kb_path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"evaluations": [], "patterns": {}, "metrics": {}}

    def _save_kb(self):
        with open(self._kb_path, "w") as f:
            json.dump(self._kb, f, indent=2)
