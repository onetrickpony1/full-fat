import os
import stat
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

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


# ---------------------------------------------------------------------------- the carton icon

def test_icon_files_come_with_full_fat():
    for name in launcher.icon_names():
        data = launcher.icon_bytes(name)
        assert data[:4] in (b"\x89PNG", b"\x00\x00\x01\x00", b"icns"), name
    assert launcher.icon_bytes("full-fat-256.png")[16:24] == (256).to_bytes(4, "big") * 2


@pytest.mark.skipif(sys.platform in ("win32", "darwin"), reason="the Linux launcher")
def test_linux_launchers_show_the_carton(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    desk = tmp_path / "Desktop"
    desk.mkdir()
    made = launcher.create(tmp_path / "Full Fat", desktop=desk)
    png = tmp_path / "share" / "icons" / "hicolor" / "256x256" / "apps" / "full-fat.png"
    assert png.read_bytes() == launcher.icon_bytes("full-fat-256.png")
    for entry in (desk / "Full Fat.desktop", tmp_path / "share" / "applications" / "full-fat.desktop"):
        assert f"\nIcon={png}\n" in entry.read_text()
    assert png in made and len([m for m in made if launcher.is_icon_file(m)]) == len(launcher.ICON_SIZES)
    for m in made:  # what uninstall does with the recorded files
        assert launcher.remove(m)
    assert not png.exists()


@pytest.mark.skipif(sys.platform in ("win32", "darwin"), reason="the Linux launcher")
def test_linux_launcher_falls_back_to_the_terminal_icon(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    theirs = tmp_path / "share" / "icons" / "hicolor" / "16x16" / "apps" / "full-fat.png"
    theirs.parent.mkdir(parents=True)
    theirs.write_bytes(b"someone else's full-fat icon")
    made = launcher.create(tmp_path / "Full Fat", desktop=tmp_path)
    assert theirs.read_bytes() == b"someone else's full-fat icon"  # never replaced
    assert "\nIcon=utilities-terminal\n" in made[0].read_text()


def test_remove_keeps_changed_icons(tmp_path):
    p = tmp_path / "full-fat.png"
    p.write_bytes(launcher.icon_bytes("full-fat-32.png") + b"edited")
    assert not launcher.remove(p) and p.exists()
    p.write_bytes(launcher.icon_bytes("full-fat-32.png"))
    assert launcher.remove(p) and not p.exists()


def test_a_shortcut_is_recognised_by_its_description(tmp_path):
    lnk = tmp_path / "Full Fat.lnk"
    desc = launcher.shortcut_env(lnk, tmp_path, tmp_path, tmp_path)["FULL_FAT_DESC"]
    for pad in (b"L\x00\x00\x00", b"L\x00\x00"):  # the text can start at an odd byte
        lnk.write_bytes(pad + desc.encode("utf-16-le") + b"\x00\x00")
        assert launcher.is_ours(lnk)
    lnk.write_bytes(b"L\x00\x00\x00" + "Some other shortcut".encode("utf-16-le"))
    assert not launcher.remove(lnk) and lnk.exists()


def test_windows_shortcut_with_the_script_in_full_fats_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("FULL_FAT_CONFIG", str(tmp_path / "cfg"))
    calls = []

    def shortcut(lnk, target, folder, icon):
        calls.append((lnk, target, folder, icon))
        lnk.write_bytes(launcher.shortcut_env(lnk, target, folder, icon)["FULL_FAT_DESC"].encode("utf-16-le"))
        return True
    monkeypatch.setattr(launcher, "make_shortcut", shortcut)
    desk = tmp_path / "Desktop"
    made = launcher._create_windows(["full-fat.exe"], tmp_path / "Full Fat", desk)
    lnk, script, ico = made
    assert lnk == desk / "Full Fat.lnk" and script == tmp_path / "cfg" / "Full Fat.cmd"
    assert ico.read_bytes() == launcher.icon_bytes("full-fat.ico")
    assert calls == [(lnk, script, tmp_path / "Full Fat", ico)]
    assert all(launcher.remove(m) for m in made)


def test_windows_falls_back_to_the_script_on_the_desktop(tmp_path, monkeypatch):
    monkeypatch.setenv("FULL_FAT_CONFIG", str(tmp_path / "cfg"))
    monkeypatch.setattr(launcher, "make_shortcut", lambda *a: False)
    made = launcher._create_windows(["full-fat.exe"], tmp_path / "Full Fat", tmp_path / "Desktop")
    assert made == [tmp_path / "Desktop" / "Full Fat.cmd"]
    assert sorted(p.name for p in (tmp_path / "cfg").iterdir()) == []  # nothing left behind


def test_shortcut_paths_go_through_the_environment():
    assert "$env:FULL_FAT_TARGET" in launcher.SHORTCUT_PS and "'" + "C:" not in launcher.SHORTCUT_PS
    env = launcher.shortcut_env(PureWindowsPath(r"C:\Users\o'neil\OneDrive\Desktop\Full Fat.lnk"),
                                PureWindowsPath(r"C:\x\Full Fat.cmd"), PureWindowsPath(r"C:\Users\o'neil\Full Fat"),
                                PureWindowsPath(r"C:\x\full-fat.ico"))
    assert env["FULL_FAT_LNK"].endswith(r"Desktop\Full Fat.lnk") and "(made by Full Fat)" in env["FULL_FAT_DESC"]


def test_mac_icon_is_set_with_osascript(tmp_path, monkeypatch):
    seen = {}

    class R:
        returncode, stdout = 0, "true\n"

    def run(cmd, **kw):
        seen["cmd"] = cmd
        return R()
    monkeypatch.setattr(launcher.subprocess, "run", run)
    f = tmp_path / "Full Fat.command"
    assert launcher.set_mac_icon(f)
    cmd = seen["cmd"]
    assert cmd[:4] == ["osascript", "-l", "JavaScript", "-e"] and "setIconForFileOptions" in cmd[4]
    assert cmd[5].endswith("full-fat.icns") and cmd[6] == str(f)
    R.stdout = "false\n"
    assert not launcher.set_mac_icon(f)
    monkeypatch.setattr(launcher.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(OSError("no osascript")))
    assert not launcher.set_mac_icon(f)


@pytest.mark.skipif(sys.platform != "darwin", reason="needs macOS")
@pytest.mark.xfail(strict=False, reason="not yet seen on a real Mac; if it fails, the file keeps Terminal's icon")
def test_mac_icon_really_sets(tmp_path):
    f = tmp_path / "Full Fat.command"
    f.write_text("#!/bin/sh\n")
    assert launcher.set_mac_icon(f)
