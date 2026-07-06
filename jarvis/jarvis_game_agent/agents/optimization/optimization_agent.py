"""
OptimizationAgent
=================
Phase 6 — Scans scripts and scenes for performance issues.
Suggests and applies optimizations automatically.
"""

import re
from typing import Dict, List
from ..base_agent import BaseAgent


class OptimizationAgent(BaseAgent):
    NAME = "optimization"
    ROLE = "Detects performance bottlenecks and optimizes scripts and assets"

    OPT_SYSTEM_PROMPT = """
You are a Unity performance engineer. Given C# code with a performance issue,
return ONLY the optimized version of the code. No explanation. No markdown.
"""

    # Rules: (pattern_to_find, issue_description, fix_hint)
    PERF_RULES = [
        (r"void Update\(\).*?Find\(", "Find() called in Update — cache in Start()", "cache"),
        (r"void Update\(\).*?GetComponent\(", "GetComponent() in Update — cache in Awake()", "cache"),
        (r"void Update\(\).*?new ", "Memory allocation in Update loop", "object_pool"),
        (r"Debug\.Log\(.*?Update", "Debug.Log in Update — remove for build", "remove_log"),
        (r"transform\.position.*?Update", "transform.position set in Update without deltaTime", "use_deltatime"),
        (r"Camera\.main", "Camera.main called repeatedly — cache it", "cache"),
    ]

    def run(self, project_data: Dict, context: Dict = None) -> Dict:
        context = context or {}
        scripts = project_data.get("code", {}).get("scripts", [])

        issues    = []
        optimized = []

        for script in scripts:
            code = script.get("code", "")
            name = script.get("name", "unknown")
            found = self._scan_script(name, code)

            if found:
                issues.extend(found)
                if context.get("auto_fix_perf", False):
                    fixed_code = self._optimize_script(code, found)
                    opt_script = dict(script)
                    opt_script["code"] = fixed_code
                    opt_script["optimized"] = True
                    optimized.append(opt_script)

        self.log.info("[Optimization] Found %d performance issues", len(issues))
        return {
            "issues": issues,
            "optimized_scripts": optimized,
            "summary": f"{len(issues)} issues found, {len(optimized)} scripts optimized"
        }

    def _scan_script(self, name: str, code: str) -> List[Dict]:
        found = []
        # Join lines for multi-line pattern matching
        flat = code.replace("\n", " ")
        for pattern, description, fix_type in self.PERF_RULES:
            if re.search(pattern, flat):
                found.append({
                    "script": name,
                    "issue": description,
                    "fix_type": fix_type
                })
        return found

    def _optimize_script(self, code: str, issues: List[Dict]) -> str:
        issue_list = "\n".join(f"- {i['issue']}" for i in issues)
        prompt = (
            f"Fix these performance issues in this Unity C# code:\n"
            f"{issue_list}\n\n"
            f"Code:\n{code}"
        )
        return self.ask_llm(prompt, system=self.OPT_SYSTEM_PROMPT)
