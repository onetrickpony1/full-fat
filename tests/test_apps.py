import tomllib

from full_fat import apps

EXISTING = '''model = "gpt-6.2-astra"

[projects."/home/u/other"]
trust_level = "trusted"
'''


def test_trust_appends_only():
    new = apps.codex_trust_text(EXISTING, "/home/u/JASP-AI")
    assert new.startswith(EXISTING)
    data = tomllib.loads(new)
    assert data["projects"]["/home/u/JASP-AI"] == {"trust_level": "trusted"}
    assert data["projects"]["/home/u/other"] == {"trust_level": "trusted"}


def test_trust_existing_and_windows_path():
    assert apps.codex_trust_text(EXISTING, "/home/u/other") is None
    win = r"C:\Users\me\JASP-AI"
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
    assert apps.trust_codex_folder(tmp_path / "JASP-AI") == "added"
    assert (tmp_path / "config.toml.before-full-fat").read_text() == EXISTING
    assert apps.trust_codex_folder(tmp_path / "JASP-AI") == "already"
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
