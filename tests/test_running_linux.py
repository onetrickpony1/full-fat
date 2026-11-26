"""jasp.running() on Linux: a JASP of a hidden test session (APPCHECK_SESSION) is not the user's JASP."""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from full_fat import jasp

linux = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="reads /proc")


def fake_proc(tmp_path, comm, environ):
    d = tmp_path / "proc" / "4242"
    d.mkdir(parents=True)
    (d / "comm").write_text(comm + "\n")
    if environ is not None:
        (d / "environ").write_bytes(environ)
    return d


@pytest.fixture
def on_linux(monkeypatch):
    monkeypatch.setattr(jasp, "system", lambda: "linux")


def test_user_jasp_counts(tmp_path, monkeypatch, on_linux):
    fake_proc(tmp_path, "JASP", b"HOME=/home/u\0PATH=/usr/bin\0")
    monkeypatch.setattr(jasp, "PROC", tmp_path / "proc")
    assert jasp.running()


def test_session_jasp_does_not_count(tmp_path, monkeypatch, on_linux):
    fake_proc(tmp_path, "JASP", b"HOME=/home/u\0APPCHECK_SESSION=/x/session-1\0PATH=/usr/bin\0")
    monkeypatch.setattr(jasp, "PROC", tmp_path / "proc")
    assert not jasp.running()


def test_name_inside_a_value_counts(tmp_path, monkeypatch, on_linux):
    fake_proc(tmp_path, "JASP", b"NOTE=APPCHECK_SESSION=/x\0")
    monkeypatch.setattr(jasp, "PROC", tmp_path / "proc")
    assert jasp.running()


def test_unreadable_environ_counts(tmp_path, monkeypatch, on_linux):
    fake_proc(tmp_path, "JASP", None)  # no environ file: reading it fails
    monkeypatch.setattr(jasp, "PROC", tmp_path / "proc")
    assert jasp.running()


def test_other_program_with_the_variable(tmp_path, monkeypatch, on_linux):
    fake_proc(tmp_path, "sleep", b"APPCHECK_SESSION=/x\0")
    monkeypatch.setattr(jasp, "PROC", tmp_path / "proc")
    assert not jasp.running()


def _wait_named(p, name="JASP"):
    for _ in range(100):
        try:
            if Path(f"/proc/{p.pid}/comm").read_text().strip() == name:
                return
        except OSError:
            pass
        time.sleep(0.02)
    raise AssertionError("stand-in did not start")


@linux
def test_stand_in_processes(tmp_path):
    """A real stand-in: a copy of sleep named JASP, with and without APPCHECK_SESSION."""
    if jasp.running():
        pytest.skip("a JASP is open on this computer")
    sleep = shutil.which("sleep")
    if not sleep:
        pytest.skip("no sleep program")
    standin = tmp_path / "JASP"
    shutil.copy2(sleep, standin)
    env = {k: v for k, v in os.environ.items() if k != "APPCHECK_SESSION"}

    tagged = subprocess.Popen([str(standin), "30"], env=dict(env, APPCHECK_SESSION=str(tmp_path / "session")))
    try:
        _wait_named(tagged)
        assert not jasp.running()
        user = subprocess.Popen([str(standin), "30"], env=env)
        try:
            _wait_named(user)
            assert jasp.running()
        finally:
            user.kill()
            user.wait()
        assert not jasp.running()
    finally:
        tagged.kill()
        tagged.wait()
