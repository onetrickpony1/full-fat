"""End-to-end check of the Full Fat icon (used by CI): does it start the chat app inside the chat folder?

A stand-in chat app writes down the folder it was started in and what it was given. The real launcher then
runs the real `full-fat launch`, so every layer of quoting is exercised with the space in "Full Fat".

Usage: python tests/e2e_check_launcher.py LAUNCHER FOLDER [--fake-jasp] [--double-click]
--fake-jasp     answer JASP's ping on 127.0.0.1:48164 (where no JASP is installed)
--double-click  also start it as a double-click does (macOS open, Windows ShellExecute, Linux gio launch).
                Needs a single chat app set up on macOS and Windows, because nobody can answer "which one?".
"""

from __future__ import annotations

import argparse
import http.server
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

INTRO = "Give a short introduction."


class FakeJasp(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        body = b'{"jsonrpc":"2.0","id":1,"result":{"message":"pong"}}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def fake_app(folder: Path, marker: Path) -> Path:
    if os.name == "nt":
        p = folder / "fake chat.cmd"
        p.write_text('@echo off\nif "%~1"=="auth" exit /b 0\nif "%~1"=="login" exit /b 0\nif "%~1"=="mcp" exit /b 0\n'
                     f'>"{marker}.tmp" echo %CD%\n>>"{marker}.tmp" echo %*\nmove /y "{marker}.tmp" "{marker}" >nul\nexit /b 0\n')
    else:
        p = folder / "fake chat"
        p.write_text('#!/bin/sh\ncase "$1" in auth|login|mcp) exit 0;; esac\n'
                     f'{{ pwd; printf "%s\\n" "$@"; }} > {shlex.quote(str(marker) + ".tmp")}\n'
                     f'mv {shlex.quote(str(marker) + ".tmp")} {shlex.quote(str(marker))}\n')
        p.chmod(0o755)
    return p


def check(marker: Path, folder: Path, how: str, wait: float = 5) -> None:
    deadline = time.monotonic() + wait
    lines: list[str] = []
    while time.monotonic() < deadline:
        if marker.is_file():
            lines = [x.strip() for x in marker.read_text(errors="replace").splitlines()]
            if len(lines) >= 2:
                break
        time.sleep(0.5)
    # the folder it started in, then its arguments (the model and effort options, then the greeting)
    if len(lines) < 2:
        raise SystemExit(f"{how}: the chat app was not started as expected (got {lines})")
    if not os.path.samefile(lines[0], folder) or not lines[-1].strip('"').endswith(INTRO):
        raise SystemExit(f"{how}: wrong folder or message: {lines}")
    print(f"OK ({how}): started in [{lines[0]}] with {lines[1:]}", flush=True)
    marker.unlink()


def shortcut_target(lnk: Path) -> str:
    ps = "(New-Object -ComObject WScript.Shell).CreateShortcut($env:LNK).TargetPath"
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], env=dict(os.environ, LNK=str(lnk.absolute())),
                       capture_output=True, text=True, timeout=60, check=True)
    return r.stdout.strip()


def diagnose(planted: Path | None) -> None:
    """Print what the double-clicked window did, for the CI log."""
    print("--- diagnostics", flush=True)
    if planted:
        print(f"planted {planted}: exists={planted.exists()}", flush=True)
        print(planted.read_text(errors="replace") if planted.exists() else "", flush=True)
    for d in (Path.home() / ".local" / "bin", Path(os.environ.get("RUNNER_TEMP", "/nonexistent"))):
        if d.is_dir():
            print(d, sorted(x.name for x in d.iterdir()), flush=True)
    log = Path(os.environ.get("RUNNER_TEMP", "/nonexistent")) / "chat.log"
    if log.is_file():
        print("chat.log:", log.read_text(errors="replace"), flush=True)
    if sys.platform == "darwin":
        subprocess.run(["osascript", "-e", 'tell application "Terminal" to get contents of selected tab of front window'])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("launcher", type=Path)
    ap.add_argument("folder", type=Path)
    ap.add_argument("--fake-jasp", action="store_true")
    ap.add_argument("--double-click", action="store_true")
    a = ap.parse_args()

    server = None
    if a.fake_jasp:
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 48164), FakeJasp)
        threading.Thread(target=server.serve_forever, daemon=True).start()

    tmp = Path(tempfile.mkdtemp(prefix="full fat check "))
    marker = tmp / "started.txt"
    fake = fake_app(tmp, marker)
    env = dict(os.environ, FULL_FAT_CLAUDE=str(fake), FULL_FAT_CODEX=str(fake))
    linux = a.launcher.suffix == ".desktop"
    if linux:
        entry = a.launcher.read_text()
        cmd = shlex.split(next(x[5:] for x in entry.splitlines() if x.startswith("Exec=")))
    elif a.launcher.suffix.lower() == ".lnk":  # Windows shortcut: run what it points at
        cmd = [shortcut_target(a.launcher)]
        print(f"shortcut points at [{cmd[0]}]", flush=True)
    else:
        cmd = [str(a.launcher.absolute())]
    subprocess.run(cmd, cwd=tmp, env=env, stdin=subprocess.DEVNULL, timeout=120, check=True)
    check(marker, a.folder, "run")

    if a.double_click:
        planted = None
        if linux:
            copy = tmp / a.launcher.name
            copy.write_text(entry.replace("Terminal=true", "Terminal=false"))  # CI has no terminal window
            copy.chmod(0o755)
            subprocess.run(["gio", "launch", str(copy)], env=env, stdin=subprocess.DEVNULL, timeout=60, check=True)
        elif os.name == "nt":
            os.environ.update(env)
            os.startfile(a.launcher.absolute())
        elif sys.platform == "darwin":
            planted = Path.home() / ".local" / "bin" / "claude"
            if planted.exists():
                raise SystemExit(f"{planted} exists: not replacing a real Claude Code")
            planted.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(fake, planted)
            # Terminal, started by `open`, inherits this environment (CI's own stand-in apps included), so it
            # gets the one this check watches. The planted copy covers a Terminal that was already running.
            subprocess.run(["open", str(a.launcher.absolute())], env=env, timeout=60, check=True)
        try:
            check(marker, a.folder, "double-click", wait=120)
        except SystemExit:
            diagnose(planted)
            raise
        finally:
            if planted:
                planted.unlink()

    if server:
        server.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
