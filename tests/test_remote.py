import json
import os
import sys
import time

import pytest

from full_fat import apps, cli, prompts, remote, state
from test_cli import env, launch_world, setup_args  # noqa: F401  (env is a fixture)


def fake_claude(tmp_path, auth: dict | None, help_text: str):
    """A stand-in Claude Code that answers `auth status` with auth (JSON) and --help with help_text."""
    if os.name == "nt":
        pytest.skip("a POSIX shell stand-in")
    p = tmp_path / "fake-claude"
    out = json.dumps(auth) if auth is not None else "not json"
    p.write_text("#!/bin/sh\n"
                 f'if [ "$1" = auth ]; then echo \'{out}\'; exit 0; fi\n'
                 f'if [ "$1" = --help ]; then echo \'{help_text}\'; exit 0; fi\n'
                 "exit 1\n")
    p.chmod(0o755)
    return str(p)


ACCOUNT = {"loggedIn": True, "authMethod": "claude.ai", "apiProvider": "firstParty"}
HELP = "  --remote-control [name]   Start an interactive session with Remote Control enabled"


@pytest.fixture(autouse=True)
def no_api_env(monkeypatch):
    for k in remote.NOT_ACCOUNT_ENV:
        monkeypatch.delenv(k, raising=False)


def test_available_with_a_claude_account_and_a_new_claude_code(tmp_path):
    assert remote.unavailable(fake_claude(tmp_path, ACCOUNT, HELP)) is None


def test_old_claude_code_keeps_the_terminal(tmp_path):
    assert remote.unavailable(fake_claude(tmp_path, ACCOUNT, "  --resume")) == "old"


@pytest.mark.parametrize("auth", [{"loggedIn": True, "authMethod": "api_key"},
                                  {"authMethod": "claude.ai", "apiProvider": "bedrock"}, None])
def test_api_keys_other_providers_and_unknown_sign_in_keep_the_terminal(tmp_path, auth):
    assert remote.unavailable(fake_claude(tmp_path, auth, HELP)) == "account"


def test_an_api_key_in_the_environment_keeps_the_terminal(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://localhost:1")
    assert remote.unavailable(fake_claude(tmp_path, ACCOUNT, HELP)) == "account"


def test_a_missing_or_broken_claude_keeps_the_terminal(tmp_path):
    assert remote.unavailable(str(tmp_path / "nothing")) == "account"


def write_session(config, pid, **fields):
    (config / "sessions").mkdir(parents=True, exist_ok=True)
    data = {"pid": pid, "startedAt": int(time.time() * 1000), **fields}
    (config / "sessions" / f"{pid}.json").write_text(json.dumps(data))


def test_session_url_from_claude_codes_session_file(tmp_path):
    write_session(tmp_path, 4242, bridgeSessionId=None)
    assert remote.session_url(4242, time.time(), tmp_path) is None  # not connected yet
    write_session(tmp_path, 4242, bridgeSessionId="session_01GJRQ6enC4B5E8duDNG3uJ2")
    assert remote.session_url(4242, time.time(), tmp_path) == \
        "https://claude.ai/code/session_01GJRQ6enC4B5E8duDNG3uJ2"


@pytest.mark.parametrize("sid", ["session_x/../../evil", "https://example.com", "", 5])
def test_session_url_only_accepts_a_session_id(tmp_path, sid):
    write_session(tmp_path, 7, bridgeSessionId=sid)
    assert remote.session_url(7, time.time(), tmp_path) is None


def test_session_url_ignores_a_file_left_by_an_earlier_program(tmp_path):
    write_session(tmp_path, 7, bridgeSessionId="session_01GJRQ6enC4B5E8duDNG3uJ2", startedAt=1000)
    assert remote.session_url(7, time.time(), tmp_path) is None
    write_session(tmp_path, 8, bridgeSessionId="session_01GJRQ6enC4B5E8duDNG3uJ2")
    (tmp_path / "sessions" / "7.json").write_text((tmp_path / "sessions" / "8.json").read_text())
    assert remote.session_url(7, time.time(), tmp_path) is None  # another process's record


def test_session_url_uses_claude_config_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfg"))
    write_session(tmp_path / "cfg", 9, bridgeSessionId="session_01GJRQ6enC4B5E8duDNG3uJ2")
    assert remote.session_url(9, time.time()) is not None


def test_watch_opens_the_chat_once_and_stops_with_the_chat(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfg"))
    ticks = {"n": 0}

    def running():
        ticks["n"] += 1
        if ticks["n"] == 3:  # Remote Control connects a little after the start
            write_session(tmp_path / "cfg", 11, bridgeSessionId="session_01GJRQ6enC4B5E8duDNG3uJ2")
        return ticks["n"] < 8
    opened = []
    url = remote.watch(11, time.time(), still_running=running, open_link=opened.append, sleep=lambda s: None)
    assert opened == ["https://claude.ai/code/session_01GJRQ6enC4B5E8duDNG3uJ2"] == [url]


def test_watch_opens_nothing_when_claude_code_never_connects(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfg"))
    ticks = iter(range(5))
    opened = []
    assert remote.watch(12, time.time(), still_running=lambda: next(ticks) < 4,
                        open_link=opened.append, sleep=lambda s: None) is None
    assert opened == []


def test_launch_command_adds_remote_control_before_the_greeting(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfg"))
    cmd = apps.launch_command(apps.CLAUDE, "claude", "Hi.", tmp_path, remote.NAME)
    assert cmd[-3:] == ["--remote-control", "Full Fat", "Hi."]
    assert "--remote-control" not in apps.launch_command(apps.CLAUDE, "claude", "Hi.", tmp_path)
    assert "--remote-control" not in apps.launch_command(apps.CODEX, "codex", "Hi.", tmp_path, remote.NAME)


# ---------------------------------------------------------------------------- full-fat launch

@pytest.fixture
def launch(env, monkeypatch):
    """full-fat launch with everything faked; returns what it would exec and the helpers it started."""
    tmp_path, conf = env
    w, seen = launch_world(env, monkeypatch)
    helpers = []
    monkeypatch.setattr(remote, "start_detached", lambda pid: helpers.append(pid))
    return tmp_path, seen, helpers


@pytest.mark.skipif(os.name == "nt", reason="Windows runs the chat app with subprocess instead of exec")
def test_launch_opens_claude_in_the_browser_by_default(launch, monkeypatch, capsys):
    tmp_path, seen, helpers = launch
    monkeypatch.setattr(remote, "unavailable", lambda exe: None)
    assert cli.main(["launch", "--yes"]) == 0
    assert seen["cmd"][-3:] == ["--remote-control", "Full Fat", prompts.INTRO_MESSAGE]
    assert helpers == [os.getpid()]
    out = " ".join(capsys.readouterr().out.split())
    assert "also opens in your web browser" in out and "https://claude.ai/code" in out
    assert "closing it ends the chat" in out and "/exit" in out and "sign in to claude.ai" in out


@pytest.mark.skipif(os.name == "nt", reason="Windows runs the chat app with subprocess instead of exec")
@pytest.mark.parametrize("why", ["account", "old"])
def test_launch_keeps_the_terminal_when_the_browser_is_unavailable(launch, monkeypatch, capsys, why):
    tmp_path, seen, helpers = launch
    monkeypatch.setattr(remote, "unavailable", lambda exe: why)
    assert cli.main(["launch", "--yes"]) == 0
    assert "--remote-control" not in seen["cmd"] and seen["cmd"][-1] == prompts.INTRO_MESSAGE
    assert helpers == []
    assert "Your chat stays in this window" in " ".join(capsys.readouterr().out.split())


@pytest.mark.skipif(os.name == "nt", reason="Windows runs the chat app with subprocess instead of exec")
def test_open_in_terminal_keeps_claude_in_the_terminal(launch, monkeypatch):
    tmp_path, seen, helpers = launch
    monkeypatch.setattr(remote, "unavailable", lambda exe: pytest.fail("checked the browser"))
    assert cli.main(["launch", "--yes", "--open-in", "terminal"]) == 0
    assert "--remote-control" not in seen["cmd"] and helpers == []
    state.save({"claude_in": "terminal"})
    assert cli.main(["launch", "--yes"]) == 0
    assert "--remote-control" not in seen["cmd"] and helpers == []
    monkeypatch.setattr(remote, "unavailable", lambda exe: None)
    assert cli.main(["launch", "--yes", "--open-in", "browser"]) == 0
    assert "--remote-control" in seen["cmd"]


def test_setup_remembers_where_claude_chats_open(env, capsys):
    tmp_path, conf = env
    assert cli.main(setup_args(tmp_path, conf)) == 0
    assert state.load()["claude_in"] == "browser"
    out = " ".join(capsys.readouterr().out.split())
    assert "Claude chats also open in your web browser" in out and "closing it ends the chat" in out
    assert cli.main(setup_args(tmp_path, conf, "--open-in", "terminal")) == 0
    assert state.load()["claude_in"] == "terminal"
    assert "Claude chats also open in your web browser" not in capsys.readouterr().out
    assert cli.main(setup_args(tmp_path, conf, "--open-in", "app")) == 0  # a ChatGPT choice: Claude's stays
    assert state.load()["claude_in"] == "terminal"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX helper")
def test_the_detached_helper_does_not_stay_a_child(tmp_path, monkeypatch):
    """start_detached returns at once and leaves no child process behind (the helper belongs to init)."""
    monkeypatch.setattr(remote, "watch", lambda *a, **k: None)
    assert remote.start_detached(os.getpid()) is True
    with pytest.raises(ChildProcessError):
        os.waitpid(-1, os.WNOHANG)
