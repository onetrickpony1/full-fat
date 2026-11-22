"""Plain questions and messages in the terminal."""

from __future__ import annotations

import sys
import textwrap
import time

_KEEP = "\x00"


def keep(value) -> str:
    """Text that must stay on one line and intact, such as a path with a space in it."""
    return str(value).replace(" ", _KEEP)


class UI:
    def __init__(self, yes: bool = False, inp=input, out=None):
        self.yes = yes
        self._input = inp
        self._out = out or (lambda s: print(s, flush=True))

    def say(self, text: str = "") -> None:
        for para in text.split("\n"):
            line = textwrap.fill(para, 100, subsequent_indent="  " if para.startswith("  ") else "",
                                 break_long_words=False, break_on_hyphens=False) if para else ""
            self._out(line.replace(_KEEP, " "))

    def heading(self, text: str) -> None:
        self._out("")
        self._out(f"== {text}")

    def ok(self, text: str) -> None:
        self.say(f"  OK: {text}")

    def problem(self, text: str) -> None:
        self.say(f"  Problem: {text}")

    def _ask(self, prompt: str) -> str | None:
        try:
            return self._input(prompt)
        except EOFError:
            return None

    def yes_no(self, question: str, default: bool = True) -> bool:
        if self.yes:
            return default
        hint = "[Y/n]" if default else "[y/N]"
        while True:
            ans = self._ask(f"{question} {hint} ")
            if ans is None:
                return default
            ans = ans.strip().lower()
            if not ans:
                return default
            if ans[0] in "yj":
                return True
            if ans[0] == "n":
                return False
            self.say("Please type y for yes or n for no, then press Enter.")

    def choose(self, question: str, options: list[str], default: int = 1) -> int:
        """Numbered choice; returns the 1-based number."""
        if self.yes:
            return default
        self.say(question)
        for i, o in enumerate(options, 1):
            self.say(f"  {i}) {o}")
        while True:
            ans = self._ask(f"Type a number and press Enter [{default}]: ")
            if ans is None or not ans.strip():
                return default
            if ans.strip().isdigit() and 1 <= int(ans) <= len(options):
                return int(ans)
            self.say(f"Please type a number from 1 to {len(options)}.")

    def enter(self, message: str) -> bool:
        """Wait for Enter. False when there is nobody to press it."""
        if self.yes:
            return False
        return self._ask(f"{message} ") is not None


def waiting(ui: UI, message: str, check, poll: float = 2.0, timeout: float | None = None) -> bool:
    """Show message, then poll check() until it is true. Ctrl+C stops."""
    ui.say(message)
    start = time.monotonic()
    shown = 0
    while not check():
        if timeout is not None and time.monotonic() - start > timeout:
            return False
        time.sleep(poll)
        shown += 1
        if sys.stdout.isatty() and shown % 5 == 0:
            print("  still waiting...", flush=True)
    return True
