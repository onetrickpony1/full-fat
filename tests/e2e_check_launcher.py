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
        p.write_text('@echo off\nif "%~1"=="auth" exit /b 0\nif "%~1"=="login" exit /b 0\n'
                     f'>"{marker}" echo %CD%\n>>"{marker}" echo %~1\nexit /b 0\n')
    else:
        p = folder / "fake chat"
        p.write_text('#!/bin/sh\ncase "$1" in auth|login) exit 0;; esac\n'
                     f'{{ pwd; printf "%s\\n" "$@"; }} > {shlex.quote(str(marker))}\n')
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
    if len(lines) != 2:
        raise SystemExit(f"{how}: the chat app was not started as expected (got {lines})")
    if not os.path.samefile(lines[0], folder) or lines[1] != INTRO:
        raise SystemExit(f"{how}: wrong folder or message: {lines}")
    print(f"OK ({how}): started in [{lines[0]}] with [{lines[1]}]", flush=True)
    marker.unlink()


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
            # Terminal doesn't pass our environment on, so the stand-in goes where Full Fat looks for Claude Code
            planted = Path.home() / ".local" / "bin" / "claude"
            if planted.exists():
                raise SystemExit(f"{planted} exists: not replacing a real Claude Code")
            planted.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(fake, planted)
            subprocess.run(["open", str(a.launcher.absolute())], timeout=60, check=True)
        try:
            check(marker, a.folder, "double-click", wait=120)
        finally:
            if planted:
                planted.unlink()

    if server:
        server.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
