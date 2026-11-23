"""The "Full Fat" icon on the Desktop.

- macOS: "Full Fat.command", a shell script that Terminal opens on double-click. Full Fat writes it
  itself, so it has no quarantine flag (only files that browsers and similar apps download get one) and
  is made executable here, so Gatekeeper doesn't stop it. Its Finder icon is set to the carton with
  NSWorkspace's setIcon (through osascript, no extra programs); if that fails it keeps Terminal's icon.
- Windows: "Full Fat.lnk", a shortcut with the carton icon (full-fat.ico in Full Fat's own folder), made with
  PowerShell's WScript.Shell, that opens "Full Fat.cmd" in Full Fat's own folder with Command Prompt. A .cmd
  can't have its own icon. If the shortcut can't be made, "Full Fat.cmd" goes on the Desktop as before.
- Linux: "Full Fat.desktop" (Terminal=true) on the Desktop, full-fat.desktop in the applications menu, with
  Icon= the carton installed in ~/.local/share/icons/hicolor/<size>/apps/full-fat.png.
Each one runs `full-fat launch`, which checks JASP before starting the chat.

The icon files come with Full Fat (src/full_fat/icons, built by assets/icon/build.py). Everything create()
writes is recorded in Full Fat's state, and remove() deletes a file only while it still holds Full Fat's mark
(a launcher) or is byte for byte one of Full Fat's icons.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from importlib import resources
from pathlib import Path

from . import state

NAME = "Full Fat"
MARKS = ("(made by Full Fat)", "(Full Fat)")  # one is in every launcher Full Fat writes
ICON_SIZES = [16, 32, 48, 64, 128, 256, 512]
LINUX_ICON = "utilities-terminal"  # when the carton can't be installed
ICON_SUFFIXES = (".png", ".ico")


def icon_bytes(name: str) -> bytes:
    return resources.files("full_fat").joinpath("icons", name).read_bytes()


def icon_names() -> list[str]:
    return [f"full-fat-{s}.png" for s in ICON_SIZES] + ["full-fat.ico", "full-fat.icns"]


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


def shell_command(cmd: list[str]) -> str:
    """A command to paste into this computer's terminal (PowerShell on Windows, the usual shell elsewhere)."""
    if os.name == "nt":
        return "& " + " ".join("'" + c.replace("'", "''") + "'" for c in cmd)
    return " ".join(c if c and all(ch.isalnum() or ch in "/._-=" for ch in c) else _sh_quote(c) for c in cmd)


def mac_script(cmd: list[str], folder: Path) -> str:
    args = " ".join(_sh_quote(c) for c in cmd + ["launch", "--dir", str(folder)])
    return ("#!/bin/sh\n"
            "# Launcher (made by Full Fat). Double-click to start a chat about what is open in JASP.\n"
            f"exec {args}\n")


def windows_script(cmd: list[str], folder: Path) -> str:
    args = " ".join(f'"{c}"' for c in cmd + ["launch", "--dir", str(folder)])
    return ("@echo off\r\n"
            "rem Launcher (made by Full Fat). Double-click to start a chat about what is open in JASP.\r\n"
            "chcp 65001 >nul\r\n"
            f"title {NAME}\r\n"
            f"{args}\r\n"
            "if errorlevel 1 pause\r\n")


def _desktop_quote(s: str) -> str:
    if any(c in s for c in ' \t"\'\\$`'):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`") + '"'
    return s


def linux_entry(cmd: list[str], folder: Path, icon: str = LINUX_ICON) -> str:
    exec_line = " ".join(_desktop_quote(c) for c in cmd + ["launch", "--dir", str(folder)])
    return ("[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={NAME}\n"
            "Comment=Chat about what is open in JASP (Full Fat)\n"
            f"Exec={exec_line}\n"
            f"Path={folder}\n"
            "Terminal=true\n"
            f"Icon={icon}\n"
            "Categories=Education;Science;\n")


def is_ours(path: Path) -> bool:
    """Does the file still hold Full Fat's mark (a launcher), or is it one of Full Fat's icons, unchanged?"""
    if path.suffix.lower() in ICON_SUFFIXES:
        data = path.read_bytes()
        return any(data == icon_bytes(n) for n in icon_names())
    data = path.read_bytes()
    texts = [data.decode("utf-8", errors="replace")]
    if path.suffix.lower() == ".lnk":  # a shortcut keeps its description in UTF-16
        texts.append(data.decode("utf-16-le", errors="replace"))
        texts.append(data[1:].decode("utf-16-le", errors="replace"))
    return any(m in t for t in texts for m in MARKS)


def remove(path: Path) -> bool:
    """Delete a launcher or icon file. Only for paths recorded in Full Fat's state, and not if the contents were
    replaced."""
    if not path.is_file() or not is_ours(path):
        return False
    path.unlink()
    return True


def is_icon_file(path: str | Path) -> bool:
    """An icon picture Full Fat installed, as opposed to a launcher the user double-clicks."""
    return Path(path).suffix.lower() in ICON_SUFFIXES


def _write_icon(name: str, dest: Path) -> Path:
    data = icon_bytes(name)
    if dest.exists() and not dest.is_symlink() and dest.read_bytes() == data:
        return dest
    if dest.exists() and (dest.is_symlink() or not is_ours(dest)):
        raise OSError(f"{dest} is not Full Fat's")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".full-fat-tmp")
    tmp.write_bytes(data)
    os.replace(tmp, dest)
    return dest


def linux_icons(data_home: Path) -> list[Path]:
    """Put the carton into the user's icon theme folder, every size. Returns the files."""
    return [_write_icon(f"full-fat-{s}.png", data_home / "icons" / "hicolor" / f"{s}x{s}" / "apps" / "full-fat.png")
            for s in ICON_SIZES]


def mac_icon_script() -> str:
    """JavaScript for osascript: set a file's Finder icon to an image (argv: image, file). Prints true or false."""
    return ('function run(argv) { ObjC.import("AppKit"); '
            'var img = $.NSImage.alloc.initWithContentsOfFile(argv[0]); '
            'if (img.isNil()) return "false"; '
            'return $.NSWorkspace.sharedWorkspace.setIconForFileOptions(img, argv[1], 0) ? "true" : "false"; }')


def set_mac_icon(path: Path) -> bool:
    """Give the .command file the carton icon in Finder. False (and the file as it was) when that fails."""
    try:
        with resources.as_file(resources.files("full_fat").joinpath("icons", "full-fat.icns")) as icns:
            r = subprocess.run(["osascript", "-l", "JavaScript", "-e", mac_icon_script(), str(icns), str(path)],
                               capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and r.stdout.strip() == "true"


SHORTCUT_PS = ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:FULL_FAT_LNK); "
               "$s.TargetPath = $env:FULL_FAT_TARGET; $s.WorkingDirectory = $env:FULL_FAT_DIR; "
               "$s.IconLocation = $env:FULL_FAT_ICON + ',0'; $s.Description = $env:FULL_FAT_DESC; "
               "$s.WindowStyle = 1; $s.Save()")


def shortcut_env(lnk: Path, target: Path, folder: Path, icon: Path) -> dict[str, str]:
    """The paths go to PowerShell as environment variables, so no quoting can break them."""
    return {"FULL_FAT_LNK": str(lnk), "FULL_FAT_TARGET": str(target), "FULL_FAT_DIR": str(folder),
            "FULL_FAT_ICON": str(icon), "FULL_FAT_DESC": "Chat about what is open in JASP (made by Full Fat)"}


def make_shortcut(lnk: Path, target: Path, folder: Path, icon: Path) -> bool:
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                            "-Command", SHORTCUT_PS], env=dict(os.environ, **shortcut_env(lnk, target, folder, icon)),
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and lnk.is_file()


def create(folder: Path, desktop: Path | None = None) -> list[Path]:
    """Write the launcher(s). Returns the files written."""
    desktop = desktop or desktop_dir()
    cmd = full_fat_command()
    made: list[Path] = []
    if sys.platform.startswith("win"):
        made += _create_windows(cmd, folder, desktop)
    elif sys.platform == "darwin":
        p = desktop / f"{NAME}.command"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(mac_script(cmd, folder), encoding="utf-8")
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        set_mac_icon(p)
        made.append(p)
    else:
        data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
        icon = LINUX_ICON
        try:
            icons = linux_icons(data_home)
            icon = str(icons[ICON_SIZES.index(256)])
        except OSError:
            icons = []
        text = linux_entry(cmd, folder, icon)
        apps = data_home / "applications"
        for p in (desktop / f"{NAME}.desktop", apps / "full-fat.desktop"):
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
        made += icons
    return made


def _create_windows(cmd: list[str], folder: Path, desktop: Path) -> list[Path]:
    """The shortcut with the carton on the Desktop and the script in Full Fat's own folder, or, if the shortcut
    can't be made, the script on the Desktop."""
    def write(p: Path) -> Path:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(windows_script(cmd, folder))
        return p
    try:
        icon = _write_icon("full-fat.ico", state.config_dir() / "full-fat.ico")
        script = write(state.config_dir() / f"{NAME}.cmd")
    except OSError:
        return [write(desktop / f"{NAME}.cmd")]
    lnk = desktop / f"{NAME}.lnk"
    desktop.mkdir(parents=True, exist_ok=True)
    if make_shortcut(lnk, script, folder, icon):
        return [lnk, script, icon]
    for p in (script, icon):
        p.unlink()
    return [write(desktop / f"{NAME}.cmd")]
