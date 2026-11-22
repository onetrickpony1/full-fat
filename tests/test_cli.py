import json
import os
import sys
from pathlib import Path

import pytest

from conftest import make_fetcher
from full_fat import apps, cli, jasp, link, prompts, state
from full_fat.ui import UI

REAL = "[General]\naiEnabled=true\nshowRSyntax=false\n"


@pytest.fixture
def env(tmp_path, monkeypatch, fake_github):
    monkeypatch.setattr(prompts, "fetch", make_fetcher(fake_github))
    conf = tmp_path / "jasp" / "JASP.conf"
    conf.parent.mkdir()
    conf.write_text(REAL)
    monkeypatch.setattr(jasp, "running", lambda: False)
    monkeypatch.setattr("full_fat.ui.time.sleep", lambda s: None)
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)
    fake = tmp_path / "bin" / "claude"  # a stand-in Claude Code: never touch a real one
    fake.parent.mkdir()
    fake.write_text("")
    monkeypatch.setenv("FULL_FAT_CLAUDE", str(fake))
    monkeypatch.setenv("FULL_FAT_CODEX", str(tmp_path / "bin" / "no-codex"))
    monkeypatch.setattr(apps, "install", lambda app: pytest.fail("installed without consent"))
    return tmp_path, conf


def setup_args(tmp_path, conf, *extra):
    return ["setup", "--yes", "--dir", str(tmp_path / "ws"), "--settings-file", str(conf), "--jasp-version",
            "0.98.1", "--app", "claude", "--no-install-apps", "--no-sign-in", "--no-launcher", *extra]


def store_of(conf):
    return jasp.Store("ini", "JASP", path=conf)


# ---------------------------------------------------------------------------- setup and JASP's setting

def test_setup_leaves_the_setting_off(env, capsys):
    tmp_path, conf = env
    assert cli.main(setup_args(tmp_path, conf)) == 0
    assert conf.read_text() == REAL  # not switched on
    assert (tmp_path / "ws" / "AGENTS.md").is_file()
    st = state.load()
    assert st["dir"] == str(tmp_path / "ws") and st["apps"] == ["claude"]
    assert st["jasp_changes"][0]["previous"] is None
    backups = list(state.backup_dir().iterdir())
    assert len(backups) == 1 and backups[0].read_text() == REAL
    assert "== Done" in capsys.readouterr().out


def test_setup_switches_off_what_an_older_full_fat_left_on(env, monkeypatch):
    tmp_path, conf = env
    state.save({"jasp_changes": [{"store": store_of(conf).to_json(), "previous": None}]})
    conf.write_text(REAL + "rpcServerEnabled=true\n")
    monkeypatch.setattr(jasp, "running", lambda: True)  # also while JASP runs: it never writes the key back
    assert cli.main(setup_args(tmp_path, conf)) == 0
    assert "rpcServerEnabled" not in conf.read_text()


def test_setup_keeps_the_users_own_setting(env, capsys):
    tmp_path, conf = env
    conf.write_text("[General]\nrpcServerEnabled=true\n")
    assert cli.main(setup_args(tmp_path, conf)) == 0
    assert "rpcServerEnabled=true" in conf.read_text()
    assert "stays on" in capsys.readouterr().out
    assert cli.main(["uninstall", "--yes"]) == 0
    assert conf.read_text() == "[General]\nrpcServerEnabled=true\n"


def test_too_old(env, capsys):
    tmp_path, conf = env
    args = setup_args(tmp_path, conf)
    args[args.index("0.98.1")] = "0.97.1"
    assert cli.main(args) == 1
    assert "needs JASP 0.98.0 or newer" in capsys.readouterr().out
    assert conf.read_text() == REAL


def test_no_chat_app_means_not_done(env, monkeypatch, capsys):
    tmp_path, conf = env
    monkeypatch.setenv("FULL_FAT_CLAUDE", str(tmp_path / "missing"))
    assert cli.main(setup_args(tmp_path, conf)) == 1
    out = capsys.readouterr().out
    assert "Not finished" in out and "== Done" not in out


def test_yes_never_installs_but_install_apps_does(env, monkeypatch, capsys):
    tmp_path, conf = env
    monkeypatch.setenv("FULL_FAT_CLAUDE", str(tmp_path / "missing"))
    args = [a for a in setup_args(tmp_path, conf) if a != "--no-install-apps"]
    assert cli.main(args) == 1  # apps.install fails the test if it is called
    assert "only when you say so" in capsys.readouterr().out
    done = []

    def install(app):
        done.append(app.key)
        (tmp_path / "missing").write_text("")
        return True
    monkeypatch.setattr(apps, "install", install)
    assert cli.main(args + ["--install-apps"]) == 0 and done == ["claude"]


def test_closed_input_does_not_install(env, monkeypatch):
    tmp_path, conf = env
    monkeypatch.setenv("FULL_FAT_CLAUDE", str(tmp_path / "missing"))

    def no_input(prompt):
        raise EOFError
    assert cli.ensure_app(apps.CLAUDE, UI(inp=no_input), may_install=True, may_sign_in=False) is None


def test_rerun_and_careful_is_remembered(env):
    tmp_path, conf = env
    cli.main(setup_args(tmp_path, conf, "--careful"))
    (tmp_path / "ws" / "mine.txt").write_text("x")
    cli.main(setup_args(tmp_path, conf))
    s = json.loads((tmp_path / "ws" / ".claude" / "settings.json").read_text())
    assert "mcp__jasp__jasp_analysis_run" not in s["permissions"]["allow"]  # still careful
    assert (tmp_path / "ws" / "mine.txt").read_text() == "x"
    cli.main(setup_args(tmp_path, conf, "--no-careful"))
    s = json.loads((tmp_path / "ws" / ".claude" / "settings.json").read_text())
    assert "mcp__jasp__jasp_analysis_run" in s["permissions"]["allow"]


def test_first_run_notes_say_how_to_trust(env, capsys):
    tmp_path, conf = env
    cli.main(setup_args(tmp_path, conf))
    out = " ".join(capsys.readouterr().out.split())
    assert 'Press the Down arrow once, so that "Yes, I trust this folder" is picked, then press Enter' in out
    assert "Open a new Terminal window and type: full-fat launch" in out


def test_setup_fails_when_connector_fails(env, monkeypatch, capsys):
    tmp_path, conf = env
    from full_fat import connector
    monkeypatch.setattr(connector, "warm", lambda server, cwd, timeout=300: (
        False, "error: Building source distributions is disabled, but attempted to build `cryptography`"))
    assert cli.main(setup_args(tmp_path, conf)) == 1
    out = capsys.readouterr().out
    assert "could not be prepared" in out and "no ready-made version" in out and "Almost done" in out
    assert "internet" not in out


def test_default_command_is_setup(env, monkeypatch):
    seen = {}
    monkeypatch.setattr(cli, "cmd_setup", lambda a, ui: seen.setdefault("cmd", a.cmd) and 0)
    cli.main(["--yes", "--no-launcher"])
    assert seen["cmd"] == "setup"


# ---------------------------------------------------------------------------- starting a chat

class World:
    """A pretend JASP that reads rpcServerEnabled only when it starts, as the real one does."""

    def __init__(self, conf, running=False, server=False):
        self.conf, self.is_up, self.server, self.starts = conf, running, server, []

    def running(self):
        return self.is_up

    def ping(self, host, port):
        return self.is_up and self.server

    def open(self, _j):
        self.is_up = True
        self.server = store_of(self.conf).enabled()
        self.starts.append(self.server)
        return True


def connect(world, monkeypatch, conf, answers=("",)):
    monkeypatch.setattr(jasp, "open_jasp", world.open)
    j = jasp.detect(str(conf), "0.98.1")
    it = iter(answers)

    def inp(prompt):
        try:
            return next(it)
        except StopIteration:
            raise EOFError from None
    return cli.connect(j, "127.0.0.1", 48164, UI(inp=inp), is_running=world.running, ping=world.ping, start_wait=1)


def test_connect_when_jasp_is_closed(env, monkeypatch):
    tmp_path, conf = env
    w = World(conf)
    assert connect(w, monkeypatch, conf)
    assert w.starts == [True]  # JASP started with its connection on
    assert w.ping("", 0)  # still answering
    assert "rpcServerEnabled" not in conf.read_text()  # but the setting is off again on disk
    w.is_up = False
    w.open(None)  # the next JASP start without Full Fat
    assert w.starts[-1] is False


def test_connect_when_jasp_already_answers(env, monkeypatch):
    tmp_path, conf = env
    state.save({"jasp_changes": [{"store": store_of(conf).to_json(), "previous": None}]})
    conf.write_text(REAL + "rpcServerEnabled=true\n")  # left on by an interrupted start
    w = World(conf, running=True, server=True)
    assert connect(w, monkeypatch, conf)
    assert w.starts == [] and "rpcServerEnabled" not in conf.read_text()


def test_connect_asks_to_close_jasp_without_its_connection(env, monkeypatch, capsys):
    tmp_path, conf = env
    w = World(conf, running=True, server=False)
    polls = {"n": 0}

    def running():
        polls["n"] += 1
        if polls["n"] > 3:
            w.is_up = False  # the user closes JASP
        return w.is_up
    w.running = running
    assert connect(w, monkeypatch, conf)
    out = capsys.readouterr().out
    assert "close JASP" in out and w.starts == [True]
    assert "rpcServerEnabled" not in conf.read_text()


def test_connect_switches_off_when_stopped(env, monkeypatch):
    tmp_path, conf = env
    w = World(conf)

    def open_and_stop(_j):
        assert store_of(conf).enabled()
        raise KeyboardInterrupt
    monkeypatch.setattr(jasp, "open_jasp", open_and_stop)
    with pytest.raises(KeyboardInterrupt):
        cli.connect(jasp.detect(str(conf), "0.98.1"), "h", 1, UI(yes=True), is_running=w.running, ping=w.ping)
    assert "rpcServerEnabled" not in conf.read_text()


def test_connect_gives_up_and_switches_off(env, monkeypatch):
    tmp_path, conf = env
    w = World(conf)
    w.open = lambda _j: True  # JASP opens but never answers (for example a question nobody answers)
    assert not connect(w, monkeypatch, conf, answers=())
    assert "rpcServerEnabled" not in conf.read_text()


def test_connect_keeps_the_users_own_setting(env, monkeypatch):
    tmp_path, conf = env
    conf.write_text("[General]\nrpcServerEnabled=true\n")
    w = World(conf)
    assert connect(w, monkeypatch, conf)
    assert conf.read_text() == "[General]\nrpcServerEnabled=true\n"


@pytest.mark.skipif(os.name == "nt", reason="Windows runs the chat app with subprocess instead of exec")
def test_launch_starts_the_chat(env, monkeypatch):
    tmp_path, conf = env
    cli.main(setup_args(tmp_path, conf))
    w = World(conf)
    monkeypatch.setattr(jasp, "open_jasp", w.open)
    monkeypatch.setattr(jasp, "ping", w.ping)
    monkeypatch.setattr(jasp, "running", w.running)
    monkeypatch.setattr(apps, "signed_in", lambda app, exe: True)
    seen = {}
    monkeypatch.setattr(cli.os, "execv", lambda exe, cmd: seen.update(cmd=cmd))
    monkeypatch.setattr(cli, "real_terminal_input", lambda: None)
    monkeypatch.setattr(cli.os, "chdir", lambda d: seen.update(cwd=d))
    assert cli.main(["launch", "--yes"]) == 0
    assert seen["cwd"] == tmp_path / "ws" and seen["cmd"][-1] == prompts.INTRO_MESSAGE
    assert "rpcServerEnabled" not in conf.read_text()


# ---------------------------------------------------------------------------- doctor

def test_doctor_reports(env, capsys, monkeypatch):
    tmp_path, conf = env
    monkeypatch.setattr(jasp, "ping", lambda h, p, timeout=3: False)
    monkeypatch.setenv("FULL_FAT_CLAUDE", str(tmp_path / "missing"))
    cli.main(setup_args(tmp_path, conf))
    capsys.readouterr()
    rc = cli.main(["doctor", "--dir", str(tmp_path / "ws"), "--settings-file", str(conf)])
    out = capsys.readouterr().out
    assert "off until Full Fat opens JASP" in out and "Chat folder" in out
    assert "Claude Code is not installed" in out and rc == 1


def test_doctor_finds_a_setting_left_on(env, capsys, monkeypatch):
    tmp_path, conf = env
    monkeypatch.setattr(jasp, "ping", lambda h, p, timeout=3: False)
    cli.main(setup_args(tmp_path, conf))
    conf.write_text(REAL + "rpcServerEnabled=true\n")
    capsys.readouterr()
    assert cli.main(["doctor", "--dir", str(tmp_path / "ws"), "--settings-file", str(conf)]) == 1
    assert "left switched on" in capsys.readouterr().out


# ---------------------------------------------------------------------------- uninstall

def test_uninstall_restores_and_removes_only_full_fats_files(env):
    tmp_path, conf = env
    conf.write_text("[General]\nrpcServerEnabled=false\n")
    cli.main(setup_args(tmp_path, conf))
    ws = tmp_path / "ws"
    (ws / "mine.txt").write_text("x")
    (ws / "my folder").mkdir()
    (ws / "AGENTS.md").write_text("I changed this")
    assert cli.main(["uninstall", "--yes"]) == 0
    assert conf.read_text() == "[General]\nrpcServerEnabled=false\n"
    assert sorted(p.name for p in ws.iterdir()) == ["AGENTS.md", "mine.txt", "my folder"]
    assert not state.state_file().exists()


def test_uninstall_removes_an_untouched_folder(env):
    tmp_path, conf = env
    cli.main(setup_args(tmp_path, conf))
    assert cli.main(["uninstall", "--yes"]) == 0
    assert not (tmp_path / "ws").exists() and conf.read_text() == REAL


def test_uninstall_never_deletes_a_folder_full_fat_did_not_make(env):
    tmp_path, conf = env
    other = tmp_path / "other"
    other.mkdir()
    (other / "AGENTS.md").write_text("mine")
    assert cli.main(["uninstall", "--yes", "--dir", str(other)]) == 0
    assert (other / "AGENTS.md").read_text() == "mine"


def test_uninstall_with_closed_input_does_nothing(env):
    tmp_path, conf = env
    cli.main(setup_args(tmp_path, conf))

    def no_input(prompt):
        raise EOFError
    a = cli.parser().parse_args(["uninstall"])
    assert cli.cmd_uninstall(a, UI(inp=no_input)) == 1
    assert (tmp_path / "ws" / "AGENTS.md").exists() and state.state_file().exists()


@pytest.mark.skipif(os.name == "nt", reason="symlinks need extra rights on Windows")
def test_uninstall_counts_and_keeps_links(env, capsys):
    tmp_path, conf = env
    cli.main(setup_args(tmp_path, conf))
    ws = tmp_path / "ws"
    target = tmp_path / "data"
    target.mkdir()
    (target / "keep.csv").write_text("1")
    (ws / "data link").symlink_to(target, target_is_directory=True)
    cli.main(["uninstall", "--yes"])
    assert (target / "keep.csv").exists() and (ws / "data link").is_symlink()
    assert "1 other file(s)" in " ".join(capsys.readouterr().out.split())


# ---------------------------------------------------------------------------- the terminal handed to the chat app

@pytest.mark.skipif(not hasattr(os, "openpty"), reason="needs a pseudo-terminal")
def test_real_terminal_input_replaces_dev_tty(tmp_path):
    import subprocess
    script = tmp_path / "t.py"
    script.write_text(
        "import os, sys\n"
        f"sys.path.insert(0, {str(Path(cli.__file__).parents[1])!r})\n"
        "from full_fat import cli\n"
        "fd = os.open('/dev/tty', os.O_RDWR); os.dup2(fd, 0)\n"
        "before = os.ttyname(0); cli.real_terminal_input()\n"
        "print(before, os.ttyname(0), os.ttyname(1))\n")
    master, slave = os.openpty()
    try:
        r = subprocess.run([sys.executable, str(script)], stdin=slave, stdout=slave, stderr=subprocess.PIPE,
                           start_new_session=True, timeout=30,
                           preexec_fn=lambda: __import__("fcntl").ioctl(0, __import__("termios").TIOCSCTTY, 0))
        out = os.read(master, 4096).decode().split()
    finally:
        os.close(master)
        os.close(slave)
    assert r.returncode == 0, r.stderr
    assert out[0] == "/dev/tty" and out[1] == out[2] != "/dev/tty"
