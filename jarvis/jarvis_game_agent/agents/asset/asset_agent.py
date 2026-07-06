"""
AssetAgent
==========
Phase 1+2 — Manages creation of all 3D assets.
Coordinates ImageAnalyzer → BlenderBridge → UnityBridge.
"""

from typing import Dict, List
from ..base_agent import BaseAgent


class AssetAgent(BaseAgent):
    NAME = "asset"
    ROLE = "Creates 3D assets via Blender and imports them into Unity"

    SPEC_SYSTEM_PROMPT = """
You are a 3D asset designer. Given an asset description, return a detailed spec as JSON:
{
  "name": "asset_name",
  "type": "character|prop|environment|vehicle|weapon",
  "style": "low_poly|realistic|stylized",
  "polygon_target": 500,
  "colors": ["#hex1", "#hex2"],
  "materials": ["material_name"],
  "dimensions": {"width": 1, "height": 2, "depth": 1},
  "blender_primitives": ["cube", "cylinder"],
  "texture_resolution": 512,
  "export_format": "fbx"
}
Return ONLY JSON, no other text.
"""

    def run(self, asset_list: List, context: Dict = None) -> Dict:
        context  = context or {}
        created  = []
        failed   = []

        if not asset_list:
            return {"created": [], "failed": [], "response": "No assets to create."}

        for asset_desc in asset_list:
            # Accept string or dict
            if isinstance(asset_desc, str):
                name = asset_desc
                desc = asset_desc
            else:
                name = asset_desc.get("name", "unknown")
                desc = str(asset_desc)

            try:
                spec   = self._generate_spec(desc, context)
                result = self._create_asset(spec, context)
                created.append({"name": name, "spec": spec, "result": result})
                self.log.info("[Asset] ✅ Created: %s", name)
            except Exception as e:
                self.log.error("[Asset] ❌ Failed: %s — %s", name, e)
                failed.append({"name": name, "error": str(e)})

        return {"created": created, "failed": failed}

    def _generate_spec(self, description: str, context: Dict) -> Dict:
        art_style = "low_poly"
        if self.memory:
            art_style = self.memory.get_style("art", "low_poly")

        prompt = (
            f"Create a 3D asset spec for: {description}\n"
            f"Art style: {art_style}\n"
            f"Keep polygon count low for game use."
        )
        return self.ask_llm(prompt, system=self.SPEC_SYSTEM_PROMPT, expect_json=True)

    def _create_asset(self, spec: Dict, context: Dict) -> Dict:
        from ...blender.scripts.blender_bridge import BlenderBridge
        bridge = BlenderBridge()
        result = bridge.create_from_spec(spec)

        if result.get("exported") and context.get("auto_import_unity", True):
            from ...unity.editor_bridge.unity_bridge import UnityBridge
            unity = UnityBridge()
            unity.import_asset(result.get("export_path", ""))

        return result
