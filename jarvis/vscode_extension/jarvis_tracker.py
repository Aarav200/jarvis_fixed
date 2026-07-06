"""
vscode_extension/jarvis_tracker.py

Run this alongside Jarvis. It watches VS Code's process title
and writes the active file path to memory/vscode_active.txt
every time you switch files.

Run in a separate terminal:
    python vscode_extension/jarvis_tracker.py
"""

import re
import subprocess
import time
from pathlib import Path
import sys

ACTIVE_FILE = Path("memory/vscode_active.txt")
ACTIVE_FILE.parent.mkdir(exist_ok=True)

print("Jarvis VS Code tracker running...")
print("Switch files in VS Code and Jarvis will know what you're editing.")
print("Press Ctrl+C to stop.\n")

last_file = ""

while True:
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-Process code -ErrorAction SilentlyContinue | "
             "Select-Object -ExpandProperty MainWindowTitle | "
             "Select-Object -First 1"],
            capture_output=True, text=True, timeout=3
        )
        title = result.stdout.strip()

        if title and ("Visual Studio Code" in title or "VS Code" in title):
            # Extract filename from title: "main.py - jarvis - Visual Studio Code"
            match = re.match(r"^([^-•]+?)[\s]*[-•]", title)
            if match:
                filename = match.group(1).strip()
                # Remove leading dot for modified indicator
                filename = filename.lstrip("● ").strip()

                if filename and filename != last_file and "." in filename:
                    # Search for the file
                    found = None
                    search_dirs = [
                        Path("C:/Users/achaw/Downloads"),
                        Path("C:/Users/achaw/Documents"),
                        Path("C:/Users/achaw/Desktop"),
                        Path("C:/Users/achaw/OneDrive"),
                        Path.home(),
                        Path.cwd(),
                    ]
                    for search_dir in search_dirs:
                        if search_dir.exists():
                            matches = list(search_dir.rglob(filename))
                            if matches:
                                found = matches[0]
                                break

                    if found:
                        ACTIVE_FILE.write_text(str(found), encoding="utf-8")
                        last_file = filename
                        print(f"✓ Tracking: {found}")
                    else:
                        # Just write the filename, Jarvis will search
                        ACTIVE_FILE.write_text(filename, encoding="utf-8")
                        last_file = filename
                        print(f"~ Detected: {filename} (searching...)")

    except KeyboardInterrupt:
        print("\nTracker stopped.")
        sys.exit(0)
    except Exception as e:
        pass

    time.sleep(2)