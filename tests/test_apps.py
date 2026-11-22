import tomllib

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
