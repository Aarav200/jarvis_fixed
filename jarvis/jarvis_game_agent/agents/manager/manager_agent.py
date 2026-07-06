"""
ManagerAgent
============
The brain of the multi-agent system.
Receives every command, decides which agents to invoke, sequences tasks,
and assembles the final result.
"""

import logging
from typing import Dict, Optional

from ..base_agent import BaseAgent

logger = logging.getLogger("jarvis.game_agent.manager")


class ManagerAgent(BaseAgent):
    NAME = "manager"
    ROLE = "Coordinates all specialized agents to complete game development tasks"

    # Intent → handler map
    INTENT_MAP = {
        "full_game": "_handle_full_game",
        "asset_3d": "_handle_asset_3d",
        "code": "_handle_code",
        "scene": "_handle_scene",
        "gdd": "_handle_gdd",
        "test": "_handle_test",
        "blender": "_handle_blender",
        "preference": "_handle_preference",
        "unknown": "_handle_unknown",
    }

    def __init__(self, memory_manager=None, llm_caller=None):
        super().__init__(memory_manager, llm_caller)
        self._agents = {}   # lazily loaded

    # ─────────────────────────────────────────
    # PUBLIC ENTRY POINT
    # ─────────────────────────────────────────

    def run(self, command: str, image=None, context: Dict = None) -> Dict:
        print("=== MANAGER RUN LOADED ===", flush=True)

        context = context or {}
        context["image"] = image

        logger.info("[Manager] Processing: %s", command)
        print("[MANAGER] Classifying intent", flush=True)

        intent = self._classify_intent(command, image)

        logger.info("[Manager] Intent: %s", intent)
        print("[MANAGER] Intent =", intent, flush=True)

        handler_name = self.INTENT_MAP.get(intent, "_handle_unknown")
        print("[MANAGER] Handler =", handler_name, flush=True)

        handler = getattr(self, handler_name)

        print("[MANAGER] Calling handler", flush=True)
        result = handler(command, context)

        print("[MANAGER] Handler returned", flush=True)

        # Store project state
        if self.memory and result.get("project_id"):
            self.memory.update_project(
                result["project_id"],
                {
                    "last_command": command,
                    "last_intent": intent,
                }
            )

        print("[MANAGER] Returning result", flush=True)
        return result

    # ─────────────────────────────────────────
    # INTENT CLASSIFICATION
    # ─────────────────────────────────────────
    


    def _classify_intent(self, command: str, image=None) -> str:
        cmd = command.lower()
        try:
            from ...asset_intent import detect_asset_intent

            if detect_asset_intent(command):
                return "blender"
        except Exception:
            pass

        if image and any(w in cmd for w in ["create this", "model this", "build this", "import this"]):
            return "asset_3d"

        if any(w in cmd for w in ["create a game", "make a game", "build a game",
                                  "full game", "horror game", "survival game",
                                  "racing game", "rpg", "platformer game"]):
            return "full_game"

        if any(w in cmd for w in ["write a script", "write an inventory", "write a combat",
                                  "write a save", "write an ai", "code a", "create a system"]):
            return "code"

        if any(w in cmd for w in ["create a scene", "build a scene", "setup scene",
                                  "import to unity", "add to unity"]):
            return "scene"

        if any(w in cmd for w in ["game design", "design document", "gdd", "game plan",
                                  "mechanics", "progression"]):
            return "gdd"

        if any(w in cmd for w in ["test", "find bugs", "bug report", "simulate player"]):
            return "test"

        if any(w in cmd for w in ["blender","low poly","3d model","model a", "tree", "pine tree", "oak tree","rock", "boulder","sword", "fantasy sword", "medieval sword","house","car", "vehicle","create a tree", "create a crate", "create a sword"]):
            return "blender"

        if any(w in cmd for w in ["remember", "prefer", "i like", "always use",
                                  "my style", "set style"]):
            return "preference"

        return "unknown"

    # ─────────────────────────────────────────
    # HANDLERS
    # ─────────────────────────────────────────

    def _handle_full_game(self, command: str, context: Dict) -> Dict:
        """Phase 10: Full game generation pipeline."""
        from ..planner.planner_agent import PlannerAgent
        from ..asset.asset_agent import AssetAgent
        from ..programming.programming_agent import ProgrammingAgent
        from ..testing.testing_agent import TestingAgent
        from ..critic.critic_agent import CriticAgent

        planner = PlannerAgent(self.memory, self._llm)
        plan = planner.run(command, context)

        project_id = plan.get("project_id", "project_001")
        gdd = plan.get("gdd", {})

        logger.info("[Manager] GDD created. Starting asset pipeline...")

        asset_agent = AssetAgent(self.memory, self._llm)
        assets = asset_agent.run(gdd.get("assets", []), context)

        logger.info("[Manager] Assets ready. Starting code generation...")

        prog_agent = ProgrammingAgent(self.memory, self._llm)
        code = prog_agent.run(gdd.get("systems", []), context)

        logger.info("[Manager] Code ready. Starting tests...")

        test_result = {"bugs": [], "status": "skipped"}
        if context.get("enable_testing", True):
            tester = TestingAgent(self.memory, self._llm)
            test_result = tester.run(project_id, context)

        critic = CriticAgent(self.memory, self._llm)
        review = critic.run(
            {"plan": plan, "assets": assets, "code": code, "tests": test_result},
            context,
        )

        # Save lessons
        if self.memory:
            self.memory.add_lesson(
                category="full_game",
                what_worked=f"Generated game: {command[:60]}",
                what_failed=str(test_result.get("bugs", [])),
                notes=review.get("summary", "")
            )
            self.memory.save_project(project_id, {
                "command": command,
                "gdd": gdd,
                "assets": assets,
                "code": code,
                "tests": test_result,
                "review": review
            })

        response = (
            f"✅ Game project created: {project_id}\n"
            f"  📋 GDD: {len(gdd.get('mechanics', []))} mechanics\n"
            f"  🎨 Assets: {len(assets.get('created', []))} created\n"
            f"  💻 Scripts: {len(code.get('scripts', []))} scripts\n"
            f"  🐛 Bugs found: {len(test_result.get('bugs', []))}\n"
            f"  ⭐ Review: {review.get('score', 'N/A')}/10"
        )

        return {
            "project_id": project_id,
            "plan": plan,
            "assets": assets,
            "code": code,
            "tests": test_result,
            "review": review,
            "response": response,
        }

    def _handle_asset_3d(self, command: str, context: Dict) -> Dict:
        """Phase 1+2: Image → 3D asset → Unity."""
        from ...pipeline.image_to_3d.image_analyzer import ImageAnalyzer
        from ...blender.scripts.blender_bridge import BlenderBridge
        from ...unity.editor_bridge.unity_bridge import UnityBridge

        image = context.get("image")
        analyzer = ImageAnalyzer(self._llm)
        spec = analyzer.analyze(image, command)

        blender = BlenderBridge()
        asset = blender.create_from_spec(spec)

        response = f"🎨 3D asset created: {spec.get('type', 'object')}"

        if asset.get("exported") and context.get("auto_import", True):
            unity = UnityBridge()
            imported = unity.import_asset(asset["export_path"])
            response += f"\n✅ Imported into Unity: {imported.get('path', '')}"

        return {"spec": spec, "asset": asset, "response": response}

    def _handle_code(self, command: str, context: Dict) -> Dict:
        """Phase 5: Autonomous C# code generation."""
        from ..programming.programming_agent import ProgrammingAgent
        prog = ProgrammingAgent(self.memory, self._llm)
        result = prog.run([command], context)
        scripts = result.get("scripts", [])
        names = [s.get("name", "script") for s in scripts]
        return {"result": result, "response": f"💻 Generated: {', '.join(names)}"}

    def _handle_scene(self, command: str, context: Dict) -> Dict:
        """Phase 3: Unity scene construction."""
        from ...unity.scene_manager.scene_manager import SceneManager
        sm = SceneManager()
        result = sm.create_scene(command, context)
        return {"result": result, "response": f"🌍 Scene created: {result.get('scene_name', 'NewScene')}"}

    def _handle_gdd(self, command: str, context: Dict) -> Dict:
        """Phase 4: Game design document."""
        from ..planner.planner_agent import PlannerAgent
        planner = PlannerAgent(self.memory, self._llm)
        plan = planner.run(command, context)
        gdd = plan.get("gdd", {})
        return {
            "gdd": gdd,
            "response": (
                f"📋 GDD created: {gdd.get('title', 'New Game')}\n"
                f"  Mechanics: {len(gdd.get('mechanics', []))}\n"
                f"  Systems: {len(gdd.get('systems', []))}"
            )
        }

    def _handle_test(self, command: str, context: Dict) -> Dict:
        """Phase 7: Game testing."""
        from ..testing.testing_agent import TestingAgent
        tester = TestingAgent(self.memory, self._llm)
        result = tester.run("current_project", context)
        bugs = result.get("bugs", [])
        return {
            "result": result,
            "response": (
                f"🐛 Testing complete. Found {len(bugs)} issue(s).\n"
                + "\n".join(f"  - {b}" for b in bugs[:5])
            )
        }

    def _handle_blender(self, command: str, context: Dict) -> Dict:
        print("[BLENDER] Using ProceduralAssetAgent", flush=True)

        from jarvis_game_agent.blender.scripts.procedural_asset_agent import ProceduralAssetAgent
        from jarvis_game_agent.asset_intent import detect_asset_intent

        intent = detect_asset_intent(command)
        if isinstance(intent, tuple):
            asset_name = intent[1]
        else:
            asset_name = intent

        if not asset_name:
            return {
                "response": "Could not determine which asset to create."
            }

        agent = ProceduralAssetAgent()

        result = agent.create(asset_name)

        return {
            "result": result,
            "response": f"Created: {asset_name}"
        }

    def _handle_preference(self, command: str, context: Dict) -> Dict:
        """Phase 8: Store user preferences."""
        if not self.memory:
            return {"response": "Memory not available."}

        cmd = command.lower()
        saved = []

        if "low poly" in cmd or "lowpoly" in cmd:
            self.memory.set_preference("art_style", "low_poly")
            self.memory.set_style("art", "low_poly")
            saved.append("art style: low poly")
        if "realistic" in cmd:
            self.memory.set_preference("art_style", "realistic")
            self.memory.set_style("art", "realistic")
            saved.append("art style: realistic")
        if "pixel" in cmd:
            self.memory.set_preference("art_style", "pixel")
            saved.append("art style: pixel")
        if "c#" in cmd or "csharp" in cmd:
            self.memory.set_style("code", "csharp_clean")
            saved.append("code style: clean C#")

        if not saved:
            # Let LLM extract preference
            if self._llm:
                extracted = self.ask_llm(
                    f"Extract a key-value preference from: '{command}'. "
                    "Return JSON like {{\"key\": \"...\", \"value\": \"...\"}}",
                    expect_json=True
                )
                if isinstance(extracted, dict) and "key" in extracted:
                    self.memory.set_preference(extracted["key"], extracted["value"])
                    saved.append(f"{extracted['key']}: {extracted['value']}")

        saved_str = ", ".join(saved) if saved else "preference noted"
        return {"response": f"✅ Remembered: {saved_str}"}

    def _handle_unknown(self, command: str, context: Dict) -> Dict:
        return {
            "response": (
                "I'm not sure what game dev task that is. Try:\n"
                "  'Create a horror game...'\n"
                "  'Create this car in Unity' [+ image]\n"
                "  'Write an inventory system'\n"
                "  'Test the game and find bugs'"
            )
        }