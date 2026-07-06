"""
BlenderBridge
=============
Phase 2 — Controls Blender headlessly via Python API.
Creates meshes, applies materials, exports FBX/GLTF.
"""

import os
import json
import subprocess
import tempfile
import pathlib
import logging
from typing import Dict

from ...config.settings import Settings

logger = logging.getLogger("jarvis.game_agent.blender")


class BlenderBridge:
    """
    Communicates with Blender via:
    1. blender --background --python script.py (headless)
    2. Passes a JSON spec file to the script
    3. Blender exports FBX/GLTF to output path
    """

    SCRIPTS_DIR = pathlib.Path(__file__).parent

    def create_from_spec(self, spec: Dict) -> Dict:
        print("[BLENDER_BRIDGE] Enter create_from_spec", flush=True)
        """Create a 3D asset from an asset specification dict."""
        asset_name   = spec.get("name", "asset").replace(" ", "_")
        print("[BLENDER_BRIDGE] Asset =", asset_name, flush=True)
        export_fmt   = spec.get("export_format", "fbx").lower()
        print("[BLENDER_BRIDGE] Format =", export_fmt, flush=True)
        output_dir   = pathlib.Path(Settings.PROJECTS_DIR) / "assets" / asset_name
        output_dir.mkdir(parents=True, exist_ok=True)
        export_path  = str(output_dir / f"{asset_name}.{export_fmt}")
        print("[BLENDER_BRIDGE] Export path =", export_path, flush=True)

        script_path  = self._write_blender_script(spec, export_path)
        print("[BLENDER_BRIDGE] Script =", script_path, flush=True)
        success      = self._run_blender(script_path)
        print("[BLENDER_BRIDGE] Success =", success, flush=True)

        if success and os.path.exists(export_path):
            logger.info("[Blender] ✅ Exported: %s", export_path)
            return {"exported": True, "export_path": export_path,
                    "asset_name": asset_name, "format": export_fmt}
        else:
            logger.warning("[Blender] ⚠️ Blender not available — returning spec only")
            return {"exported": False, "export_path": export_path,
                    "asset_name": asset_name, "spec": spec,
                    "note": "Blender not installed or export failed"}

    def create_from_command(self, command: str) -> Dict:
        print("[BLENDER_BRIDGE] Enter create_from_command", flush=True)
        """Natural language → asset spec → Blender."""
        spec = self._command_to_spec(command)
        print("[BLENDER_BRIDGE] Spec =", spec, flush=True)
        return self.create_from_spec(spec)

    def _command_to_spec(self, command: str) -> Dict:
        cmd = command.lower()
        spec = {"export_format": "fbx", "style": "low_poly"}

        if "tree" in cmd:
            spec.update({"name": "low_poly_tree", "type": "vegetation",
                          "blender_primitives": ["cylinder", "ico_sphere"],
                          "colors": ["#4a7c59", "#8B4513"], "polygon_target": 200})
        elif "crate" in cmd:
            spec.update({"name": "sci_fi_crate", "type": "prop",
                          "blender_primitives": ["cube"],
                          "colors": ["#444444", "#888888"], "polygon_target": 150})
        elif "sword" in cmd:
            spec.update({"name": "medieval_sword", "type": "weapon",
                          "blender_primitives": ["cube", "cylinder"],
                          "colors": ["#C0C0C0", "#8B4513"], "polygon_target": 300})
        elif "car" in cmd:
            spec.update({"name": "car", "type": "vehicle",
                          "blender_primitives": ["cube", "cylinder"],
                          "colors": ["#cc3333", "#111111"], "polygon_target": 800})
        elif "character" in cmd or "person" in cmd:
            spec.update({"name": "character", "type": "character",
                          "blender_primitives": ["cube", "cylinder", "uv_sphere"],
                          "colors": ["#f4c2a1", "#334455"], "polygon_target": 600})
        else:
            # Generic prop
            words = [w for w in cmd.split() if len(w) > 3]
            name  = "_".join(words[:3]) if words else "prop"
            spec.update({"name": name, "type": "prop",
                          "blender_primitives": ["cube"],
                          "colors": ["#888888"], "polygon_target": 200})

        return spec

    def _write_blender_script(self, spec: Dict, export_path: str) -> str:
        print("[WRITE_SCRIPT] START", flush=True)
        """Generate the Python script that Blender will execute."""
        spec_json = json.dumps(spec)
        print("[WRITE_SCRIPT] JSON OK", flush=True)

        script = f"""
import bpy
import json
import math

# Clear scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

spec = {spec_json}
export_path = r"{export_path}"
asset_type = spec.get("type", "prop")
primitives = spec.get("blender_primitives", ["cube"])
colors = spec.get("colors", ["#888888"])
poly_target = spec.get("polygon_target", 300)

created_objects = []

# Create geometry
for i, primitive in enumerate(primitives):
    if primitive == "cube":
        bpy.ops.mesh.primitive_cube_add(location=(i * 0.5, 0, 0))
    elif primitive == "cylinder":
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, location=(0, 0, i * 0.5))
    elif primitive == "uv_sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(segments=8, ring_count=8, location=(0, 0, i))
    elif primitive == "ico_sphere":
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, location=(0, 0, i))
    elif primitive == "cone":
        bpy.ops.mesh.primitive_cone_add(vertices=8, location=(i * 0.3, 0, 0))
    elif primitive == "torus":
        bpy.ops.mesh.primitive_torus_add(location=(0, 0, i))

    obj = bpy.context.active_object
    created_objects.append(obj)

    # Assign material
    mat = bpy.data.materials.new(name=f"Mat_{{primitive}}_{{i}}")
    mat.use_nodes = True
    color_hex = colors[i % len(colors)].lstrip("#")
    r = int(color_hex[0:2], 16) / 255.0
    g = int(color_hex[2:4], 16) / 255.0
    b = int(color_hex[4:6], 16) / 255.0
    principled = mat.node_tree.nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = (r, g, b, 1.0)
        principled.inputs["Metallic"].default_value = 0.3 if "metal" in spec.get("materials", []) else 0.0
        principled.inputs["Roughness"].default_value = 0.5
    obj.data.materials.append(mat)

# Join all objects into one
if len(created_objects) > 1:
    bpy.ops.object.select_all(action='DESELECT')
    for obj in created_objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = created_objects[0]
    bpy.ops.object.join()

final_obj = bpy.context.active_object
if final_obj:
    final_obj.name = spec.get("name", "asset")

# Apply scale
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# Export 
export_format = spec.get("export_format", "fbx").lower()
if export_format == "fbx":
    bpy.ops.export_scene.fbx(
        filepath=export_path,
        use_selection=False,
        mesh_smooth_type='FACE',
        add_leaf_bones=False,
        bake_anim=False
    )
elif export_format in ["gltf", "glb"]:
    bpy.ops.export_scene.gltf(
        filepath=export_path,
        export_format='GLB' if export_format == "glb" else 'GLTF_SEPARATE'
    )

print(f"[BlenderBridge] Exported: {{export_path}}")
"""
        print("[WRITE_SCRIPT] SCRIPT BUILT", flush=True)
        # Write to temp file
        tmp = tempfile.NamedTemporaryFile(
            mode="w",encoding="utf-8", suffix=".py", delete=False,
            prefix="jarvis_blender_"
        )
        print(type(script), flush=True)
        print("[WRITE_SCRIPT] Script length =", len(script), flush=True)

        try:
            tmp.write(script)
            print("[WRITE_SCRIPT] SCRIPT WRITTEN", flush=True)
        except Exception as e:
            print("[WRITE_SCRIPT] WRITE ERROR =", repr(e), flush=True)
            raise
        tmp.close()

        print("[WRITE_SCRIPT] TEMP FILE CLOSED", flush=True)
        print("[WRITE_SCRIPT] Returning:", tmp.name, flush=True)

        return tmp.name

    def _run_blender(self, script_path: str) -> bool:
        blender_exe = Settings.BLENDER_EXECUTABLE
        try:
            result = subprocess.run(
                [blender_exe, "--background", "--python", script_path],
                capture_output=True, text=True,
                timeout=Settings.BLENDER_TIMEOUT
            )
            if result.returncode == 0:
                return True
            logger.error("[Blender] Error: %s", result.stderr[-500:])
            return False
        except FileNotFoundError:
            logger.warning("[Blender] Blender executable not found at: %s", blender_exe)
            return False
        except subprocess.TimeoutExpired:
            logger.error("[Blender] Timeout after %ds", Settings.BLENDER_TIMEOUT)
            return False
        finally:
            try:
                os.unlink(script_path)
            except Exception:
                pass
