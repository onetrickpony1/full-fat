"""Start JASP's connector (jasp-mcp) once, exactly as the chat apps will, so its first start (uvx downloads
about 30 packages) happens during setup and not while the chat app waits for it."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from pathlib import Path

INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "full-fat", "version": "1"}}}


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
