"""
test_voice_integration.py
=========================
Run this BEFORE patching brain.py to verify everything works.
No Blender needed for these tests — they only test intent detection.

Run from jarvis/ root:
    python jarvis_game_agent/voice_integration/test_voice_integration.py
"""

import sys
import pathlib

# Make sure asset_intent is importable
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from asset_intent import detect_asset_intent, spoken_name

# ── Test cases: (voice command, expected_spec or None) ────────
TEST_CASES = [
    # ✅ Should match
    ("Jarvis create a pine tree",           "pine_tree"),
    ("create an oak tree",                  "oak_tree"),
    ("Jarvis make a fantasy sword",         "fantasy_sword"),
    ("Jarvis create a medieval sword",      "medieval_sword"),
    ("create a house",                      "small_house"),
    ("make a car",                          "compact_car"),
    ("Jarvis create a rock",                "small_rock"),
    ("build me a boulder",                  "large_boulder"),
    ("generate an oak",                     "oak_tree"),
    ("create a cottage",                    "small_house"),
    ("Jarvis make a magic sword",           "fantasy_sword"),
    ("give me a pine",                      "pine_tree"),
    ("build a vehicle",                     "compact_car"),
    ("Jarvis create a large boulder",       "large_boulder"),
    ("make a tree",                         "pine_tree"),
    ("Jarvis generate a compact car",       "compact_car"),

    # ❌ Should NOT match (existing Jarvis commands)
    ("what is the weather today",           None),
    ("play some music",                     None),
    ("set a timer for 10 minutes",          None),
    ("who is calling",                      None),
    ("open visual studio code",             None),
    ("tell me a joke",                      None),
    ("what time is it",                     None),
    ("send a message to mom",               None),
]


def run_tests():
    passed = 0
    failed = 0

    print("=" * 60)
    print("  Voice Integration — Intent Detection Tests")
    print("=" * 60)

    for command, expected_spec in TEST_CASES:
        is_asset, spec = detect_asset_intent(command)

        if expected_spec is None:
            # Should NOT match
            if not is_asset:
                status = "✅ PASS"
                passed += 1
            else:
                status = f"❌ FAIL  (matched '{spec}' but should not match)"
                failed += 1
        else:
            # Should match with correct spec
            if is_asset and spec == expected_spec:
                status = "✅ PASS"
                passed += 1
            elif is_asset and spec != expected_spec:
                status = f"❌ FAIL  (got '{spec}', expected '{expected_spec}')"
                failed += 1
            else:
                status = f"❌ FAIL  (no match, expected '{expected_spec}')"
                failed += 1

        print(f"  {status}")
        print(f"     CMD:  {command!r}")
        if is_asset:
            print(f"     →     {spec}  ({spoken_name(spec)})")
        print()

    print("=" * 60)
    print(f"  Results: {passed} passed  |  {failed} failed  |  {len(TEST_CASES)} total")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    ok = run_tests()
    sys.exit(0 if ok else 1)
