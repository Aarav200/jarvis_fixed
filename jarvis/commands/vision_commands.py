"""
commands/vision_commands.py — Voice commands for the vision system.
"""

from commands import register_command
from utils.logger import get_logger

log = get_logger(__name__)

# Global reference to vision context (set by main.py at startup)
_vision: "VisionContext | None" = None


def set_vision(vision) -> None:
    global _vision
    _vision = vision


@register_command("what_do_you_see")
def what_do_you_see(_: str) -> str:
    """Hey Jarvis, what do you see?"""
    if not _vision:
        return "My camera isn't active right now."
    return _vision.describe_now()


@register_command("what_am_i_doing")
def what_am_i_doing(_: str) -> str:
    """Hey Jarvis, what am I doing?"""
    if not _vision:
        return "My camera isn't active right now."
    state = _vision.capture_now()
    if not state or not state.person_present:
        return "I don't see you at the desk right now."
    if state.activity == "unknown":
        return "I can see you but I'm not sure what you're doing."
    return f"{state.activity_context} You seem to be {state.activity}."


@register_command("am_i_productive")
def am_i_productive(_: str) -> str:
    """Hey Jarvis, am I being productive?"""
    if not _vision:
        return "My camera isn't active."
    state = _vision.get_state()
    productive = ["coding", "reading", "working"]
    unproductive = ["gaming", "resting", "away", "on phone"]
    if state.activity in productive:
        return f"Yes sir, you're being productive. You're {state.activity}. Keep it up!"
    elif state.activity in unproductive:
        return f"Honestly sir, you're {state.activity}. Maybe time to get back to work?"
    return "I'm not sure — I can see you but can't tell if you're being productive."


@register_command("enable_camera")
def enable_camera(_: str) -> str:
    """Turn camera on."""
    if _vision:
        _vision.start()
        return "Camera enabled, sir."
    return "Vision system not initialized."


@register_command("disable_camera")
def disable_camera(_: str) -> str:
    """Turn camera off."""
    if _vision:
        _vision.stop()
        return "Camera disabled, sir."
    return "Vision system not initialized."


@register_command("switch_to_webcam")
def switch_to_webcam(_: str) -> str:
    """Switch from built-in to external webcam."""
    if not _vision:
        return "Vision system not initialized."
    success = _vision.switch_to_external_camera(index=1)
    if success:
        return "Switched to external webcam and enabled continuous mode, sir."
    return "Couldn't find external webcam. Make sure it's plugged in."


@register_command("teach_object")
def teach_object(param: str) -> str:
    """
    Teach Jarvis what an object is.
    param: object_name|description
    """
    if not _vision:
        return "Vision system not initialized."
    if "|" in param:
        name, desc = param.split("|", 1)
    else:
        name, desc = param, ""
    _vision.learn_object(name.strip(), desc.strip())
    return f"Got it! I'll remember that's a {name.strip()} from now on."

@register_command("what_do_i_see")
def what_do_i_see_alias(_: str) -> str:
    return what_do_you_see(_)