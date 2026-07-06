"""
ImageAnalyzer
=============
Phase 1 & 11 — Vision pipeline.
Analyzes images/sketches/screenshots to extract 3D asset specifications.
"""

import base64
import logging
from typing import Dict, Optional

logger = logging.getLogger("jarvis.game_agent.pipeline.image_analyzer")


class ImageAnalyzer:
    """
    Accepts an image (file path, bytes, or PIL Image) and a text command.
    Returns a structured asset specification for BlenderBridge.
    """

    VISION_SYSTEM_PROMPT = """
You are a 3D asset analyst and game art director.
Analyze the provided image and extract a detailed 3D asset specification.
Return ONLY JSON:
{
  "type": "vehicle|character|prop|environment|weapon|building",
  "name": "descriptive_asset_name",
  "style": "low_poly|realistic|stylized|cartoon",
  "material": "metal|wood|stone|fabric|plastic|organic",
  "primary_colors": ["#hex1", "#hex2"],
  "dimensions": {"width": 1.0, "height": 1.5, "depth": 2.0},
  "key_features": ["feature1", "feature2"],
  "polygon_target": 800,
  "blender_primitives": ["cube", "cylinder"],
  "export_format": "fbx",
  "notes": "any important detail for the 3D artist"
}
"""

    def __init__(self, llm_caller=None):
        self._llm = llm_caller

    def analyze(self, image, command: str) -> Dict:
        """
        image: file path (str), bytes, or PIL Image. Can be None.
        command: user's voice/text command.
        Returns asset spec dict.
        """
        if image is None:
            logger.info("[ImageAnalyzer] No image — using text command only")
            return self._analyze_text_only(command)

        image_data = self._load_image(image)
        if image_data is None:
            return self._analyze_text_only(command)

        return self._analyze_with_vision(image_data, command)

    def _analyze_with_vision(self, image_b64: str, command: str) -> Dict:
        """Send image + command to vision-capable LLM."""
        if not self._llm:
            logger.warning("[ImageAnalyzer] No LLM connected — using text fallback")
            return self._analyze_text_only(command)

        # Build multi-modal message
        try:
            # Try Jarvis-style LLM with image support
            if hasattr(self._llm, "analyze_image"):
                result = self._llm.analyze_image(
                    image_b64=image_b64,
                    prompt=f"Analyze this image for 3D asset creation: {command}",
                    system=self.VISION_SYSTEM_PROMPT
                )
            else:
                # Fallback: describe image in text prompt
                result = self._llm(
                    f"Analyze this image for 3D asset creation. "
                    f"Command: {command}. "
                    f"[Image provided but vision not available — infer from command]",
                    system=self.VISION_SYSTEM_PROMPT
                )

            if isinstance(result, dict):
                return result
            # Parse JSON from string response
            import json, re
            text = re.sub(r"```json|```", "", str(result)).strip()
            return json.loads(text)

        except Exception as e:
            logger.error("[ImageAnalyzer] Vision analysis failed: %s", e)
            return self._analyze_text_only(command)

    def _analyze_text_only(self, command: str) -> Dict:
        """Fallback: build spec from command text alone."""
        cmd = command.lower()

        # Keyword-based spec builder
        spec = {
            "export_format": "fbx",
            "style": "low_poly",
            "polygon_target": 600,
            "blender_primitives": ["cube"]
        }

        # Type detection
        if any(w in cmd for w in ["car", "vehicle", "truck", "bus", "bike"]):
            spec.update({"type": "vehicle", "name": "vehicle",
                         "material": "metal", "primary_colors": ["#cc3333", "#111111"],
                         "blender_primitives": ["cube", "cylinder"],
                         "dimensions": {"width": 2.0, "height": 1.5, "depth": 4.5},
                         "polygon_target": 1000})
        elif any(w in cmd for w in ["character", "person", "human", "npc", "hero"]):
            spec.update({"type": "character", "name": "character",
                         "material": "fabric", "primary_colors": ["#f4c2a1", "#334455"],
                         "blender_primitives": ["cube", "uv_sphere", "cylinder"],
                         "dimensions": {"width": 0.6, "height": 1.8, "depth": 0.4},
                         "polygon_target": 800})
        elif any(w in cmd for w in ["tree", "plant", "bush", "flower"]):
            spec.update({"type": "vegetation", "name": "tree",
                         "material": "organic", "primary_colors": ["#4a7c59", "#8B4513"],
                         "blender_primitives": ["cylinder", "ico_sphere"],
                         "dimensions": {"width": 1.5, "height": 4.0, "depth": 1.5},
                         "polygon_target": 200})
        elif any(w in cmd for w in ["building", "house", "structure", "wall"]):
            spec.update({"type": "building", "name": "building",
                         "material": "stone", "primary_colors": ["#aaaaaa", "#888877"],
                         "blender_primitives": ["cube"],
                         "dimensions": {"width": 8.0, "height": 6.0, "depth": 8.0},
                         "polygon_target": 400})
        elif any(w in cmd for w in ["sword", "weapon", "gun", "bow"]):
            spec.update({"type": "weapon", "name": "sword",
                         "material": "metal", "primary_colors": ["#C0C0C0", "#8B4513"],
                         "blender_primitives": ["cube", "cylinder"],
                         "dimensions": {"width": 0.1, "height": 1.2, "depth": 0.05},
                         "polygon_target": 300})
        else:
            # Generic prop
            words = [w for w in cmd.split() if len(w) > 3 and w not in
                     ["create","make","build","unity","jarvis","blender","model"]]
            name  = "_".join(words[:2]) if words else "prop"
            spec.update({"type": "prop", "name": name,
                         "material": "plastic", "primary_colors": ["#888888"],
                         "polygon_target": 300})

        return spec

    def _load_image(self, image) -> Optional[str]:
        """Convert image to base64 string."""
        try:
            # Already base64 string
            if isinstance(image, str) and not image.startswith("/") and len(image) > 200:
                return image

            # File path
            if isinstance(image, str):
                with open(image, "rb") as f:
                    return base64.b64encode(f.read()).decode("utf-8")

            # Bytes
            if isinstance(image, bytes):
                return base64.b64encode(image).decode("utf-8")

            # PIL Image
            try:
                import io
                from PIL import Image as PILImage
                if isinstance(image, PILImage.Image):
                    buf = io.BytesIO()
                    image.save(buf, format="PNG")
                    return base64.b64encode(buf.getvalue()).decode("utf-8")
            except ImportError:
                pass

            logger.warning("[ImageAnalyzer] Unknown image type: %s", type(image))
            return None

        except Exception as e:
            logger.error("[ImageAnalyzer] Could not load image: %s", e)
            return None
