import os
import stat
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

from full_fat import launcher


def test_mac_script_quotes():
    s = launcher.mac_script(["/Users/o'neil/.local/bin/full-fat"], PurePosixPath("/Users/o'neil/JASP AI"))
    assert s.startswith("#!/bin/sh\n")
    assert "exec '/Users/o'\\''neil/.local/bin/full-fat' 'launch' '--dir' '/Users/o'\\''neil/JASP AI'" in s


def test_windows_script():
    s = launcher.windows_script([r"C:\Users\me\.local\bin\full-fat.exe"], PureWindowsPath(r"C:\Users\me\JASP-AI"))
    assert "\r\n" in s and s.startswith("@echo off")
    assert r'"C:\Users\me\.local\bin\full-fat.exe" "launch" "--dir" "C:\Users\me\JASP-AI"' in s


def test_linux_entry():
    s = launcher.linux_entry(["/home/u/.local/bin/full-fat"], PurePosixPath("/home/u/JASP AI"))
    assert "Terminal=true" in s and 'Exec=/home/u/.local/bin/full-fat launch --dir "/home/u/JASP AI"' in s


def test_create_here(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    desk = tmp_path / "Desktop"
    desk.mkdir()
    made = launcher.create(tmp_path / "JASP-AI", desktop=desk)
    assert made and made[0].parent == desk and "Talk to JASP" in made[0].name
    if os.name != "nt":
        assert made[0].stat().st_mode & stat.S_IXUSR
