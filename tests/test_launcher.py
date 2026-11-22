import os
import stat
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

from full_fat import launcher


def test_mac_script_quotes():
    s = launcher.mac_script(["/Users/o'neil/.local/bin/full-fat"], PurePosixPath("/Users/o'neil/Full Fat"))
    assert s.startswith("#!/bin/sh\n")
    assert "exec '/Users/o'\\''neil/.local/bin/full-fat' 'launch' '--dir' '/Users/o'\\''neil/Full Fat'" in s


def test_windows_script():
    s = launcher.windows_script([r"C:\Users\me\.local\bin\full-fat.exe"], PureWindowsPath(r"C:\Users\me\Full Fat"))
    assert "\r\n" in s and s.startswith("@echo off")
    assert r'"C:\Users\me\.local\bin\full-fat.exe" "launch" "--dir" "C:\Users\me\Full Fat"' in s


def test_linux_entry():
    s = launcher.linux_entry(["/home/u/.local/bin/full-fat"], PurePosixPath("/home/u/Full Fat"))
    assert "Terminal=true" in s and 'Exec=/home/u/.local/bin/full-fat launch --dir "/home/u/Full Fat"' in s


def test_create_here(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    desk = tmp_path / "Desktop"
    desk.mkdir()
    made = launcher.create(tmp_path / "Full Fat", desktop=desk)
    assert made and made[0].parent == desk and "Full Fat" in made[0].name
    if os.name != "nt":
        assert made[0].stat().st_mode & stat.S_IXUSR


def test_shell_command_for_pasting():
    import os
    from full_fat import launcher
    if os.name == "nt":
        assert launcher.shell_command(["C:/Users/a b/full-fat.exe", "launch"]) == "& 'C:/Users/a b/full-fat.exe' 'launch'"
    else:
        assert launcher.shell_command(["/Users/a b/.local/bin/full-fat", "launch"]) == \
            "'/Users/a b/.local/bin/full-fat' launch"
