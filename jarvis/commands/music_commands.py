import urllib.parse
import subprocess
import webbrowser
import threading
import time
from commands import register_command
from utils.logger import get_logger
log = get_logger(__name__)

_CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
_USER_DATA  = r"C:\Users\achaw\AppData\Local\Google\Chrome\User Data"
_APP_ID = "cinhimbnkkaeohfgghhklpknlkffjgod"

def _launch_and_play(query: str) -> None:
    try:
        import pyautogui
        import pygetwindow as gw

        encoded = urllib.parse.quote_plus(query)
        subprocess.Popen([
            _CHROME_EXE,
            f"--app-id={_APP_ID}",
            f"--app=https://music.youtube.com/search?q={encoded}",
            f"--user-data-dir={_USER_DATA}",
            "--profile-directory=Default",
        ])

        # Wait for app and page to load
        time.sleep(5)

        # Find the YouTube Music window and bring it to front
        windows = gw.getWindowsWithTitle("YouTube Music")
        if windows:
            win = windows[0]
            win.activate()
            time.sleep(1)

            # Click the Play button — it's roughly at center-left of the window
            # Based on your screenshot the Play button is at ~480x325 in the app
            win_x = win.left
            win_y = win.top
            play_x = win_x + 480
            play_y = win_y + 325
            pyautogui.click(play_x, play_y)
            log.info("Clicked Play at (%d, %d)", play_x, play_y)

    except Exception as e:
        log.error("Playback failed: %s", e)
        encoded = urllib.parse.quote_plus(query)
        webbrowser.open(f"https://music.youtube.com/search?q={encoded}")

@register_command("play_music")
def play_music(query: str) -> str:
    if not query:
        return "What would you like me to play?"
    threading.Thread(target=_launch_and_play, args=(query,), daemon=True).start()
    return f"Playing {query}."

@register_command("play_song")
def play_song(query: str) -> str:
    return play_music(query)

@register_command("play_youtube")
def play_youtube(query: str) -> str:
    if not query:
        return "What would you like to watch?"
    encoded = urllib.parse.quote_plus(query)
    webbrowser.open(f"https://www.youtube.com/results?search_query={encoded}")
    return f"Opening YouTube for {query}."

@register_command("pause_music")
def pause_music(_: str) -> str:
    return "Pausing music."