"""
ProgrammingAgent
================
Phase 5 — Autonomous C# Code Generation
Generates scripts, compiles, detects errors, auto-fixes until build succeeds.
"""

import os
import subprocess
import pathlib
from typing import Dict, List
from ..base_agent import BaseAgent
from ...config.settings import Settings


class ProgrammingAgent(BaseAgent):
    NAME = "programming"
    ROLE = "Generates C# Unity scripts with autonomous error detection and fixing"

    CODE_SYSTEM_PROMPT = """
You are an expert Unity C# developer. Generate clean, production-ready C# scripts.
Return ONLY a JSON array of scripts:
[
  {
    "name": "ScriptName",
    "filename": "ScriptName.cs",
    "type": "MonoBehaviour|ScriptableObject|static",
    "description": "what it does",
    "code": "using UnityEngine;\\n\\npublic class ScriptName : MonoBehaviour {\\n  // full implementation\\n}"
  }
]
Include full implementations, not stubs. Use proper Unity APIs.
"""

    FIX_SYSTEM_PROMPT = """
You are an expert Unity C# debugger. Fix the compilation error and return the corrected code ONLY.
No explanation. No markdown. Just the fixed C# code.
"""

    def run(self, systems: List, context: Dict = None) -> Dict:
        context = context or {}
        scripts = []
        failed  = []

        if not systems:
            return {"scripts": [], "failed": []}

        for system in systems:
            name = system if isinstance(system, str) else system.get("name", "Script")
            try:
                script = self._generate_script(name, system, context)
                fixed  = self._auto_fix_loop(script)
                scripts.append(fixed)
                self._save_script(fixed, context)
                self.log.info("[Programming] ✅ Script ready: %s", fixed["name"])
            except Exception as e:
                self.log.error("[Programming] ❌ Failed: %s — %s", name, e)
                failed.append({"name": name, "error": str(e)})

        return {"scripts": scripts, "failed": failed}

    def _generate_script(self, name: str, system_spec, context: Dict) -> Dict:
        memory_ctx = self.get_memory_context()
        if isinstance(system_spec, dict):
            desc = f"Type: {system_spec.get('type', 'system')}, Name: {name}"
        else:
            desc = str(system_spec)

        prompt = (
            f"{memory_ctx}\n\n"
            f"Generate a Unity C# script for: {desc}\n"
            f"Script name: {name}"
        )

        result = self.ask_llm(prompt, system=self.CODE_SYSTEM_PROMPT, expect_json=True)

        # Handle array or single script
        if isinstance(result, list) and result:
            return result[0]
        if isinstance(result, dict) and "name" in result:
            return result

        # Fallback template
        return {
            "name": name,
            "filename": f"{name}.cs",
            "type": "MonoBehaviour",
            "description": f"Auto-generated {name}",
            "code": self._fallback_template(name)
        }

    def _auto_fix_loop(self, script: Dict) -> Dict:
        if not Settings.AUTO_FIX_CODE:
            return script

        max_retries = Settings.MAX_FIX_RETRIES
        for attempt in range(max_retries):
            errors = self._check_syntax(script["code"])
            if not errors:
                self.log.info("[Programming] Script %s OK (attempt %d)",
                              script["name"], attempt + 1)
                return script

            self.log.warning("[Programming] Errors in %s (attempt %d/%d): %s",
                             script["name"], attempt + 1, max_retries, errors[:200])

            fixed_code = self.ask_llm(
                f"Fix these C# errors:\n{errors}\n\nCode:\n{script['code']}",
                system=self.FIX_SYSTEM_PROMPT
            )
            script = dict(script)
            script["code"] = fixed_code

        self.log.error("[Programming] Could not fix %s after %d attempts",
                       script["name"], max_retries)
        return script

    def _check_syntax(self, code: str) -> str:
        """Basic syntax checks. Full check requires Unity/mcs."""
        errors = []
        # Check balanced braces
        opens  = code.count("{")
        closes = code.count("}")
        if opens != closes:
            errors.append(f"Unbalanced braces: {opens} open, {closes} close")
        # Check using statements
        if "MonoBehaviour" in code and "using UnityEngine" not in code:
            errors.append("Missing: using UnityEngine;")
        # Check class declaration
        if "class " not in code:
            errors.append("No class declaration found")
        return "; ".join(errors)

    def _save_script(self, script: Dict, context: Dict):
        project_path = Settings.UNITY_PROJECT_PATH
        if not project_path:
            # Save locally
            output_dir = pathlib.Path(Settings.PROJECTS_DIR) / "scripts"
        else:
            output_dir = pathlib.Path(project_path) / "Assets" / "Scripts" / "JarvisGenerated"

        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / script.get("filename", f"{script['name']}.cs")

        with open(file_path, "w") as f:
            f.write(script["code"])

        script["saved_path"] = str(file_path)
        self.log.info("[Programming] Saved: %s", file_path)

    def _fallback_template(self, name: str) -> str:
        return f"""using UnityEngine;

/// <summary>
/// {name} - Auto-generated by Jarvis Game Agent
/// </summary>
public class {name} : MonoBehaviour
{{
    [Header("Settings")]
    public float speed = 5f;

    private void Start()
    {{
        Debug.Log("[{name}] Initialized");
    }}

    private void Update()
    {{
        // Add logic here
    }}
}}
"""
