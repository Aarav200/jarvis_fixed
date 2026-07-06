"""
gui.py — Optional Tkinter dashboard for Jarvis.

Provides a visual status panel showing:
  • Current status (listening / processing / speaking)
  • Last utterance and response
  • Conversation history feed
  • Quick-command buttons

Launch alongside main.py:
    python gui.py          # Launches full Jarvis + GUI
    or
    python main.py         # Headless mode (no GUI)
"""

import threading
import time
import tkinter as tk
from tkinter import scrolledtext, font as tkfont
from queue import Queue, Empty

import config
from brain import Brain
from command_router import CommandRouter
from plugins import PluginLoader
from utils.logger import get_logger
from utils.text_helpers import sanitise_for_tts
from voice import VoiceEngine

log = get_logger(__name__)

# ─── Colour palette ───────────────────────────────────────────────────────────
BG       = "#0d0f14"
PANEL    = "#161b22"
ACCENT   = "#00d4ff"
GREEN    = "#39d353"
YELLOW   = "#f0c040"
RED      = "#ff4c4c"
TEXT     = "#e6edf3"
MUTED    = "#7d8590"

STATUS_COLOURS = {
    "idle":       MUTED,
    "listening":  GREEN,
    "processing": YELLOW,
    "speaking":   ACCENT,
    "error":      RED,
}


# ─────────────────────────────────────────────────────────────────────────────
class JarvisGUI:
    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._root.title("Jarvis — Voice Assistant")
        self._root.configure(bg=BG)
        self._root.geometry("700x520")
        self._root.resizable(False, False)

        self._ui_queue: Queue = Queue()   # thread-safe updates from backend

        self._build_ui()
        self._start_backend()
        self._poll_ui_queue()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        mono = tkfont.Font(family="Courier New", size=10)
        title_font = tkfont.Font(family="Courier New", size=18, weight="bold")
        label_font = tkfont.Font(family="Courier New", size=9)

        # Header
        header = tk.Frame(self._root, bg=BG)
        header.pack(fill="x", padx=20, pady=(20, 5))
        tk.Label(header, text="J A R V I S", font=title_font,
                 fg=ACCENT, bg=BG).pack(side="left")

        # Status indicator
        self._status_dot = tk.Label(header, text="●", font=("Courier New", 18),
                                     fg=MUTED, bg=BG)
        self._status_dot.pack(side="right")
        self._status_label = tk.Label(header, text="IDLE",
                                       font=label_font, fg=MUTED, bg=BG)
        self._status_label.pack(side="right", padx=(0, 5))

        # Divider
        tk.Frame(self._root, bg=ACCENT, height=1).pack(fill="x", padx=20)

        # Last interaction display
        mid = tk.Frame(self._root, bg=BG)
        mid.pack(fill="x", padx=20, pady=10)

        tk.Label(mid, text="You said:", font=label_font, fg=MUTED, bg=BG).grid(
            row=0, column=0, sticky="w")
        self._user_var = tk.StringVar(value="—")
        tk.Label(mid, textvariable=self._user_var, font=mono, fg=TEXT,
                 bg=PANEL, wraplength=600, justify="left",
                 padx=8, pady=4, relief="flat").grid(
            row=1, column=0, sticky="ew", pady=(2, 8))

        tk.Label(mid, text="Jarvis:", font=label_font, fg=MUTED, bg=BG).grid(
            row=2, column=0, sticky="w")
        self._jarvis_var = tk.StringVar(value="—")
        tk.Label(mid, textvariable=self._jarvis_var, font=mono, fg=ACCENT,
                 bg=PANEL, wraplength=600, justify="left",
                 padx=8, pady=4, relief="flat").grid(
            row=3, column=0, sticky="ew", pady=(2, 8))
        mid.columnconfigure(0, weight=1)

        # Conversation feed
        tk.Label(self._root, text="Conversation History",
                 font=label_font, fg=MUTED, bg=BG).pack(anchor="w", padx=20)
        self._history_box = scrolledtext.ScrolledText(
            self._root, font=mono, bg=PANEL, fg=TEXT,
            relief="flat", height=10, state="disabled",
            insertbackground=ACCENT,
        )
        self._history_box.pack(fill="both", expand=True, padx=20, pady=(2, 10))

        # Quick commands
        btn_frame = tk.Frame(self._root, bg=BG)
        btn_frame.pack(fill="x", padx=20, pady=(0, 15))

        quick_cmds = [
            ("🕐 Time",        "what time is it"),
            ("📅 Date",        "what is today's date"),
            ("🔊 Vol 50",      "set volume to 50"),
            ("🔍 Search",      "search the web for"),
            ("🧹 Clear",       "clear memory"),
            ("⏹ Stop",        "stop"),
        ]
        for i, (label, cmd) in enumerate(quick_cmds):
            btn = tk.Button(
                btn_frame, text=label,
                font=label_font, bg=PANEL, fg=TEXT,
                activebackground=ACCENT, activeforeground=BG,
                relief="flat", padx=10, pady=5, cursor="hand2",
                command=lambda c=cmd: self._inject_command(c),
            )
            btn.grid(row=0, column=i, padx=3)

    # ── Backend wiring ─────────────────────────────────────────────────────────

    def _start_backend(self) -> None:
        loader = PluginLoader(config.PLUGINS_DIR)
        loader.load_all()

        self._voice = VoiceEngine()
        self._brain = Brain()
        self._router = CommandRouter()
        self._inject_queue: Queue = Queue()

        self._voice.start_listening()

        self._backend_thread = threading.Thread(
            target=self._backend_loop, daemon=True, name="jarvis-backend"
        )
        self._backend_thread.start()

    def _backend_loop(self) -> None:
        self._push_status("idle")
        self._push_status("listening")
        while True:
            # Check injected commands from buttons
            try:
                utterance = self._inject_queue.get_nowait()
            except Empty:
                utterance = self._voice.get_utterance(timeout=0.5)

            if utterance is None:
                continue

            utterance = utterance.strip()
            if not utterance:
                continue

            self._push_ui(("user", utterance))
            self._push_status("processing")

            response = self._brain.think(utterance)
            spoken = response.spoken_text

            if response.action:
                result = self._router.dispatch(response.action)
                if result == CommandRouter.SIGNAL_CLEAR_MEMORY:
                    self._brain.clear_short_term()
                    spoken = "Memory cleared."
                elif result == CommandRouter.SIGNAL_STOP:
                    spoken = "Goodbye."
                    self._push_ui(("jarvis", spoken))
                    self._push_status("idle")
                    self._voice.speak(spoken)
                    self._root.after(1500, self._root.destroy)
                    return
                elif not spoken or spoken == "I'll take care of that.":
                    spoken = result

            self._push_ui(("jarvis", spoken))
            self._push_status("speaking")
            self._voice.speak(spoken)
            self._push_status("listening")

    def _inject_command(self, text: str) -> None:
        self._inject_queue.put(text)

    # ── Thread-safe UI updates ─────────────────────────────────────────────────

    def _push_ui(self, item) -> None:
        self._ui_queue.put(item)

    def _push_status(self, status: str) -> None:
        self._ui_queue.put(("status", status))

    def _poll_ui_queue(self) -> None:
        try:
            while True:
                item = self._ui_queue.get_nowait()
                if item[0] == "status":
                    self._update_status(item[1])
                elif item[0] == "user":
                    self._user_var.set(item[1])
                    self._append_history(f"You: {item[1]}")
                elif item[0] == "jarvis":
                    self._jarvis_var.set(item[1])
                    self._append_history(f"Jarvis: {item[1]}\n")
        except Empty:
            pass
        self._root.after(100, self._poll_ui_queue)

    def _update_status(self, status: str) -> None:
        colour = STATUS_COLOURS.get(status, MUTED)
        self._status_dot.config(fg=colour)
        self._status_label.config(text=status.upper(), fg=colour)

    def _append_history(self, text: str) -> None:
        self._history_box.config(state="normal")
        self._history_box.insert(tk.END, text + "\n")
        self._history_box.see(tk.END)
        self._history_box.config(state="disabled")


# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    root = tk.Tk()
    app = JarvisGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
