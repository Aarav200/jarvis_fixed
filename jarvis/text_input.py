"""
text_input.py — Text input mode for Jarvis.
"""

import threading
import sys
from utils.logger import get_logger

log = get_logger(__name__)

GREEN  = "\033[92m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
RED    = "\033[91m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


class TextInputHandler:
    SPECIAL_COMMANDS = {
        "/help":       "show_help",
        "/status":     "which ai are you using",
        "/clear":      "clear memory",
        "/vision":     "show camera",
        "/hide":       "hide camera",
        "/quit":       "stop",
        "/exit":       "stop",
        "/time":       "what time is it",
        "/date":       "what is the date",
        "/see":        "what do you see",
        "/doing":      "what am i doing",
        "/shirt":      "what am i wearing",
        "/habits":     "what are my habits",
        "/yesterday":  "what did i do yesterday",
        "/today":      "what did i do today",
        "/memory":     "what do you remember about me",
        "/startup":    "what are my startup routines",
        "/productive": "am i being productive",
    }

    def __init__(self, jarvis_instance) -> None:
        self._jarvis  = jarvis_instance
        self._thread  = None
        self._running = False

    def start(self) -> None:
        self._running = True
        self._thread  = threading.Thread(
            target=self._input_loop,
            daemon=True,
            name="jarvis-text-input"
        )
        self._thread.start()
        log.info("Text input mode active.")

    def stop(self) -> None:
        self._running = False

    def _input_loop(self) -> None:
        self._print_welcome()
        while self._running:
            try:
                sys.stdout.write(f"{CYAN}You:{RESET} ")
                sys.stdout.flush()
                line = sys.stdin.readline()
                if not line:
                    break
                text = line.strip()
                if not text:
                    continue

                if text.startswith("/"):
                    mapped = self.SPECIAL_COMMANDS.get(text.lower())
                    if mapped == "show_help":
                        self._print_help()
                        continue
                    elif mapped:
                        text = mapped
                    else:
                        print(f"{RED}Unknown command: {text}{RESET}")
                        print(f"Type {CYAN}/help{RESET} for commands.")
                        continue

                log.info("[TEXT INPUT] '%s'", text)
                print(f"{YELLOW}⚡ {text}{RESET}")
                self._jarvis._handle_utterance(text)

            except (EOFError, KeyboardInterrupt):
                break
            except Exception as e:
                log.debug("Text input error: %s", e)

    def _print_welcome(self) -> None:
        print(f"\n{BOLD}{CYAN}{'─'*50}{RESET}")
        print(f"{BOLD}{CYAN}  JARVIS TEXT INPUT ACTIVE{RESET}")
        print(f"{CYAN}  Type commands or use voice.{RESET}")
        print(f"{CYAN}  Type {YELLOW}/help{CYAN} for special commands.{RESET}")
        print(f"{BOLD}{CYAN}{'─'*50}{RESET}\n")

    def _print_help(self) -> None:
        print(f"\n{BOLD}{YELLOW}Special Commands:{RESET}")
        for cmd, action in self.SPECIAL_COMMANDS.items():
            if action != "show_help":
                print(f"  {CYAN}{cmd:<12}{RESET} → {action}")
        print(f"\n{YELLOW}Or type naturally:{RESET}")
        print(f"  {CYAN}open chrome{RESET}")
        print(f"  {CYAN}what colour is my shirt{RESET}")
        print(f"  {CYAN}send whatsapp to Akshay saying hello{RESET}")
        print()