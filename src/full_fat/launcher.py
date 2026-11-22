"""The "Talk to JASP" icon on the Desktop.

- macOS: "Talk to JASP.command", a shell script that Terminal opens on double-click. Full Fat writes it
  itself, so it has no quarantine flag (only files that browsers and similar apps download get one) and
  is made executable here, so Gatekeeper doesn't stop it.
- Windows: "Talk to JASP.cmd", opened by Command Prompt.
- Linux: "Talk to JASP.desktop" (Terminal=true) on the Desktop and in the applications menu.
Each one runs `full-fat launch`, which checks JASP before starting the chat.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

NAME = "Talk to JASP"


def full_fat_command() -> list[str]:
    """How to run this Full Fat again from a launcher."""
    exe = shutil.which("full-fat")
    if exe:
        return [str(Path(exe).absolute())]
    name = "full-fat.exe" if os.name == "nt" else "full-fat"
    bin_dir = os.environ.get("UV_TOOL_BIN_DIR") or os.environ.get("XDG_BIN_HOME")
    for c in ([Path(bin_dir) / name] if bin_dir else []) + [Path.home() / ".local" / "bin" / name,
                                                         Path(sys.executable).parent / name]:
        if c.is_file():
            return [str(c)]
    return [sys.executable, "-m", "full_fat"]


def desktop_dir() -> Path:
    home = Path.home()
    if sys.platform.startswith("win"):
        try:
            import winreg  # noqa: PLC0415
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
                v = winreg.QueryValueEx(k, "Desktop")[0]
            p = Path(os.path.expandvars(v))
            if p.is_dir():
                return p  # also right when OneDrive moved the Desktop
        except OSError:
            pass
        return home / "Desktop"
    if sys.platform != "darwin":
        try:
            r = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and r.stdout.strip() and Path(r.stdout.strip()) != home:
                return Path(r.stdout.strip())
        except (OSError, subprocess.SubprocessError):
            pass
    return home / "Desktop"


def _sh_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def mac_script(cmd: list[str], folder: Path) -> str:
    args = " ".join(_sh_quote(c) for c in cmd + ["launch", "--dir", str(folder)])
    return ("#!/bin/sh\n"
            "# Talk to JASP (made by Full Fat). Double-click to start a chat about what is open in JASP.\n"
            f"exec {args}\n")


def windows_script(cmd: list[str], folder: Path) -> str:
    args = " ".join(f'"{c}"' for c in cmd + ["launch", "--dir", str(folder)])
    return ("@echo off\r\n"
            "rem Talk to JASP (made by Full Fat). Double-click to start a chat about what is open in JASP.\r\n"
            "chcp 65001 >nul\r\n"
            "title Talk to JASP\r\n"
            f"{args}\r\n"
            "if errorlevel 1 pause\r\n")


def _desktop_quote(s: str) -> str:
    if any(c in s for c in ' \t"\'\\$`'):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`") + '"'
    return s


def linux_entry(cmd: list[str], folder: Path) -> str:
    exec_line = " ".join(_desktop_quote(c) for c in cmd + ["launch", "--dir", str(folder)])
    return ("[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={NAME}\n"
            "Comment=Chat about what is open in JASP (Full Fat)\n"
            f"Exec={exec_line}\n"
            f"Path={folder}\n"
            "Terminal=true\n"
            "Icon=utilities-terminal\n"
            "Categories=Education;Science;\n")


def create(folder: Path, desktop: Path | None = None) -> list[Path]:
    """Write the launcher(s). Returns the files written."""
    desktop = desktop or desktop_dir()
    cmd = full_fat_command()
    made: list[Path] = []
    if sys.platform.startswith("win"):
        p = desktop / f"{NAME}.cmd"
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(windows_script(cmd, folder))
        made.append(p)
    elif sys.platform == "darwin":
        p = desktop / f"{NAME}.command"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(mac_script(cmd, folder), encoding="utf-8")
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        made.append(p)
    else:
        text = linux_entry(cmd, folder)
        apps = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "applications"
        for p in (desktop / f"{NAME}.desktop", apps / "talk-to-jasp.desktop"):
            if p.parent == desktop and not desktop.is_dir():
                continue
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
            p.chmod(p.stat().st_mode | stat.S_IXUSR)
            try:  # GNOME asks before running untrusted desktop files
                subprocess.run(["gio", "set", str(p), "metadata::trusted", "true"],
                               capture_output=True, timeout=5)
            except (OSError, subprocess.SubprocessError):
                pass
            made.append(p)
    return made
