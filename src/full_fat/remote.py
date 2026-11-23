"""Claude chats that also open in the browser (Claude Code's Remote Control).

`claude --remote-control "Full Fat"` starts the usual chat in the Terminal and also lists it as "Full Fat" at
https://claude.ai/code, where the user can read and type in a browser (checked with Claude Code 2.1.330 on a Max
plan). Approval questions show in both places. Closing the Terminal ends the chat, and /exit in the Terminal
archives the browser session. It needs a Pro or Max plan signed in with a Claude account: not an API key, not
a custom ANTHROPIC_BASE_URL or a cloud provider. On Team and Enterprise plans an admin must allow it.

How the browser opens: Full Fat starts Claude Code in the same Terminal window and waits for it (the Terminal
works as usual: Claude Code reads and writes it directly, and Full Fat leaves Ctrl+C to it). Meanwhile a helper
thread of Full Fat waits until Claude Code records the browser session for its process and then opens it.
Claude Code 2.1.330 writes `<config dir>/sessions/<pid>.json` with `bridgeSessionId` ("session_...") once
Remote Control is connected; https://claude.ai/code/<that ID> is the link Claude Code itself prints. That file
is Claude Code's own and may change, so when it never shows up the helper opens nothing, and the Terminal text
tells the user where to find the chat. Reading Claude Code's printed link instead would need Full Fat to sit
between Claude Code and the Terminal, which breaks the Terminal chat on some systems.

Full Fat waits rather than handing the process over (exec) so that it can tell when Claude Code refuses Remote
Control (an admin can switch it off for a Team, Enterprise or Education plan; only a Max plan was tried): if
Claude Code ends with an error within a few seconds and nothing opened, Full Fat starts the chat again in the
Terminal only (cli.run_chat, refused below).

The same helper copies JASP's plot images into the chat folder while the chat runs (plots.py), because the
browser only opens files inside the folder the chat runs in. It stops when Claude Code ends.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

from . import apps, plots

NAME = "Full Fat"  # the name the chat has at claude.ai/code
CODE_URL = "https://claude.ai/code"
SESSION_ID = re.compile(r"session_[A-Za-z0-9]{8,64}")
# Signs that Claude Code is not using a Claude account (API key, own server or a cloud provider)
NOT_ACCOUNT_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "CLAUDE_CODE_USE_BEDROCK",
                   "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY")
WAIT_FOR_SESSION = 15 * 60  # seconds: the first chat starts with welcome screens and the trust question


def claude_config_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def unavailable(exe: str) -> str | None:
    """Why this Claude Code can't open the chat in the browser: "account" (no Claude account sign-in, or it
    can't tell), "old" (no Remote Control in this version), or None when it can. Reads only the kind of sign-in
    from `claude auth status`, never names or tokens."""
    if any(os.environ.get(k) for k in NOT_ACCOUNT_ENV):
        return "account"
    try:
        r = subprocess.run([exe, "auth", "status"], capture_output=True, text=True, timeout=60)
        info = json.loads(r.stdout) if r.returncode == 0 else {}
    except (OSError, subprocess.SubprocessError, ValueError):
        info = {}
    if not isinstance(info, dict) or info.get("authMethod") != "claude.ai" or \
            info.get("apiProvider", "firstParty") != "firstParty":
        return "account"
    try:
        r = subprocess.run([exe, "--help"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return "old"
    return None if "--remote-control" in (r.stdout or "") + (r.stderr or "") else "old"


def session_url(pid: int, since: float, config: Path | None = None) -> str | None:
    """The browser link of the Remote Control chat that Claude Code process pid started (after since)."""
    try:
        data = json.loads(((config or claude_config_dir()) / "sessions" / f"{pid}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("pid") != pid:
        return None
    started = data.get("startedAt")
    if isinstance(started, (int, float)) and started < (since - 60) * 1000:
        return None  # left over from an earlier program with the same process ID
    sid = data.get("bridgeSessionId")
    if isinstance(sid, str) and SESSION_ID.fullmatch(sid):
        return f"{CODE_URL}/{sid}"
    return None


def alive(pid: int) -> bool:
    if os.name == "nt":
        return True  # os.kill would end the process on Windows; the helper passes still_running there
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def watch(pid: int, folder: Path, plot_dirs: list[Path], since: float, still_running=None,
          open_link=None, interval: float = 1.0, wait: float = WAIT_FOR_SESSION,
          clock=time.monotonic, sleep=time.sleep) -> str | None:
    """Open the chat in the browser once Claude Code has it, and copy JASP's plots into the folder, until the
    chat ends. Returns the link it opened, if any."""
    still_running = still_running or (lambda: alive(pid))
    open_link = open_link or apps.open_link
    copier = plots.Copier(plot_dirs, folder)
    copier.clear_earlier()
    opened = None
    end_wait = clock() + wait
    while still_running():
        if opened is None and clock() < end_wait:
            url = session_url(pid, since)
            if url:
                open_link(url)
                opened = url
        copier.sync()
        sleep(interval)
    copier.sync()
    return opened


QUICK_EXIT = 15  # seconds: a chat that ends with an error this soon was refused, not used
CTRL_C_EXITS = (130, 0xC000013A)  # quitting with Ctrl+C (POSIX shells, Windows)


def refused(code: int, seconds: float, opened: str | None) -> bool:
    """Did Claude Code refuse Remote Control? An admin can switch it off for a Team, Enterprise or Education
    plan; then `claude --remote-control` stops with an error before the student could have chatted. A chat
    that ended normally (0), with Ctrl+C or by a signal, that ran longer, or that opened in the browser was
    not refused."""
    return code > 0 and code not in CTRL_C_EXITS and seconds < QUICK_EXIT and not opened


class Helper(threading.Thread):
    """The helper as a thread of Full Fat, which waits for Claude Code to finish."""

    def __init__(self, proc: subprocess.Popen, folder: Path, plot_dirs: list[Path]):
        super().__init__(daemon=True)
        self.proc, self.folder, self.plot_dirs = proc, folder, plot_dirs
        self.since = time.time()
        self.stop = threading.Event()
        self.opened: str | None = None

    def run(self) -> None:
        try:
            self.opened = watch(self.proc.pid, self.folder, self.plot_dirs, self.since,
                                still_running=lambda: self.proc.poll() is None and not self.stop.is_set())
        except Exception:  # noqa: BLE001  # the helper must never fail into the chat
            pass

    def finish(self, timeout: float = 5) -> str | None:
        """Stop the helper (after a last copy of the plots) and return the link it opened, if any."""
        self.stop.set()
        self.join(timeout)
        return self.opened


def start_thread(proc: subprocess.Popen, folder: Path, plot_dirs: list[Path]) -> Helper:
    t = Helper(proc, folder, plot_dirs)
    t.start()
    return t
