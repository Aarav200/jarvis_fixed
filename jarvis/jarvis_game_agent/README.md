# 🎮 Jarvis Game Agent — Final Phase
**Autonomous Game Development Module**

---

## What This Is

A **self-contained module** that transforms Jarvis into an autonomous game development studio.
Zero changes to `main.py` or `brain.py`.

---

## Setup (2 Steps)

### Step 1 — Drop folder into Jarvis
```
your_jarvis_project/
├── main.py
├── brain.py
└── jarvis_game_agent/   ← drop here
```

### Step 2 — Add one line to `main.py`
```python
from jarvis_game_agent import GameAgentPlugin
GameAgentPlugin.register(jarvis)   # jarvis = your Jarvis instance
```

That's it. All voice commands are now live.

---

## Configuration

Edit `config/game_agent_config.json`:
```json
{
  "BLENDER_EXECUTABLE": "blender",
  "UNITY_PROJECT_PATH": "C:/Users/Aarav/UnityProjects/YourGame",
  "UNITY_WS_PORT": 6400,
  "DEFAULT_ART_STYLE": "low_poly"
}
```

---

## Unity Setup

Copy `unity/editor_bridge/JarvisUnityBridge.cs` into:
```
YourUnityProject/Assets/Editor/JarvisUnityBridge.cs
```
Unity will auto-start the bridge when the Editor opens.

---

## Voice Commands

| Command | What Happens |
|---------|-------------|
| `"Create a horror game in an abandoned hospital"` | Full GDD → Assets → Code → Test → Build |
| `"Create this car in Unity"` + image | Image → Blender 3D model → Unity import |
| `"Create a low poly tree"` | Blender auto-generates and exports |
| `"Write an inventory system"` | C# script generated + auto-fixed + saved |
| `"Create a survival game scene"` | Unity scene created with lighting + terrain |
| `"Test the game and find bugs"` | Code analysis + AI bug report |
| `"I prefer low poly art style"` | Stored in memory permanently |

---

## Architecture

```
jarvis_game_agent/
│
├── plugin.py                    ← Single registration point
├── config/
│   └── game_agent_config.json  ← All settings
│
├── agents/
│   ├── manager/                 ← Orchestrates everything
│   ├── planner/                 ← Creates GDD + task breakdown
│   ├── asset/                   ← 3D asset pipeline
│   ├── programming/             ← C# generation + auto-fix
│   ├── testing/                 ← Bug detection + reports
│   ├── optimization/            ← Performance fixes
│   └── critic/                  ← Quality scoring
│
├── blender/
│   └── scripts/blender_bridge.py  ← Headless Blender control
│
├── unity/
│   ├── editor_bridge/
│   │   ├── unity_bridge.py      ← Python side (WS + HTTP + File)
│   │   └── JarvisUnityBridge.cs ← Unity Editor side
│   └── scene_manager/           ← Scene construction
│
├── pipeline/
│   ├── image_to_3d/             ← Vision → asset spec
│   └── learning_system.py       ← Post-project evaluation
│
└── memory/
    ├── memory_manager.py        ← All persistent storage
    ├── projects/                ← Per-project state
    ├── lessons/                 ← Lessons learned
    ├── preferences/             ← User preferences
    └── styles/                  ← Art/code style memory
```

---

## Data Flow

```
Voice Command
     │
     ▼
GameAgentPlugin.handle()
     │
     ▼
ManagerAgent._classify_intent()
     │
     ├─ full_game  → PlannerAgent → AssetAgent → ProgrammingAgent → TestingAgent → CriticAgent
     ├─ asset_3d   → ImageAnalyzer → BlenderBridge → UnityBridge
     ├─ code       → ProgrammingAgent (generate → compile → fix loop)
     ├─ scene      → SceneManager → UnityBridge
     ├─ blender    → BlenderBridge (headless)
     ├─ test       → TestingAgent (analyze + report)
     └─ preference → MemoryManager (stored permanently)
```

---

## How Unity Communication Works

```
Python                          Unity Editor
  │                                  │
  │──── WebSocket (port 6400) ──────▶│  (preferred)
  │                                  │
  │──── HTTP POST (port 6401) ──────▶│  (fallback)
  │                                  │
  │──── cmd_*.json files ───────────▶│  (offline fallback)
  │◀─── resp_*.json files ───────────│
```

---

## Jarvis Plugin API Compatibility

The plugin auto-detects which Jarvis API is available:
- `jarvis.register_plugin(plugin)` → full plugin registration
- `jarvis.on_command(phrase, fn)` → phrase-based registration  
- Manual: `GameAgentPlugin.handle(command, image=image_bytes)`

---

## Extending

Add a new agent in `agents/myagent/myagent.py`, inherit `BaseAgent`, implement `run()`.
Register it in `agents/manager/manager_agent.py` INTENT_MAP.
No other files need changing.
