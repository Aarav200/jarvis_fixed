"""
plugins/vscode_plugin.py — VS Code integration for Jarvis.

Phase 4: Jarvis watches your active VS Code file and can:
  - Detect and fix bugs
  - Fix indentation
  - Explain what code does
  - Suggest improvements
  - Run the file and explain errors

Setup:
  1. Place this file in jarvis/plugins/
  2. Add the VS Code snippet to your settings.json (instructions below)
  3. Say "Jarvis fix my code" / "what's wrong here" / "explain this code"

VS Code auto-tracking:
  Add to VS Code settings.json (Ctrl+Shift+P → "Open Settings JSON"):
  
  "files.autoSave": "onFocusChange"
  
  AND add this to .vscode/tasks.json in any project:
  {
    "version": "2.0.0",
    "tasks": [{
      "label": "jarvis-track",
      "type": "shell",
      "command": "echo ${file} > C:/Users/achaw/Downloads/jarvis_fixed/jarvis/memory/vscode_active.txt",
      "runOptions": {"runOn": "folderOpen"}
    }]
  }
  
  OR install the "Run on Save" VS Code extension and configure it to
  write the active file path to memory/vscode_active.txt on every save.
"""

import json
import os
import re
import subprocess
import sys
import time
import threading
from pathlib import Path
from typing import Optional

from utils.logger import get_logger

log = get_logger(__name__)

# File where VS Code writes the active file path
ACTIVE_FILE_PATH = Path("memory/vscode_active.txt")
# Pending fix waiting for confirmation
PENDING_FIX_FILE = Path("memory/pending_fix.json")


class VSCodePlugin:
    """
    VS Code integration — reads active file, analyses with LLM,
    shows fix in terminal, applies on confirmation.
    """

    def __init__(self, brain, voice) -> None:
        self._brain  = brain
        self._voice  = voice
        self._pending_fix: Optional[dict] = None
        self._watcher_thread = None
        self._last_file = None
        self._running = False

    def start(self) -> None:
        """Start background file watcher."""
        self._running = True
        self._watcher_thread = threading.Thread(
            target=self._watch_active_file,
            daemon=True,
            name="jarvis-vscode-watcher"
        )
        self._watcher_thread.start()
        log.info("VS Code plugin started — watching for active file.")

    def stop(self) -> None:
        self._running = False

    # ── Public command handlers ───────────────────────────────────────────────

    def get_active_file(self) -> Optional[Path]:
        """Return path of currently active VS Code file."""
        if ACTIVE_FILE_PATH.exists():
            try:
                path_str = ACTIVE_FILE_PATH.read_text(encoding="utf-8").strip()
                p = Path(path_str)
                if p.exists():
                    log.debug("Active file from tracker: %s", p)
                    return p
                # Tracker wrote just a filename — search for it
                fname = Path(path_str).name
                search_dirs = [
                    Path("C:/Users/achaw/Downloads"),
                    Path("C:/Users/achaw/Documents"),
                    Path("C:/Users/achaw/Desktop"),
                    Path.cwd(),
                ]
                for d in search_dirs:
                    if d.exists():
                        for found in d.rglob(fname):
                            if found.is_file():
                                log.info("Found file: %s", found)
                                return found
            except Exception as e:
                log.debug("Active file read error: %s", e)
        # Fallback: try to detect via process list on Windows
        result = self._detect_via_process()
        if result:
            log.info("Active file via process: %s", result)
        return result

    def read_active_code(self) -> Optional[tuple[Path, str]]:
        """Read code from active VS Code file. Returns (path, code) or None."""
        path = self.get_active_file()
        if path is None:
            return None
        try:
            code = path.read_text(encoding="utf-8")
            return path, code
        except Exception as e:
            log.error("Could not read file %s: %s", path, e)
            return None

    def fix_code(self) -> str:
        """Main fix command — analyse code and propose fix."""
        result = self.read_active_code()
        if not result:
            return "I can't find your active VS Code file. Please save your file first, sir."

        path, code = result
        filename = path.name
        lang = self._detect_language(path)

        self._voice.speak(f"Reading {filename}, analysing for issues now sir.")
        lines = code.count("\n")
        log.info("Analysing code: %s (%d lines)", filename, lines)
        print(f"\n[JARVIS] Analysing {filename} ({lines} lines)...")

        # For large files, send first 80 lines (imports/structure) + last 150 lines (errors)
        code_to_send = code
        if lines > 300:
            code_lines = code.splitlines()
            first_part = code_lines[:80]
            last_part  = code_lines[-150:]
            code_to_send = "\n".join(first_part) + "\n...\n" + "\n".join(last_part)
            print(f"[JARVIS] File large — sending first 80 + last 150 lines to LLM")

        prompt = f"""You are an expert {lang} developer. Analyse this code and find ALL issues:
bugs, syntax errors, logic errors, indentation problems, missing imports, junk text.

File: {filename}
```{lang}
{code_to_send[:4000]}
```

Respond in this EXACT format:
ISSUES_FOUND: yes/no
PROBLEMS:
- [line X] description of problem
FIXED_CODE:
```{lang}
<complete fixed code here>
```
EXPLANATION: brief explanation of what was wrong in 1 sentence"""

        print(f"[JARVIS] Sending to Groq LLM...")
        response = self._ask_llm(prompt)
        if not response:
            print("\n[JARVIS VSCODE] LLM returned no response — check Groq API key/connection.")
            return "I could not analyse the code right now, sir."
        print(f"[JARVIS] Got response ({len(response)} chars)")

        # Parse response
        issues_found = "yes" in response.lower().split("issues_found:")[-1][:10]
        fixed_code   = self._extract_code_block(response, lang)
        explanation  = self._extract_section(response, "EXPLANATION:")
        problems     = self._extract_section(response, "PROBLEMS:")

        if not issues_found or not fixed_code:
            return f"I reviewed {filename} and it looks clean to me, sir. No obvious issues found."

        # Store pending fix
        self._pending_fix = {
            "path":        str(path),
            "original":    code,
            "fixed":       fixed_code,
            "explanation": explanation,
            "timestamp":   time.time(),
        }
        self._save_pending_fix()

        # Print diff to terminal
        self._print_fix_preview(filename, problems, explanation, code, fixed_code)

        return (f"I found issues in {filename}. {explanation or 'See terminal for details.'}. "
                f"Say 'yes apply it' to fix, or 'no' to skip.")

    def explain_code(self) -> str:
        """Explain what the current code does."""
        result = self.read_active_code()
        if not result:
            return "I can't find your active VS Code file, sir."

        path, code = result
        lang = self._detect_language(path)

        self._voice.speak(f"Reading {path.name}, let me explain what this does.")
        print(f"\n[JARVIS] Explaining {path.name}...")

        # Send last 150 lines for large files
        code_lines = code.splitlines()
        code_to_send = "\n".join(code_lines[-150:]) if len(code_lines) > 150 else code

        prompt = f"""Explain this {lang} code clearly and concisely in 3-4 sentences max.
Focus on: what it does overall, key functions, any obvious issues.
No bullet points — plain sentences only.

```{lang}
{code_to_send[:3000]}
```"""

        print(f"[JARVIS] Sending to Groq...")
        response = self._ask_llm(prompt)
        print(f"[JARVIS] Response: {response[:100] if response else 'None'}")
        return response or "I could not analyse the code right now."

    def suggest_improvements(self) -> str:
        """Suggest improvements for current code."""
        result = self.read_active_code()
        if not result:
            return "I can't find your active VS Code file, sir."

        path, code = result
        lang = self._detect_language(path)

        self._voice.speak("Reviewing your code for improvements.")

        prompt = f"""Review this {lang} code and suggest the top 3 improvements.
Focus on: performance, readability, best practices, potential bugs.
Be specific and actionable. Keep each suggestion to 1 sentence.

```{lang}
{code[:3000]}
```

Format:
1. [improvement]
2. [improvement]  
3. [improvement]"""

        response = self._ask_llm(prompt)
        if response:
            # Print full suggestions to terminal
            print(f"\n{'='*50}")
            print(f"JARVIS CODE SUGGESTIONS: {path.name}")
            print('='*50)
            print(response)
            print('='*50 + '\n')
            # Speak summary
            lines = [l.strip() for l in response.split('\n') if l.strip() and l[0].isdigit()]
            spoken = f"I have {len(lines)} suggestions for {path.name}. " + (lines[0] if lines else "Check the terminal for details.")
            return spoken
        return "Couldn't analyse the code right now."

    def run_and_explain(self) -> str:
        """Run the current file and explain any errors."""
        result = self.read_active_code()
        if not result:
            return "I can't find your active VS Code file, sir."

        path, code = result
        lang = self._detect_language(path)

        if lang not in ("python", "javascript", "typescript"):
            return f"I can run Python and JavaScript files. This is {lang}, sir."

        self._voice.speak(f"Running {path.name} now.")

        try:
            if lang == "python":
                proc = subprocess.run(
                    [sys.executable, str(path)],
                    capture_output=True, text=True, timeout=15,
                    cwd=str(path.parent)
                )
            else:
                proc = subprocess.run(
                    ["node", str(path)],
                    capture_output=True, text=True, timeout=15,
                    cwd=str(path.parent)
                )

            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()
            returncode = proc.returncode

            print(f"\n{'='*50}")
            print(f"JARVIS RUN: {path.name}")
            print('='*50)
            if stdout:
                print(f"OUTPUT:\n{stdout}")
            if stderr:
                print(f"ERRORS:\n{stderr}")
            print(f"Exit code: {returncode}")
            print('='*50 + '\n')

            if returncode == 0 and not stderr:
                spoken = f"{path.name} ran successfully."
                if stdout and len(stdout) < 200:
                    spoken += f" Output: {stdout}"
                return spoken

            # Explain the error
            if stderr:
                error_prompt = f"""This {lang} code produced this error:

```
{stderr[:1000]}
```

Code:
```{lang}
{code[:2000]}
```

In 2 sentences max: what is the error and how to fix it?"""
                explanation = self._ask_llm(error_prompt)
                return explanation or f"{path.name} has errors. Check the terminal for details."

        except subprocess.TimeoutExpired:
            return f"{path.name} timed out after 15 seconds — possible infinite loop."
        except FileNotFoundError:
            return "Python/Node not found. Make sure it's in your PATH."
        except Exception as e:
            log.error("Run failed: %s", e)
            return f"Couldn't run {path.name}: {e}"

        return f"{path.name} ran with exit code {returncode}."

    def apply_pending_fix(self) -> str:
        """Apply the last proposed fix to the file."""
        fix = self._pending_fix or self._load_pending_fix()
        if not fix:
            return "No pending fix to apply, sir."

        # Check fix isn't stale (older than 5 minutes)
        if time.time() - fix.get("timestamp", 0) > 300:
            self._pending_fix = None
            return "The pending fix expired, sir. Ask me to fix the code again."

        path = Path(fix["path"])
        try:
            # Backup original
            backup = path.with_suffix(path.suffix + ".bak")
            backup.write_text(fix["original"], encoding="utf-8")

            # Write fixed code
            path.write_text(fix["fixed"], encoding="utf-8")
            self._pending_fix = None

            log.info("Fix applied to %s (backup: %s)", path.name, backup.name)
            print(f"\n✓ Fix applied to {path.name}")
            print(f"  Backup saved as {backup.name}\n")
            return f"Done sir. Fix applied to {path.name}. Original backed up as {backup.name}."

        except Exception as e:
            log.error("Could not apply fix: %s", e)
            return f"Couldn't apply the fix: {e}"

    def discard_pending_fix(self) -> str:
        self._pending_fix = None
        return "Okay sir, fix discarded."

    def show_active_file(self) -> str:
        """Tell user which file Jarvis is watching."""
        path = self.get_active_file()
        if path:
            code = path.read_text(encoding="utf-8")
            lines = code.count('\n') + 1
            lang  = self._detect_language(path)
            return f"I'm watching {path.name} — {lines} lines of {lang}."
        return "I'm not tracking any VS Code file right now. Save your file and I'll pick it up."

    # ── Private helpers ───────────────────────────────────────────────────────

    def _ask_llm(self, prompt: str) -> Optional[str]:
        """Ask Groq directly for code analysis — bypass short token limit."""
        try:
            from groq import Groq
            import config
            client = Groq(api_key=config.OPENAI_API_KEY)
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are an expert code reviewer. Be concise and precise."},
                    {"role": "user",   "content": prompt},
                ],
                max_tokens=2048,
                temperature=0.2,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            log.error("LLM code analysis failed: %s", e)
            return None

    def _detect_language(self, path: Path) -> str:
        ext_map = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".java": "java", ".cpp": "cpp", ".c": "c", ".cs": "csharp",
            ".html": "html", ".css": "css", ".json": "json",
            ".rs": "rust", ".go": "go", ".php": "php", ".rb": "ruby",
            ".swift": "swift", ".kt": "kotlin", ".dart": "dart",
        }
        return ext_map.get(path.suffix.lower(), "code")

    def _extract_code_block(self, text: str, lang: str) -> Optional[str]:
        """Extract code from markdown code block."""
        patterns = [
            rf"```{lang}\n(.*?)```",
            r"```\w*\n(.*?)```",
            r"FIXED_CODE:\s*```\w*\n(.*?)```",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return match.group(1).strip()
        return None

    def _extract_section(self, text: str, header: str) -> str:
        """Extract text after a header until next header."""
        if header not in text:
            return ""
        idx   = text.index(header) + len(header)
        rest  = text[idx:]
        # Stop at next ALL_CAPS: header
        next_header = re.search(r'\n[A-Z_]+:', rest)
        if next_header:
            rest = rest[:next_header.start()]
        return rest.strip()

    def _print_fix_preview(self, filename, problems, explanation, original, fixed) -> None:
        """Print a readable diff of the fix to terminal."""
        print(f"\n{'='*60}")
        print(f"JARVIS FIX PREVIEW: {filename}")
        print('='*60)
        if problems:
            print(f"PROBLEMS FOUND:\n{problems}")
            print('-'*60)
        if explanation:
            print(f"EXPLANATION: {explanation}")
            print('-'*60)

        # Show line diff
        orig_lines  = original.splitlines()
        fixed_lines = fixed.splitlines()
        changes = 0
        for i, (o, f) in enumerate(zip(orig_lines, fixed_lines)):
            if o != f:
                print(f"  Line {i+1}:")
                print(f"  - {o}")
                print(f"  + {f}")
                changes += 1
                if changes >= 20:
                    print(f"  ... and more changes")
                    break
        # Show added/removed lines
        if len(fixed_lines) > len(orig_lines):
            for line in fixed_lines[len(orig_lines):]:
                print(f"  + {line}")
        elif len(orig_lines) > len(fixed_lines):
            for line in orig_lines[len(fixed_lines):]:
                print(f"  - {line}")

        print('='*60)
        print("Say 'yes apply it' to apply, 'no' to skip.")
        print('='*60 + '\n')

    def _detect_via_process(self) -> Optional[Path]:
        """Try to find VS Code active file via running processes."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-Process code -ErrorAction SilentlyContinue | "
                 "Select-Object -ExpandProperty MainWindowTitle | "
                 "Select-Object -First 1"],
                capture_output=True, text=True, timeout=3
            )
            title = result.stdout.strip()
            if not title:
                return None
            # VS Code title: "index (1).html - mudtea - Visual Studio Code"
            # Split on " - " or " — "
            parts = re.split(r" [—-] ", title)
            if parts:
                fname = parts[0].strip().lstrip("● ").strip()
                if fname and "." in fname:
                    # Search common locations
                    search_dirs = [
                        Path("C:/Users/achaw/Downloads"),
                        Path("C:/Users/achaw/Documents"),
                        Path("C:/Users/achaw/Desktop"),
                        Path.cwd(),
                    ]
                    for search_dir in search_dirs:
                        if search_dir.exists():
                            for p in search_dir.rglob(fname):
                                if p.is_file():
                                    return p
        except Exception as e:
            log.debug("Process detection error: %s", e)
        return None

    def _save_pending_fix(self) -> None:
        if self._pending_fix:
            PENDING_FIX_FILE.parent.mkdir(exist_ok=True)
            PENDING_FIX_FILE.write_text(
                json.dumps(self._pending_fix, ensure_ascii=False),
                encoding="utf-8"
            )

    def _load_pending_fix(self) -> Optional[dict]:
        if PENDING_FIX_FILE.exists():
            try:
                return json.loads(PENDING_FIX_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None

    def _watch_active_file(self) -> None:
        """Background thread — logs when active file changes."""
        while self._running:
            try:
                path = self.get_active_file()
                if path and path != self._last_file:
                    self._last_file = path
                    log.info("VS Code active file: %s", path.name)
            except Exception:
                pass
            time.sleep(3)


# ── Plugin registration ────────────────────────────────────────────────────────

_instance: Optional[VSCodePlugin] = None


def setup(jarvis) -> None:
    """Called by PluginLoader when Jarvis starts."""
    global _instance
    _instance = VSCodePlugin(jarvis.brain, jarvis.voice)
    _instance.start()

    # Register voice/text commands
    _register_commands(jarvis)
    log.info("VS Code plugin loaded.")


def _register_commands(jarvis) -> None:
    """Inject VS Code commands into Jarvis's handle_utterance."""
    original_handle = jarvis._handle_utterance

    def patched_handle(utterance: str) -> None:
        lower = utterance.lower().strip()

        # Fix code
        if any(p in lower for p in [
            "fix my code", "fix this code", "fix the code",
            "what's wrong", "whats wrong", "what is wrong",
            "find the bug", "debug this", "check my code",
            "there is an error", "it's giving an error", "giving error",
            "something wrong with my code", "code is broken",
        ]):
            spoken = _instance.fix_code()
            jarvis.voice.speak(spoken)
            return

        # Apply fix
        if any(p in lower for p in [
            "yes apply", "apply it", "apply the fix", "yes fix it",
            "go ahead", "apply fix", "yes do it", "apply changes",
        ]):
            spoken = _instance.apply_pending_fix()
            jarvis.voice.speak(spoken)
            return

        # Discard fix
        if any(p in lower for p in [
            "no don't", "no skip", "discard", "cancel fix",
            "don't apply", "no leave it",
        ]):
            spoken = _instance.discard_pending_fix()
            jarvis.voice.speak(spoken)
            return

        # Explain code
        if any(p in lower for p in [
            "explain this code", "explain my code", "what does this do",
            "what does this code do", "explain the code",
            "what is this code doing", "tell me what this does",
        ]):
            spoken = _instance.explain_code()
            jarvis.voice.speak(spoken)
            return

        # Suggest improvements
        if any(p in lower for p in [
            "improve my code", "suggest improvements", "how can i improve",
            "make it better", "refactor this", "any suggestions",
            "code review", "review my code",
        ]):
            spoken = _instance.suggest_improvements()
            jarvis.voice.speak(spoken)
            return

        # Run file
        if any(p in lower for p in [
            "run my code", "run this file", "run the code",
            "execute this", "run it", "test my code",
            "run and check", "run the file",
        ]):
            spoken = _instance.run_and_explain()
            jarvis.voice.speak(spoken)
            return

        # Which file
        if any(p in lower for p in [
            "which file", "what file", "what are you watching",
            "what file are you on", "current file",
        ]):
            spoken = _instance.show_active_file()
            jarvis.voice.speak(spoken)
            return

        # Fallthrough to original handler
        original_handle(utterance)

    jarvis._handle_utterance = patched_handle