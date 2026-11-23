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


def test_connect_notices_when_jasp_does_not_start(env, monkeypatch, capsys):
    tmp_path, conf = env
    w = World(conf)
    w.open = lambda _j: True  # the start fails: JASP never shows up as running
    clock = {"t": 0.0}

    def tick():
        clock["t"] += 1
        return clock["t"]
    monkeypatch.setattr(cli.time, "monotonic", tick)
    monkeypatch.setattr("full_fat.ui.time.monotonic", tick)
    monkeypatch.setattr(jasp, "open_jasp", w.open)
    asked = []

    def inp(prompt):
        asked.append(prompt)
        raise EOFError
    assert not cli.connect(jasp.detect(str(conf), "0.98.1"), "127.0.0.1", 48164, UI(inp=inp),
                           is_running=w.running, ping=w.ping, start_wait=1000)
    assert "JASP closed again, or it did not start" in capsys.readouterr().out
    assert asked and "Open JASP yourself" in asked[0]
    assert clock["t"] < 200  # it stopped waiting soon, not after the full wait
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


def launch_world(env, monkeypatch, *setup_extra):
    tmp_path, conf = env
    assert cli.main(setup_args(tmp_path, conf, *setup_extra)) == 0
    w = World(conf)
    monkeypatch.setattr(jasp, "open_jasp", w.open)
    monkeypatch.setattr(jasp, "ping", w.ping)
    monkeypatch.setattr(jasp, "running", w.running)
    monkeypatch.setattr(apps, "signed_in", lambda app, exe: True)
    seen = {}
    monkeypatch.setattr(cli.os, "execv", lambda exe, cmd: seen.update(cmd=cmd))
    monkeypatch.setattr(cli, "real_terminal_input", lambda: None)
    monkeypatch.setattr(cli.os, "chdir", lambda d: seen.update(cwd=d))
    return w, seen


def app_setup_args(tmp_path, conf):
    return [a if a != "claude" else "codex" for a in setup_args(tmp_path, conf)]


def test_setup_picks_the_chatgpt_app_when_it_is_installed(env, monkeypatch, capsys):
    tmp_path, conf = env
    monkeypatch.setenv("FULL_FAT_CHATGPT_APP", "yes")  # Codex for the Terminal is not installed (env fixture)
    assert cli.main(app_setup_args(tmp_path, conf)) == 0  # done, without Codex for the Terminal
    assert state.load()["chatgpt_in"] == "app"
    out = " ".join(capsys.readouterr().out.split())
    assert "ChatGPT chats open in the ChatGPT app" in out and "Codex side" in out and "sign in" in out
    assert "close the Terminal window" in out and "picker under the message box" in out
    assert "Press Enter to send it" in out
    assert "Codex may show a welcome screen" not in out
    assert "Codex.app" not in out and "config" not in out.lower().replace("configur", "")


def test_setup_keeps_the_terminal_without_the_app(env, monkeypatch):
    tmp_path, conf = env
    fake = tmp_path / "bin" / "codex"
    fake.write_text("")
    monkeypatch.setenv("FULL_FAT_CODEX", str(fake))
    assert cli.main(app_setup_args(tmp_path, conf)) == 0
    assert state.load()["chatgpt_in"] == "terminal"
    monkeypatch.setenv("FULL_FAT_CHATGPT_APP", "yes")
    assert cli.main(app_setup_args(tmp_path, conf) + ["--open-in", "terminal"]) == 0
    assert state.load()["chatgpt_in"] == "terminal"


def test_setup_asks_where_and_defaults_to_the_app(env, monkeypatch):
    monkeypatch.setenv("FULL_FAT_CHATGPT_APP", "yes")
    asked = []

    def inp(prompt):
        asked.append(prompt)
        return ""
    a = cli.parser().parse_args(["setup"])
    assert cli.chatgpt_place(a, {}, UI(inp=inp)) == "app" and asked
    assert cli.chatgpt_place(a, {}, UI(inp=lambda p: "2")) == "terminal"
    assert cli.chatgpt_place(a, {"chatgpt_in": "terminal"}, UI(yes=True)) == "terminal"
    monkeypatch.setenv("FULL_FAT_CHATGPT_APP", "none")
    assert cli.chatgpt_place(a, {}, UI(inp=inp)) == "terminal"


def test_launch_opens_the_chatgpt_app_after_switching_the_setting_off(env, monkeypatch, capsys):
    tmp_path, conf = env
    monkeypatch.setenv("FULL_FAT_CHATGPT_APP", "yes")
    w, seen = launch_world(env, monkeypatch)
    state.save({"apps": ["codex"], "chatgpt_in": "app"})
    opened = []

    def open_app(url):
        assert "rpcServerEnabled" not in conf.read_text()  # off on disk before the app opens
        opened.append(url)
        return True
    monkeypatch.setattr(apps, "open_desktop_app", open_app)
    assert cli.main(["launch", "--yes"]) == 0
    assert w.starts == [True] and opened == [apps.deep_link(tmp_path / "ws", prompts.INTRO_MESSAGE)]
    assert "cmd" not in seen  # no Terminal chat
    out = " ".join(capsys.readouterr().out.split())
    assert "opening a new chat on its Codex side" in out and "close the Terminal window" in out


@pytest.mark.skipif(os.name == "nt", reason="Windows runs the chat app with subprocess instead of exec")
def test_launch_falls_back_to_the_terminal_when_the_app_does_not_open(env, monkeypatch, capsys):
    tmp_path, conf = env
    monkeypatch.setenv("FULL_FAT_CHATGPT_APP", "yes")
    fake = tmp_path / "bin" / "codex"
    fake.write_text("")
    monkeypatch.setenv("FULL_FAT_CODEX", str(fake))
    w, seen = launch_world(env, monkeypatch)
    state.save({"apps": ["codex"], "chatgpt_in": "app"})
    monkeypatch.setattr(apps, "open_desktop_app", lambda url: False)
    assert cli.main(["launch", "--yes"]) == 0
    assert "did not open, so the chat starts here in the Terminal" in " ".join(capsys.readouterr().out.split())
    assert seen["cmd"][0] == str(fake) and seen["cmd"][-1] == prompts.INTRO_MESSAGE
    assert w.starts == [True] and "rpcServerEnabled" not in conf.read_text()


@pytest.mark.skipif(os.name == "nt", reason="Windows runs the chat app with subprocess instead of exec")
def test_launch_uses_the_terminal_when_the_app_is_gone(env, monkeypatch, capsys):
    tmp_path, conf = env
    fake = tmp_path / "bin" / "codex"
    fake.write_text("")
    monkeypatch.setenv("FULL_FAT_CODEX", str(fake))
    w, seen = launch_world(env, monkeypatch)
    state.save({"apps": ["codex"], "chatgpt_in": "app"})  # FULL_FAT_CHATGPT_APP=none: the app was removed
    monkeypatch.setattr(apps, "open_desktop_app", lambda url: pytest.fail("tried to open a missing app"))
    assert cli.main(["launch", "--yes"]) == 0
    assert "could not find the ChatGPT app" in capsys.readouterr().out
    assert seen["cmd"][0] == str(fake)


@pytest.mark.skipif(os.name == "nt", reason="Windows runs the chat app with subprocess instead of exec")
def test_launch_open_in_terminal_overrides_the_app(env, monkeypatch):
    tmp_path, conf = env
    monkeypatch.setenv("FULL_FAT_CHATGPT_APP", "yes")
    fake = tmp_path / "bin" / "codex"
    fake.write_text("")
    monkeypatch.setenv("FULL_FAT_CODEX", str(fake))
    w, seen = launch_world(env, monkeypatch)
    state.save({"apps": ["codex"], "chatgpt_in": "app"})
    monkeypatch.setattr(apps, "open_desktop_app", lambda url: pytest.fail("opened the app"))
    assert cli.main(["launch", "--yes", "--open-in", "terminal"]) == 0
    assert seen["cmd"][0] == str(fake)


def test_doctor_checks_the_app_instead_of_terminal_codex(env, monkeypatch, capsys):
    tmp_path, conf = env
    monkeypatch.setattr(jasp, "ping", lambda h, p, timeout=3: False)
    monkeypatch.setenv("FULL_FAT_CHATGPT_APP", "yes")
    cli.main(app_setup_args(tmp_path, conf))
    capsys.readouterr()
    assert cli.main(["doctor", "--dir", str(tmp_path / "ws"), "--settings-file", str(conf)]) == 0
    assert "The ChatGPT app is installed" in capsys.readouterr().out
    monkeypatch.setenv("FULL_FAT_CHATGPT_APP", "none")
    assert cli.main(["doctor", "--dir", str(tmp_path / "ws"), "--settings-file", str(conf)]) == 1


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
    import select
    import time
    master, slave = os.openpty()
    data = b""
    try:
        # read while the child runs: on macOS the child's last close of the terminal waits until its output is read
        p = subprocess.Popen([sys.executable, str(script)], stdin=slave, stdout=slave, stderr=subprocess.PIPE,
                             start_new_session=True,
                             preexec_fn=lambda: __import__("fcntl").ioctl(0, __import__("termios").TIOCSCTTY, 0))
        os.close(slave)
        slave = -1
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            ready, _, _ = select.select([master], [], [], 0.5)
            if ready:
                try:
                    chunk = os.read(master, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                data += chunk
            elif p.poll() is not None:
                break
        p.wait(timeout=10)
        err = p.stderr.read().decode(errors="replace")
    finally:
        os.close(master)
        if slave != -1:
            os.close(slave)
    out = data.decode(errors="replace").split()
    assert p.returncode == 0, err
    assert out[0] == "/dev/tty" and out[1] == out[2] != "/dev/tty"
