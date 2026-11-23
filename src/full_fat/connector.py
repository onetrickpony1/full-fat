"""Start JASP's connector (jasp-mcp) once, exactly as the chat apps will, so its first start (uvx downloads
about 30 packages) happens during setup and not while the chat app waits for it."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import workspace

INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "full-fat", "version": "1"}}}


def archive_gone(url: str, timeout: float = 30) -> bool:
    """Does GitHub say this connector archive does not exist (404 or 410)? Any other failure (offline, a
    slow network, GitHub down) is not "gone": the connector start reports that with its own message."""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "full-fat"})
    try:
        with urllib.request.urlopen(req, timeout=timeout):
            return False
    except urllib.error.HTTPError as e:
        return e.code in (404, 410)
    except (OSError, ValueError):
        return False


def folder_archive_gone(server: dict) -> bool:
    """Is the connector archive a chat folder's settings name (`jasp-mcp @ <url>`) gone from GitHub?"""
    for a in server.get("args") or []:
        if isinstance(a, str) and a.startswith("jasp-mcp @ "):
            return archive_gone(a.removeprefix("jasp-mcp @ ").strip())
    return False


def pick_url(gone=None) -> str:
    """The connector archive setup writes into the chat folder: the pinned commit, or main's commit when the
    pinned one can no longer be downloaded (see workspace.JASP_MCP_FALLBACK_SHA)."""
    gone = gone or archive_gone
    if gone(workspace.JASP_MCP_URL) and not gone(workspace.JASP_MCP_FALLBACK_URL):
        return workspace.JASP_MCP_FALLBACK_URL
    return workspace.JASP_MCP_URL


def explain(detail: str) -> str:
    """What to tell the user about a failed start, from the connector's last line."""
    d = (detail or "").lower()
    where = f" (Details: {detail})" if detail else ""
    if any(w in d for w in ("build", "compile", "rustc", "cargo", "wheel", "no solution found")):
        return ("A part it needs could not be installed on this computer: there is no ready-made version of it "
                "for this kind of computer." + where + " Please report this, with the details, at "
                "https://github.com/onetrickpony1/full-fat/issues")
    if any(w in d for w in ("dns", "network", "connect", "timed out", "timeout", "resolve", "tls", "certificate",
                            "unreachable", "offline", "no answer in time")):
        return "It could not download what it needs. Check the internet connection, then run Full Fat again." + where
    if "no such file" in d or "not found" in d or "winerror 2" in d:
        return "uv, which starts it, is missing. Run the Full Fat install line again." + where
    return "Run Full Fat again. If it fails again, please report it with the details." + where


def warm(server: dict, cwd: Path, timeout: float = 300) -> tuple[bool, str]:
    """Run the server command, send MCP initialize, wait for the answer, stop it.

    Returns (ok, detail). detail is the last line the connector printed when it failed.
    """
    env = dict(os.environ, **server.get("env", {}))
    kw = {"creationflags": 0x08000000} if os.name == "nt" else {}  # CREATE_NO_WINDOW
    try:
        p = subprocess.Popen([server["command"], *server["args"]], cwd=cwd, env=env, text=True,
                             encoding="utf-8", errors="replace", stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kw)
    except OSError as e:
        return False, str(e)
    lines: queue.Queue = queue.Queue()
    err: list[str] = []

    def read_out():
        for line in p.stdout:
            lines.put(line)

    def read_err():
        for line in p.stderr:
            err.append(line.rstrip())
            del err[:-20]

    threading.Thread(target=read_out, daemon=True).start()
    threading.Thread(target=read_err, daemon=True).start()
    try:
        p.stdin.write(json.dumps(INIT) + "\n")
        p.stdin.flush()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                line = lines.get(timeout=1)
            except queue.Empty:
                if p.poll() is not None:
                    return False, (err[-1] if err else f"stopped with code {p.returncode}")
                continue
            try:
                data = json.loads(line)
            except ValueError:
                continue
            if data.get("id") == 1:
                return ("result" in data), ("" if "result" in data else str(data.get("error")))
        return False, "no answer in time"
    except OSError as e:
        return False, str(e)
    finally:
        try:
            p.stdin.close()
        except OSError:
            pass
        p.terminate()
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
