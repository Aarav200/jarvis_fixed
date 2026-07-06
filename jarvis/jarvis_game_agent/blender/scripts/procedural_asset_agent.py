"""
procedural_asset_agent.py
=========================
Drop this into jarvis_game_agent/blender/scripts/
Replaces the old blender_bridge.py primitive-only generator.

Usage (standalone):
    python procedural_asset_agent.py "pine tree"
    python procedural_asset_agent.py "fantasy sword"
    python procedural_asset_agent.py all

Usage (from Jarvis):
    from jarvis_game_agent.blender.scripts.procedural_asset_agent import ProceduralAssetAgent
    agent = ProceduralAssetAgent()
    result = agent.create("pine tree")
"""

import os
import json
import subprocess
import pathlib
import logging
import sys
from typing import Dict, Optional

log = logging.getLogger("jarvis.game_agent.blender.procedural")

# ── Paths ─────────────────────────────────────────────────────
HERE        = pathlib.Path(__file__).parent
SPECS_DIR   = HERE.parent.parent / "asset_specs"          # jarvis_game_agent/asset_specs/
SCRIPTS_DIR = HERE                                          # same folder as this file
GENERATOR   = HERE / "procedural_mesh_generator.py"
EXPORTS_DIR = HERE.parent.parent.parent / "projects" / "assets"  # jarvis_game_agent/../projects/assets/

# Fallback: check next to this file for specs
if not SPECS_DIR.exists():
    SPECS_DIR = HERE / "asset_specs"

EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Name aliases (voice command → spec filename) ───────────────
ALIASES = {
    # trees
    "pine tree":          "pine_tree",
    "pine":               "pine_tree",
    "oak tree":           "oak_tree",
    "oak":                "oak_tree",
    # rocks
    "small rock":         "small_rock",
    "rock":               "small_rock",
    "large boulder":      "large_boulder",
    "boulder":            "large_boulder",
    # weapons
    "fantasy sword":      "fantasy_sword",
    "magic sword":        "fantasy_sword",
    "medieval sword":     "medieval_sword",
    "sword":              "medieval_sword",
    # vehicles
    "compact car":        "compact_car",
    "car":                "compact_car",
    # buildings
    "small house":        "small_house",
    "house":              "small_house",
    "building":           "small_house",
}


class ProceduralAssetAgent:
    """
    Reads a JSON asset spec and drives Blender headlessly
    to produce a proper, recognizable low-poly mesh.
    """

    def __init__(self,
                 blender_exe: str = r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
                 specs_dir: pathlib.Path = None,
                 exports_dir: pathlib.Path = None,
                 timeout: int = 120):
        self.blender   = blender_exe
        self.specs_dir = pathlib.Path(specs_dir)   if specs_dir   else SPECS_DIR
        self.out_dir   = pathlib.Path(exports_dir) if exports_dir else EXPORTS_DIR
        self.timeout   = timeout
        self.generator = GENERATOR

    # ─────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────

    def create(self, asset_name: str) -> Dict:
        """
        Main entry point.
        asset_name: natural language or exact spec name
        Returns dict with status, export_path, asset_name.
        """
        spec_name = self._resolve_name(asset_name)
        spec_path = self._find_spec(spec_name)

        if spec_path is None:
            log.error("[Procedural] No spec found for: %s", asset_name)
            return {
                "status":  "error",
                "error":   f"No spec file found for '{asset_name}'. "
                           f"Looked for '{spec_name}.json' in {self.specs_dir}",
                "asset_name": asset_name
            }

        with open(spec_path) as f:
            spec = json.load(f)

        fmt         = spec.get("export_format", "fbx")
        clean_name  = spec.get("name", spec_name)
        export_path = str(self.out_dir / clean_name / f"{clean_name}.{fmt}")
        os.makedirs(os.path.dirname(export_path), exist_ok=True)

        log.info("[Procedural] Creating: %s → %s", clean_name, export_path)
        print(f"[ProceduralAssetAgent] Launching Blender for: {clean_name}")

        success = self._run_blender(str(spec_path), export_path)

        if success and os.path.exists(export_path):
            size_kb = os.path.getsize(export_path) // 1024
            log.info("[Procedural] ✅ %s exported (%d KB)", clean_name, size_kb)
            return {
                "status":      "success",
                "asset_name":  clean_name,
                "export_path": export_path,
                "format":      fmt,
                "size_kb":     size_kb,
                "spec_path":   str(spec_path),
            }
        else:
            log.error("[Procedural] ❌ Export failed for %s", clean_name)
            return {
                "status":     "error",
                "error":      "Blender export failed or file not found",
                "asset_name": clean_name,
                "tried_path": export_path
            }

    def create_batch(self, asset_names: list) -> list:
        """Create multiple assets. Returns list of results."""
        return [self.create(name) for name in asset_names]

    def list_available(self) -> list:
        """List all available spec names."""
        if not self.specs_dir.exists():
            return []
        return [f.stem for f in self.specs_dir.glob("*.json")]

    # ─────────────────────────────────────────
    # INTERNAL
    # ─────────────────────────────────────────

    def _resolve_name(self, raw: str) -> str:
        """Map natural language to spec file name."""
        cleaned = raw.lower().strip()
        if cleaned in ALIASES:
            return ALIASES[cleaned]
        # Try direct match (underscored)
        underscored = cleaned.replace(" ", "_")
        if (self.specs_dir / f"{underscored}.json").exists():
            return underscored
        # Partial match
        for alias, spec in ALIASES.items():
            if alias in cleaned or cleaned in alias:
                return spec
        return underscored  # best guess

    def _find_spec(self, spec_name: str) -> Optional[pathlib.Path]:
        """Find a spec JSON file by name."""
        candidate = self.specs_dir / f"{spec_name}.json"
        if candidate.exists():
            return candidate
        # Case-insensitive search
        for f in self.specs_dir.glob("*.json"):
            if f.stem.lower() == spec_name.lower():
                return f
        return None

    def _run_blender(self, spec_path: str, output_path: str) -> bool:
        """Run Blender headlessly with the generator script."""
        if not self.generator.exists():
            log.error("[Procedural] Generator script not found: %s", self.generator)
            return False

        cmd = [
            self.blender,
            "--background",
            "--python", str(self.generator),
            "--",
            spec_path,
            output_path
        ]

        log.info("[Procedural] CMD: %s", " ".join(cmd))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            # Print Blender stdout for debugging
            if result.stdout:
                for line in result.stdout.splitlines():
                    if any(tag in line for tag in ["[OK]", "[DONE]", "[INFO]",
                                                    "[WARN]", "[ERROR]", "→"]):
                        print(f"  Blender: {line}")

            if result.returncode != 0:
                log.error("[Procedural] Blender exit code %d", result.returncode)
                if result.stderr:
                    log.error("[Procedural] stderr:\n%s", result.stderr[-800:])
                return False

            return True

        except FileNotFoundError:
            log.error(
                "[Procedural] Blender not found at '%s'. "
                "Install Blender and add it to PATH, or set blender_exe.",
                self.blender
            )
            return False

        except subprocess.TimeoutExpired:
            log.error("[Procedural] Blender timed out after %ds", self.timeout)
            return False

        except Exception as e:
            log.error("[Procedural] Unexpected error: %s", e)
            return False


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s"
    )

    agent = ProceduralAssetAgent()

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python procedural_asset_agent.py 'pine tree'")
        print("  python procedural_asset_agent.py 'fantasy sword'")
        print("  python procedural_asset_agent.py all")
        print()
        print("Available specs:", agent.list_available())
        sys.exit(0)

    target = " ".join(sys.argv[1:])

    if target.lower() == "all":
        names = agent.list_available()
        print(f"Building all {len(names)} assets: {names}")
        results = agent.create_batch(names)
        ok  = [r for r in results if r["status"] == "success"]
        err = [r for r in results if r["status"] != "success"]
        print(f"\n✅ {len(ok)} succeeded  ❌ {len(err)} failed")
        for e in err:
            print(f"  FAILED: {e['asset_name']} — {e.get('error', '?')}")
    else:
        result = agent.create(target)
        if result["status"] == "success":
            print(f"\n✅ {result['asset_name']} → {result['export_path']} ({result['size_kb']} KB)")
        else:
            print(f"\n❌ Failed: {result.get('error', 'unknown error')}")
        sys.exit(0 if result["status"] == "success" else 1)
