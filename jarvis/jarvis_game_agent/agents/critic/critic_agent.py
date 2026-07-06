"""
CriticAgent
===========
Phase 6 — Reviews all agent outputs, scores quality, provides feedback.
The final quality gate before delivery.
"""

from typing import Dict
from ..base_agent import BaseAgent


class CriticAgent(BaseAgent):
    NAME = "critic"
    ROLE = "Reviews game quality, scores results, provides improvement feedback"

    CRITIC_SYSTEM_PROMPT = """
You are a senior game director reviewing an AI-generated game project.
Evaluate the project across these dimensions and return ONLY JSON:
{
  "score": 8,
  "dimensions": {
    "game_design":   {"score": 8, "feedback": "..."},
    "code_quality":  {"score": 7, "feedback": "..."},
    "asset_quality": {"score": 8, "feedback": "..."},
    "completeness":  {"score": 9, "feedback": "..."},
    "fun_factor":    {"score": 7, "feedback": "..."}
  },
  "strengths": ["strength1", "strength2"],
  "weaknesses": ["weakness1", "weakness2"],
  "improvements": ["improvement1", "improvement2"],
  "summary": "one paragraph overall assessment",
  "ship_ready": false
}
Be specific and actionable. Score 1-10.
"""

    def run(self, project_data: Dict, context: Dict = None) -> Dict:
        context = context or {}
        self.log.info("[Critic] Reviewing project...")

        import json
        summary = json.dumps({
            "gdd":    project_data.get("plan", {}).get("gdd", {}),
            "assets": len(project_data.get("assets", {}).get("created", [])),
            "scripts": [s.get("name") for s in
                        project_data.get("code", {}).get("scripts", [])],
            "bugs":   project_data.get("tests", {}).get("bugs", []),
            "test_score": project_data.get("tests", {}).get("score", 0)
        }, indent=2)[:3000]

        review = self.ask_llm(
            f"Review this game project:\n{summary}",
            system=self.CRITIC_SYSTEM_PROMPT,
            expect_json=True
        )

        review.setdefault("score", 5)
        review.setdefault("summary", "Review complete.")
        review.setdefault("improvements", [])

        # Store lessons from weaknesses
        if self.memory and review.get("weaknesses"):
            for weakness in review["weaknesses"]:
                self.memory.add_lesson(
                    category="critic_review",
                    what_worked=str(review.get("strengths", ["N/A"])[0]),
                    what_failed=weakness,
                    notes=review.get("summary", "")
                )

        self.log.info("[Critic] Score: %s/10. Ship ready: %s",
                      review.get("score"), review.get("ship_ready"))
        return review
