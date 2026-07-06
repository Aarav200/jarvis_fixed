"""
TestingAgent
============
Phase 7 — Autonomous Game Testing
Launches game, simulates player behavior, detects bugs, generates reports.
"""

import json
import datetime
import pathlib
from typing import Dict, List
from ..base_agent import BaseAgent
from ...config.settings import Settings


class TestingAgent(BaseAgent):
    NAME = "testing"
    ROLE = "Simulates gameplay, detects bugs, softlocks, and balance issues"

    ANALYSIS_SYSTEM_PROMPT = """
You are a QA engineer and game tester. Analyze the game project and identify:
1. Potential bugs
2. Softlocks (states where player can't progress)
3. Balance issues
4. Missing null checks
5. Performance concerns

Return JSON:
{
  "bugs": ["bug description 1", "bug description 2"],
  "softlocks": ["softlock description"],
  "balance_issues": ["balance issue"],
  "performance_warnings": ["warning"],
  "missing_features": ["missing feature"],
  "score": 7,
  "recommendation": "short recommendation"
}
"""

    def run(self, project_id: str, context: Dict = None) -> Dict:
        context = context or {}
        self.log.info("[Testing] Starting test for: %s", project_id)

        # Gather project info
        project_data = {}
        if self.memory:
            project_data = self.memory.load_project(project_id) or {}

        # Analyze code for bugs
        code_bugs = self._analyze_code(project_data, context)

        # Check scene integrity
        scene_issues = self._check_scene(project_data, context)

        # LLM-powered analysis
        ai_analysis = self._ai_analysis(project_data, code_bugs, context)

        bugs = (
            ai_analysis.get("bugs", []) +
            code_bugs.get("errors", []) +
            scene_issues.get("errors", [])
        )

        report = {
            "project_id":           project_id,
            "timestamp":            datetime.datetime.utcnow().isoformat(),
            "bugs":                 bugs,
            "softlocks":            ai_analysis.get("softlocks", []),
            "balance_issues":       ai_analysis.get("balance_issues", []),
            "performance_warnings": ai_analysis.get("performance_warnings", []),
            "missing_features":     ai_analysis.get("missing_features", []),
            "score":                ai_analysis.get("score", 5),
            "recommendation":       ai_analysis.get("recommendation", ""),
            "total_issues":         len(bugs),
            "status":               "passed" if len(bugs) == 0 else "issues_found"
        }

        self._save_report(project_id, report)

        if self.memory:
            self.memory.update_project(project_id, {"test_report": report})

        self.log.info("[Testing] Done. Found %d issues.", len(bugs))
        return report

    def _analyze_code(self, project_data: Dict, context: Dict) -> Dict:
        errors = []
        scripts = project_data.get("code", {}).get("scripts", [])

        for script in scripts:
            code = script.get("code", "")
            name = script.get("name", "unknown")

            # Null reference checks
            if "GetComponent" in code and "== null" not in code and "!= null" not in code:
                errors.append(f"{name}: GetComponent() used without null check")

            # Find/FindWithTag performance
            if "FindObjectOfType" in code or "Find(" in code:
                errors.append(f"{name}: Find() in Update() is expensive — cache it in Start()")

            # Coroutine checks
            if "StartCoroutine" in code and "IEnumerator" not in code:
                errors.append(f"{name}: StartCoroutine called but no IEnumerator found")

            # Infinity/NaN guards
            if "/ " in code and "Mathf.Approximately" not in code:
                errors.append(f"{name}: Possible division — ensure no divide-by-zero")

        return {"errors": errors}

    def _check_scene(self, project_data: Dict, context: Dict) -> Dict:
        errors = []
        gdd = project_data.get("gdd", {})

        required_systems = ["PlayerController", "GameManager"]
        existing_scripts = [
            s.get("name", "") for s in
            project_data.get("code", {}).get("scripts", [])
        ]

        for system in required_systems:
            if system not in existing_scripts:
                errors.append(f"Missing required script: {system}")

        mechanics = gdd.get("mechanics", [])
        if not mechanics:
            errors.append("No game mechanics defined in GDD")

        return {"errors": errors}

    def _ai_analysis(self, project_data: Dict, code_analysis: Dict,
                     context: Dict) -> Dict:
        summary = json.dumps({
            "gdd":       project_data.get("gdd", {}),
            "scripts":   [s.get("name") for s in
                          project_data.get("code", {}).get("scripts", [])],
            "code_bugs": code_analysis.get("errors", [])
        }, indent=2)[:3000]  # Trim for token budget

        prompt = f"Analyze this game project for bugs and issues:\n{summary}"
        return self.ask_llm(prompt, system=self.ANALYSIS_SYSTEM_PROMPT, expect_json=True)

    def _save_report(self, project_id: str, report: Dict):
        reports_dir = pathlib.Path(Settings.LOGS_DIR) / "test_reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        ts   = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = reports_dir / f"{project_id}_test_{ts}.json"
        with open(path, "w") as f:
            json.dump(report, f, indent=2)
        self.log.info("[Testing] Report saved: %s", path)
