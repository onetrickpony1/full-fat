import os
import subprocess
import tomllib
from pathlib import Path

import pytest

from full_fat import apps

EXISTING = '''model = "gpt-6.2-astra"

[projects."/home/u/other"]
trust_level = "trusted"
'''


def test_trust_appends_only():
    new = apps.codex_trust_text(EXISTING, "/home/u/Full Fat")
    assert new.startswith(EXISTING)
    data = tomllib.loads(new)
    assert data["projects"]["/home/u/Full Fat"] == {"trust_level": "trusted"}
    assert data["projects"]["/home/u/other"] == {"trust_level": "trusted"}


def test_trust_existing_and_windows_path():
    assert apps.codex_trust_text(EXISTING, "/home/u/other") is None
    win = r"C:\Users\me\Full Fat"
    new = apps.codex_trust_text("", win)
    assert tomllib.loads(new)["projects"][win]["trust_level"] == "trusted"
    assert apps.codex_trust_state(new, win) == "trusted"


def test_trust_states():
    assert apps.codex_trust_state('[projects."/x"]\ntrust_level = "untrusted"\n', "/x") == "untrusted"
    assert apps.codex_trust_state("not = [toml", "/x") == "unreadable"
    assert apps.codex_trust_state("", "/x") is None


def test_trust_file(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    (tmp_path / "config.toml").write_text(EXISTING)
    assert apps.trust_codex_folder(tmp_path / "Full Fat") == "added"
    assert (tmp_path / "config.toml.before-full-fat").read_text() == EXISTING
    assert apps.trust_codex_folder(tmp_path / "Full Fat") == "already"
    (tmp_path / "config.toml").write_text("broken = [")
    assert apps.trust_codex_folder(tmp_path / "Other") == "skipped"
    assert (tmp_path / "config.toml").read_text() == "broken = ["


def test_find_override(tmp_path, monkeypatch):
    exe = tmp_path / "claude"
    exe.write_text("")
    monkeypatch.setenv("FULL_FAT_CLAUDE", str(exe))
    assert apps.find(apps.CLAUDE) == str(exe)
    monkeypatch.setenv("FULL_FAT_CLAUDE", str(tmp_path / "missing"))
    assert apps.find(apps.CLAUDE) is None


def test_untrust_removes_only_ours(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    (tmp_path / "config.toml").write_text(EXISTING)
    folder = str(tmp_path / "Full Fat")
    assert apps.trust_codex_folder(tmp_path / "Full Fat") == "added"
    assert apps.untrust_codex_folder(folder) == "removed"
    assert (tmp_path / "config.toml").read_text() == EXISTING
    assert apps.untrust_codex_folder(folder) == "absent"
    assert apps.untrust_codex_folder("/home/u/other") == "left"  # not ours: written another way


def test_claude_login_uses_subscription():
    assert apps.CLAUDE.login == ("auth", "login", "--claudeai")


def _posix_only():
    import os
    import pytest
    if os.name == "nt":
        pytest.skip("symlinks and file modes are POSIX here")


def test_trust_writes_through_a_symlink_and_keeps_mode_and_crlf(tmp_path, monkeypatch):
    import os
    _posix_only()
    home = tmp_path / "codex"
    home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(home))
    real = tmp_path / "dotfiles" / "config.toml"
    real.parent.mkdir()
    original = b'model = "x"\r\n\r\n[mcp_servers.s]\r\nenv = { TOKEN = "secret" }\r\n'
    real.write_bytes(original)
    os.chmod(real, 0o600)
    (home / "config.toml").symlink_to(real)
    assert apps.trust_codex_folder(tmp_path / "Full Fat") == "added"
    cfg = home / "config.toml"
    assert cfg.is_symlink() and oct(real.stat().st_mode & 0o777) == "0o600"
    data = real.read_bytes()
    assert data.startswith(original) and b"\n" not in data.replace(b"\r\n", b"")
    assert apps.untrust_codex_folder(str(tmp_path / "Full Fat")) == "removed"
    assert cfg.is_symlink() and real.read_bytes() == original
    assert oct(real.stat().st_mode & 0o777) == "0o600"


def test_untrust_never_moves_the_users_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    cfg = tmp_path / "config.toml"
    cfg.write_text(EXISTING)
    folder = str(tmp_path / "Full Fat")
    apps.trust_codex_folder(tmp_path / "Full Fat")
    cfg.write_text(cfg.read_text() + 'approval_policy = "never"\n')  # the user added a key under our block
    before = cfg.read_text()
    assert apps.untrust_codex_folder(folder) == "left"
    assert cfg.read_text() == before
    cfg.write_text(before.replace('approval_policy = "never"\n', '\n[profiles.mine]\nmodel = "y"\n'))
    assert apps.untrust_codex_folder(folder) == "removed"
    assert tomllib.loads(cfg.read_text()) == {**tomllib.loads(EXISTING), "profiles": {"mine": {"model": "y"}}}


def test_launch_flags_only_when_no_settings_choose(tmp_path, monkeypatch):
    import json
    folder = tmp_path / "Full Fat"
    (folder / ".claude").mkdir(parents=True)
    (folder / ".claude" / "settings.json").write_text(json.dumps({"permissions": {}}))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude-user"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-user"))
    assert apps.launch_command(apps.CLAUDE, "claude", "Hi", folder) == [
        "claude", "--model", "opus", "--effort", "high", "Hi"]
    (tmp_path / "claude-user").mkdir()
    (tmp_path / "claude-user" / "settings.json").write_text(json.dumps({"model": "haiku"}))  # /model saved it
    assert apps.launch_command(apps.CLAUDE, "claude", "Hi", folder) == ["claude", "--effort", "high", "Hi"]
    (folder / ".claude" / "settings.local.json").write_text(json.dumps({"effortLevel": "low"}))
    assert apps.launch_command(apps.CLAUDE, "claude", "Hi", folder) == ["claude", "Hi"]
    assert apps.launch_command(apps.CODEX, "codex", "Hi", folder) == [
        "codex", "-m", "gpt-6.2-astra", "-c", 'model_reasoning_effort="high"', "Hi"]
    (tmp_path / "codex-user").mkdir()
    (tmp_path / "codex-user" / "config.toml").write_text('model = "gpt-5"\nmodel_reasoning_effort = "low"\n')
    assert apps.launch_command(apps.CODEX, "codex", "Hi", folder) == ["codex", "Hi"]


def test_connector_failures_are_explained():
    from full_fat import connector
    assert "no ready-made version" in connector.explain(
        "error: Failed to build `cryptography==50.0.2`")
    assert "internet" in connector.explain("error: Failed to fetch: dns error")
    assert "internet" not in connector.explain("Something odd")


# ---------------------------------------------------------------------------- the ChatGPT desktop app

def test_deep_link_encodes_the_folder_and_prompt():
    from urllib.parse import parse_qs, urlsplit
    url = apps.deep_link(Path("/Users/me/Full Fat"), "Give a short introduction.")
    assert url.startswith("codex://threads/new?")
    assert " " not in url and "+" not in url
    assert "path=%2FUsers%2Fme%2FFull%20Fat&" in url and "mode=codex" in url
    q = parse_qs(urlsplit(url).query)
    assert q == {"path": ["/Users/me/Full Fat"], "mode": ["codex"], "prompt": ["Give a short introduction."]}
    win = parse_qs(urlsplit(apps.deep_link(Path(r"C:\Users\Me & You\Full Fat"), "a&b=c")).query)
    assert win["path"] == [str(Path(r"C:\Users\Me & You\Full Fat"))] and win["prompt"] == ["a&b=c"]


def test_desktop_app_found_env(monkeypatch):
    monkeypatch.setenv("FULL_FAT_CHATGPT_APP", "none")
    assert apps.desktop_app_found() is False
    monkeypatch.setenv("FULL_FAT_CHATGPT_APP", "yes")
    assert apps.desktop_app_found() is True


def test_desktop_app_found_linux(monkeypatch):
    monkeypatch.delenv("FULL_FAT_CHATGPT_APP")
    out = {"stdout": "chatgpt.desktop\n", "rc": 0}

    def run(cmd, **kw):
        assert cmd == ["xdg-mime", "query", "default", "x-scheme-handler/codex"]
        return subprocess.CompletedProcess(cmd, out["rc"], out["stdout"], "")
    monkeypatch.setattr(apps.subprocess, "run", run)
    assert apps.desktop_app_found("linux")
    out["stdout"] = ""
    assert not apps.desktop_app_found("linux")


def test_desktop_app_found_mac(tmp_path, monkeypatch):
    import plistlib
    monkeypatch.delenv("FULL_FAT_CHATGPT_APP")
    apps_dir = tmp_path / "Applications"
    monkeypatch.setattr(apps, "MAC_APP_DIRS", (str(apps_dir),))
    monkeypatch.setattr(apps, "_mac_handler", lambda: False)
    assert not apps.desktop_app_found("darwin")
    old = apps_dir / "ChatGPT.app" / "Contents"  # an older ChatGPT app without the Codex side
    old.mkdir(parents=True)
    (old / "Info.plist").write_bytes(plistlib.dumps({"CFBundleURLTypes": [{"CFBundleURLSchemes": ["chatgpt"]}]}))
    assert not apps.desktop_app_found("darwin")
    (old / "Info.plist").write_bytes(plistlib.dumps(
        {"CFBundleURLTypes": [{"CFBundleURLSchemes": ["chatgpt"]}, {"CFBundleURLSchemes": ["codex"]}]}))
    assert apps.desktop_app_found("darwin")
    (old / "Info.plist").write_bytes(b"not a plist")
    assert not apps.desktop_app_found("darwin")
    monkeypatch.setattr(apps, "_mac_handler", lambda: True)  # the app lives somewhere else
    assert apps.desktop_app_found("darwin")


def test_open_desktop_app(monkeypatch):
    seen = []

    class P:
        def __init__(self, cmd, **kw):
            seen.append(cmd)
            self.rc = 0 if "good" in cmd[1] else 1
            assert kw.get("start_new_session")

        def wait(self, timeout=None):
            if "slow" in seen[-1][1]:
                raise subprocess.TimeoutExpired(seen[-1], timeout)
            return self.rc
    monkeypatch.setattr(apps.subprocess, "Popen", P)
    assert apps.open_desktop_app("codex://good", "darwin") and seen[-1] == ["open", "codex://good"]
    assert apps.open_desktop_app("codex://good", "linux") and seen[-1] == ["xdg-open", "codex://good"]
    assert not apps.open_desktop_app("codex://bad", "linux")
    assert apps.open_desktop_app("codex://slow", "linux")

    def boom(cmd, **kw):
        raise FileNotFoundError(cmd[0])
    monkeypatch.setattr(apps.subprocess, "Popen", boom)
    assert not apps.open_desktop_app("codex://good", "linux")


def test_desktop_app_found_windows(monkeypatch):
    import sys
    import types
    monkeypatch.delenv("FULL_FAT_CHATGPT_APP")
    keys = {}

    class Key:
        def __init__(self, name):
            self.name = name

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def open_key(root, name):
        if (root, name) not in keys:
            raise FileNotFoundError(name)
        return Key(name)

    def query(k, value):
        if value != "URL Protocol":
            raise FileNotFoundError(value)
        return ("", 1)
    fake = types.SimpleNamespace(HKEY_CURRENT_USER="HKCU", HKEY_CLASSES_ROOT="HKCR", OpenKey=open_key,
                                 QueryValueEx=query)
    monkeypatch.setitem(sys.modules, "winreg", fake)
    assert not apps.desktop_app_found("win32")
    keys[("HKCR", "codex")] = True
    assert apps.desktop_app_found("win32")
    keys.clear()
    keys[("HKCU", r"Software\Classes\codex")] = True
    assert apps.desktop_app_found("win32")


def test_open_desktop_app_windows(monkeypatch):
    seen = []
    monkeypatch.setattr(apps.os, "startfile", seen.append, raising=False)
    assert apps.open_desktop_app("codex://x", "win32") and seen == ["codex://x"]

    def no_app(url):
        raise OSError("No application is associated")
    monkeypatch.setattr(apps.os, "startfile", no_app, raising=False)
    assert not apps.open_desktop_app("codex://x", "win32")


# ---------------------------------------------------------------------------- an older Codex and the folder's settings

def stand_in_codex(tmp_path, code: int, message: str):
    """A Codex that answers `codex mcp list` with code and message, and records the folder it ran in."""
    if os.name == "nt":
        pytest.skip("a POSIX shell stand-in")
    p = tmp_path / "codex-stand-in"
    p.write_text("#!/bin/sh\n"
                 f'case "$1" in login) exit 0;; mcp) pwd > "{tmp_path}/ran-in"; echo "{message}" >&2; exit {code};; '
                 "esac\n")
    p.chmod(0o755)
    return str(p)


def test_codex_that_loads_the_folder_passes(tmp_path):
    folder = tmp_path / "Full Fat"
    folder.mkdir()
    assert apps.codex_folder_problem(stand_in_codex(tmp_path, 0, "No MCP servers configured"), folder) is None
    assert (tmp_path / "ran-in").read_text().strip() == str(folder)


def test_codex_that_refuses_the_folders_settings_is_a_problem(tmp_path):
    exe = stand_in_codex(tmp_path, 1, "Error loading config.toml: unknown field `apps` in features")
    assert "unknown field" in apps.codex_folder_problem(exe, tmp_path)


@pytest.mark.parametrize("code,message", [(1, "network down"), (2, "")])
def test_other_codex_errors_are_not_blamed_on_the_settings(tmp_path, code, message):
    assert apps.codex_folder_problem(stand_in_codex(tmp_path, code, message), tmp_path) is None


def test_no_codex_is_no_problem(tmp_path):
    assert apps.codex_folder_problem(str(tmp_path / "missing"), tmp_path) is None
