import json
from pathlib import Path

import pytest

from conftest import make_fetcher
from full_fat import cli, jasp, prompts, state
from full_fat.ui import UI

REAL = "[General]\naiEnabled=true\nshowRSyntax=false\n"


@pytest.fixture
def env(tmp_path, monkeypatch, fake_github):
    monkeypatch.setattr(prompts, "fetch", make_fetcher(fake_github))
    conf = tmp_path / "jasp" / "JASP.conf"
    conf.parent.mkdir()
    conf.write_text(REAL)
    monkeypatch.setattr(jasp, "running", lambda: False)
    monkeypatch.setattr(cli.jasp, "running", lambda: False)
    return tmp_path, conf


def setup_args(tmp_path, conf, *extra):
    return ["setup", "--yes", "--dir", str(tmp_path / "ws"), "--settings-file", str(conf), "--jasp-version",
            "0.98.1", "--app", "claude", "--no-install-apps", "--no-sign-in", "--no-launcher", *extra]


def test_setup_switches_on_when_closed(env, capsys):
    tmp_path, conf = env
    assert cli.main(setup_args(tmp_path, conf)) == 0
    assert "rpcServerEnabled=true" in conf.read_text()
    assert (tmp_path / "ws" / "AGENTS.md").is_file()
    st = state.load()
    assert st["dir"] == str(tmp_path / "ws") and st["apps"] == ["claude"]
    assert st["jasp_changes"][0]["previous"] is None
    backups = list(state.backup_dir().iterdir())
    assert len(backups) == 1 and backups[0].read_text() == REAL
    out = capsys.readouterr().out
    assert "Switched on" in out


def test_setup_leaves_settings_alone_when_open(env, monkeypatch, capsys):
    tmp_path, conf = env
    monkeypatch.setattr(cli.jasp, "running", lambda: True)
    monkeypatch.setattr(jasp, "running", lambda: True)
    assert cli.main(setup_args(tmp_path, conf)) == 0
    assert conf.read_text() == REAL
    assert "JASP is open, so Full Fat did not change its settings" in capsys.readouterr().out
    assert (tmp_path / "ws" / "AGENTS.md").is_file()


def test_setup_waits_for_jasp_to_close(env, monkeypatch):
    tmp_path, conf = env
    calls = {"n": 0}

    def is_running():
        calls["n"] += 1
        return calls["n"] < 3
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)
    monkeypatch.setattr("full_fat.ui.time.sleep", lambda s: None)
    j = jasp.detect(str(conf), "0.98.1")
    assert cli.switch_on(j, UI(yes=False, inp=lambda p: ""), is_running=is_running)
    assert calls["n"] >= 3 and "rpcServerEnabled=true" in conf.read_text()


def test_too_old(env, capsys):
    tmp_path, conf = env
    args = setup_args(tmp_path, conf)
    args[args.index("0.98.1")] = "0.97.1"
    assert cli.main(args) == 1
    assert "needs JASP 0.98.0 or newer" in capsys.readouterr().out
    assert conf.read_text() == REAL


def test_rerun_and_careful_is_remembered(env):
    tmp_path, conf = env
    cli.main(setup_args(tmp_path, conf, "--careful"))
    (tmp_path / "ws" / "mine.txt").write_text("x")
    cli.main(setup_args(tmp_path, conf))
    s = json.loads((tmp_path / "ws" / ".claude" / "settings.json").read_text())
    assert "mcp__jasp" not in s["permissions"]["allow"]  # still careful
    assert (tmp_path / "ws" / "mine.txt").read_text() == "x"
    cli.main(setup_args(tmp_path, conf, "--no-careful"))
    s = json.loads((tmp_path / "ws" / ".claude" / "settings.json").read_text())
    assert "mcp__jasp" in s["permissions"]["allow"]


def test_uninstall_restores(env, monkeypatch):
    tmp_path, conf = env
    cli.main(setup_args(tmp_path, conf))
    (tmp_path / "ws" / "mine.txt").write_text("x")
    assert cli.main(["uninstall", "--yes"]) == 0
    assert conf.read_text() == REAL
    assert (tmp_path / "ws" / "mine.txt").exists()  # had a user file, so the default was to keep it
    assert not state.state_file().exists()


def test_uninstall_restores_previous_false(env):
    tmp_path, conf = env
    conf.write_text("[General]\nrpcServerEnabled=false\n")
    cli.main(setup_args(tmp_path, conf))
    assert "rpcServerEnabled=true" in conf.read_text()
    cli.main(["uninstall", "--yes"])
    assert conf.read_text() == "[General]\nrpcServerEnabled=false\n"
    assert not (tmp_path / "ws").exists()


def test_wait_for_jasp_opens_and_fixes(env, monkeypatch):
    tmp_path, conf = env
    monkeypatch.setattr("full_fat.ui.time.sleep", lambda s: None)
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)
    j = jasp.detect(str(conf), "0.98.1")
    world = {"running": True, "asked": 0}

    def ping(h, p):
        return j.enabled() and world["running"]

    def is_running():
        # the user closes JASP a moment after being asked; Full Fat then opens it again
        if not j.enabled():
            world["asked"] += 1
            if world["asked"] > 2:
                world["running"] = False
        return world["running"]

    def opened(_j):
        world["running"] = True
        return True
    monkeypatch.setattr(jasp, "open_jasp", opened)
    ui = UI(yes=False, inp=lambda prompt: "")
    assert cli.wait_for_jasp(j, "127.0.0.1", 48164, ui, is_running=is_running, ping=ping, start_wait=5)
    assert j.enabled()


def test_wait_for_jasp_non_interactive_gives_up(env, monkeypatch):
    tmp_path, conf = env
    j = jasp.detect(str(conf), "0.98.1")
    j.open_cmd = None
    assert not cli.wait_for_jasp(j, "127.0.0.1", 1, UI(yes=True), is_running=lambda: False, ping=lambda h, p: False)


def test_doctor_reports(env, capsys, monkeypatch):
    tmp_path, conf = env
    monkeypatch.setattr(jasp, "ping", lambda h, p, timeout=3: False)
    monkeypatch.setattr(cli.apps, "find", lambda app: None)
    cli.main(setup_args(tmp_path, conf))
    capsys.readouterr()
    rc = cli.main(["doctor", "--dir", str(tmp_path / "ws"), "--settings-file", str(conf)])
    out = capsys.readouterr().out
    assert "switched on" in out and "Chat folder" in out
    assert "Claude Code is not installed" in out and rc == 1


def test_default_command_is_setup(env, monkeypatch):
    seen = {}
    monkeypatch.setattr(cli, "cmd_setup", lambda a, ui: seen.setdefault("cmd", a.cmd) and 0)
    cli.main(["--yes", "--no-launcher"])
    assert seen["cmd"] == "setup"
