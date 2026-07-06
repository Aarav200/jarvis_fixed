"""
procedural_mesh_generator.py
============================
Blender Python script — run headlessly:
    blender --background --python procedural_mesh_generator.py -- <spec.json> <output.fbx>

Supports: cube, cone, cylinder, ico_sphere, plane, tapered_box
"""

import bpy
import bmesh
import json
import sys
import os
import math
from mathutils import Vector, Euler


# ─────────────────────────────────────────────────────────────
# ARGUMENT PARSING
# ─────────────────────────────────────────────────────────────

def get_args():
    """Get spec path and output path from command line after '--'."""
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    if len(argv) < 2:
        print("[ERROR] Usage: blender --background --python script.py -- spec.json output.fbx")
        sys.exit(1)

    return argv[0], argv[1]


# ─────────────────────────────────────────────────────────────
# SCENE SETUP
# ─────────────────────────────────────────────────────────────

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    # Remove orphan data
    for block in bpy.data.meshes:
        bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        bpy.data.materials.remove(block)


# ─────────────────────────────────────────────────────────────
# MATERIAL CREATION
# ─────────────────────────────────────────────────────────────

def make_material(name: str, props: dict) -> bpy.types.Material:
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    nodes.clear()

    output   = nodes.new("ShaderNodeOutputMaterial")
    bsdf     = nodes.new("ShaderNodeBsdfPrincipled")
    output.location = (300, 0)
    bsdf.location   = (0, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    base_color = props.get("base_color", [0.5, 0.5, 0.5, 1.0])
    bsdf.inputs["Base Color"].default_value = base_color
    bsdf.inputs["Roughness"].default_value  = props.get("roughness", 0.5)
    bsdf.inputs["Metallic"].default_value   = props.get("metallic", 0.0)

    # Emission for gems / headlights
    if props.get("emit", False):
        bsdf.inputs["Emission"].default_value  = base_color
        bsdf.inputs["Emission Strength"].default_value = props.get("emit_strength", 1.0)

    return mat


# ─────────────────────────────────────────────────────────────
# TAPERED BOX (the key primitive not in Blender natively)
# ─────────────────────────────────────────────────────────────

def create_tapered_box(name: str, params: dict) -> bpy.types.Object:
    """
    Creates a box that is wider at the base than the top.
    base_x, base_y = bottom face dimensions
    top_x,  top_y  = top face dimensions
    height         = Z height
    """
    bx = params.get("base_x", 1.0) / 2
    by = params.get("base_y", 1.0) / 2
    tx = params.get("top_x",  0.8) / 2
    ty = params.get("top_y",  0.8) / 2
    h  = params.get("height", 1.0)

    mesh = bpy.data.meshes.new(name)
    obj  = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()

    # 8 verts: 4 bottom, 4 top
    v0 = bm.verts.new((-bx, -by, 0))
    v1 = bm.verts.new(( bx, -by, 0))
    v2 = bm.verts.new(( bx,  by, 0))
    v3 = bm.verts.new((-bx,  by, 0))

    v4 = bm.verts.new((-tx, -ty, h))
    v5 = bm.verts.new(( tx, -ty, h))
    v6 = bm.verts.new(( tx,  ty, h))
    v7 = bm.verts.new((-tx,  ty, h))

    bm.faces.new([v3, v2, v1, v0])          # bottom
    bm.faces.new([v4, v5, v6, v7])          # top
    bm.faces.new([v0, v1, v5, v4])          # front
    bm.faces.new([v2, v3, v7, v6])          # back
    bm.faces.new([v1, v2, v6, v5])          # right
    bm.faces.new([v3, v0, v4, v7])          # left

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    return obj


# ─────────────────────────────────────────────────────────────
# PRIMITIVE CREATORS
# ─────────────────────────────────────────────────────────────

def create_primitive(comp_id: str, ptype: str, params: dict) -> bpy.types.Object:
    """Dispatch to the right Blender primitive or custom builder."""

    if ptype == "tapered_box":
        return create_tapered_box(comp_id, params)

    # For all bpy.ops primitives, deselect first
    bpy.ops.object.select_all(action='DESELECT')

    if ptype == "cube":
        size = params.get("size", 1.0)
        bpy.ops.mesh.primitive_cube_add(size=size)

    elif ptype == "cone":
        bpy.ops.mesh.primitive_cone_add(
            vertices  = params.get("vertices", 8),
            radius1   = params.get("radius1", 1.0),
            radius2   = params.get("radius2", 0.0),
            depth     = params.get("depth",   2.0)
        )

    elif ptype == "cylinder":
        bpy.ops.mesh.primitive_cylinder_add(
            vertices = params.get("vertices", 12),
            radius   = params.get("radius",   1.0),
            depth    = params.get("depth",    2.0)
        )

    elif ptype == "ico_sphere":
        bpy.ops.mesh.primitive_ico_sphere_add(
            subdivisions = params.get("subdivisions", 2),
            radius       = params.get("radius",       1.0)
        )

    elif ptype == "uv_sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments    = params.get("segments",  16),
            ring_count  = params.get("rings",     8),
            radius      = params.get("radius",    1.0)
        )

    elif ptype == "plane":
        bpy.ops.mesh.primitive_plane_add(
            size = params.get("size", 2.0)
        )

    else:
        print(f"[WARN] Unknown primitive type '{ptype}' for '{comp_id}' — using cube")
        bpy.ops.mesh.primitive_cube_add(size=0.5)

    obj = bpy.context.active_object
    obj.name = comp_id
    return obj


# ─────────────────────────────────────────────────────────────
# TRANSFORM
# ─────────────────────────────────────────────────────────────

def apply_transform(obj: bpy.types.Object, transform: dict):
    loc = transform.get("location", [0, 0, 0])
    rot = transform.get("rotation", [0, 0, 0])   # Euler XYZ radians
    scl = transform.get("scale",    [1, 1, 1])

    obj.location = Vector(loc)
    obj.rotation_euler = Euler(rot, 'XYZ')
    obj.scale = Vector(scl)

    # Apply so transforms are baked into mesh data
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    obj.select_set(False)


# ─────────────────────────────────────────────────────────────
# ASSIGN MATERIAL
# ─────────────────────────────────────────────────────────────

def assign_material(obj: bpy.types.Object, mat: bpy.types.Material):
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


# ─────────────────────────────────────────────────────────────
# JOIN ALL OBJECTS
# ─────────────────────────────────────────────────────────────

def join_objects(objects: list, final_name: str) -> bpy.types.Object:
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    result = bpy.context.active_object
    result.name = final_name
    return result


# ─────────────────────────────────────────────────────────────
# EXPORT
# ─────────────────────────────────────────────────────────────

def export_asset(obj: bpy.types.Object, output_path: str, fmt: str = "fbx"):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    fmt = fmt.lower()
    if fmt == "fbx":
        bpy.ops.export_scene.fbx(
            filepath          = output_path,
            use_selection     = True,
            mesh_smooth_type  = 'FACE',
            add_leaf_bones    = False,
            bake_anim         = False,
            apply_unit_scale  = True,
            apply_scale_options = 'FBX_SCALE_ALL'
        )
    elif fmt in ("gltf", "glb"):
        bpy.ops.export_scene.gltf(
            filepath      = output_path,
            use_selection = True,
            export_format = 'GLB' if fmt == "glb" else 'GLTF_SEPARATE'
        )
    else:
        print(f"[WARN] Unknown format '{fmt}' — defaulting to FBX")
        bpy.ops.export_scene.fbx(filepath=output_path, use_selection=True)

    print(f"[OK] Exported: {output_path}")


# ─────────────────────────────────────────────────────────────
# MAIN GENERATOR
# ─────────────────────────────────────────────────────────────

def generate(spec_path: str, output_path: str):
    with open(spec_path) as f:
        spec = json.load(f)

    asset_name = spec.get("name", "asset")
    fmt        = spec.get("export_format", "fbx")
    print(f"[INFO] Generating: {asset_name}")

    clear_scene()

    # ── Build material cache ──────────────────────────────────
    mat_defs = spec.get("materials", {})
    materials = {}
    for mat_name, mat_props in mat_defs.items():
        materials[mat_name] = make_material(mat_name, mat_props)

    # ── Build components ──────────────────────────────────────
    components = spec.get("geometry", {}).get("components", [])
    created_objects = []

    for comp in components:
        cid   = comp.get("id",        f"comp_{len(created_objects)}")
        ctype = comp.get("type",      "cube")
        params    = comp.get("params",    {})
        transform = comp.get("transform", {})
        mat_name  = comp.get("material",  None)

        print(f"  → {cid} ({ctype})")

        obj = create_primitive(cid, ctype, params)
        apply_transform(obj, transform)

        if mat_name and mat_name in materials:
            assign_material(obj, materials[mat_name])
        elif mat_name:
            print(f"  [WARN] Material '{mat_name}' not found in spec")

        created_objects.append(obj)

    if not created_objects:
        print("[ERROR] No components created")
        return

    # ── Join everything ───────────────────────────────────────
    if len(created_objects) > 1:
        final = join_objects(created_objects, asset_name)
    else:
        final = created_objects[0]
        final.name = asset_name

    # ── Origin to geometry centre ─────────────────────────────
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')

    # ── Recalculate normals ───────────────────────────────────
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')

    # ── Export ────────────────────────────────────────────────
    export_asset(final, output_path, fmt)
    print(f"[DONE] {asset_name} → {output_path}")


# ─────────────────────────────────────────────────────────────
# ENTRY
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    spec_path, output_path = get_args()
    generate(spec_path, output_path)
