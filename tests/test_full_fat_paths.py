"""The default chat folder and the icon have a space in their name: check every place that could split it."""
import json
import os
import shlex
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from conftest import make_fetcher
from full_fat import apps, cli, jasp, launcher, prompts, state, workspace
from full_fat.ui import UI, keep


@pytest.fixture
def home(tmp_path, monkeypatch, fake_github):
    """A whole setup with the defaults, in a throwaway home."""
    h = tmp_path / "home"
    (h / "Desktop").mkdir(parents=True)
    conf = tmp_path / "JASP.conf"
    conf.write_text("[General]\naiEnabled=true\n")
    monkeypatch.setattr(Path, "home", lambda: h)
    monkeypatch.setenv("XDG_DATA_HOME", str(h / "share"))
    monkeypatch.setattr(launcher, "desktop_dir", lambda: h / "Desktop")
    monkeypatch.setattr(prompts, "fetch", make_fetcher(fake_github))
    monkeypatch.setattr(jasp, "running", lambda: False)
    for k in ("claude", "codex"):  # stand-in chat apps: never touch real ones
        fake = h / "bin" / k
        fake.parent.mkdir(exist_ok=True)
        fake.write_text("")
        monkeypatch.setenv(f"FULL_FAT_{k.upper()}", str(fake))
    args = ["setup", "--yes", "--settings-file", str(conf), "--jasp-version", "0.98.1", "--app", "both",
            "--no-install-apps", "--no-sign-in"]
    return h, args


def test_default_folder_and_icon(home, capsys):
    h, args = home
    assert cli.main(args) == 0
    folder = h / "Full Fat"
    assert state.default_workspace() == folder
    assert (folder / "AGENTS.md").read_text().startswith("# Full Fat\n")
    st = state.load()
    assert st["dir"] == str(folder) and st["launchers"]
    assert Path(st["launchers"][0]).stem == "Full Fat" and Path(st["launchers"][0]).parent == h / "Desktop"
    out = capsys.readouterr().out
    assert str(folder) in out and st["launchers"][0] in out  # not split by the line wrapping
    codex = (Path(os.environ["CODEX_HOME"]) / "config.toml").read_text()
    assert tomllib.loads(codex)["projects"][str(folder)] == {"trust_level": "trusted"}


def test_uninstall_with_default_folder(home):
    h, args = home
    cli.main(args)
    made = [Path(x) for x in state.load()["launchers"]]
    assert cli.main(["uninstall", "--yes"]) == 0
    assert not (h / "Full Fat").exists() and not any(p.exists() for p in made)
    assert "projects" not in tomllib.loads((Path(os.environ["CODEX_HOME"]) / "config.toml").read_text())


def earlier_icon(h, name="Earlier name.desktop", text="[Desktop Entry]\nComment=Chat about JASP (Full Fat)\n"):
    p = h / "Desktop" / name
    p.write_text(text)
    return p


def test_setup_replaces_only_recorded_icons(home):
    h, args = home
    recorded = earlier_icon(h)
    unrecorded = earlier_icon(h, "Not recorded.desktop")
    replaced_by_user = earlier_icon(h, "Edited.desktop", "my own file\n")
    state.save({"launchers": [str(recorded), str(replaced_by_user)]})
    assert cli.main(args) == 0
    assert not recorded.exists() and unrecorded.exists() and replaced_by_user.exists()
    assert all(Path(x).stem.lower() in ("full fat", "full-fat") for x in state.load()["launchers"])


def test_setup_without_launcher_keeps_the_recorded_one(home):
    h, args = home
    recorded = earlier_icon(h)
    state.save({"launchers": [str(recorded)]})
    assert cli.main([*args, "--no-launcher"]) == 0
    assert recorded.exists() and state.load()["launchers"] == [str(recorded)]


def test_uninstall_removes_only_recorded_icons(home):
    h, args = home
    cli.main(args)
    unrecorded = earlier_icon(h)
    cli.main(["uninstall", "--yes"])
    assert unrecorded.exists()


def test_unknown_state_fields_are_kept(home):
    h, args = home
    state.save({"from_a_newer_version": 7})
    cli.main(args)
    assert state.load()["from_a_newer_version"] == 7


@pytest.mark.parametrize("pad", range(45, 101))
def test_wrapping_never_splits_a_path(pad):
    path = "/Users/a b/Library/Application Support/Full Fat"
    out = []
    UI(out=out.append).say("x" * pad + f" {keep(path)} (and more words after it)")
    assert path in "\n".join(out)
    assert "\x00" not in "".join(out)


def test_launcher_really_passes_the_spaced_folder(tmp_path, monkeypatch):
    here = tmp_path / "some dir"
    here.mkdir()
    record = here / "record.py"
    record.write_text("import json, sys\nopen(sys.argv[1], 'w').write(json.dumps(sys.argv[2:]))\n")
    seen = here / "seen.json"
    monkeypatch.setattr(launcher, "full_fat_command", lambda: [sys.executable, str(record), str(seen)])
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    folder = tmp_path / "Full Fat"
    made = launcher.create(folder, desktop=here)[0]
    if made.suffix == ".lnk":  # Windows: the shortcut opens the script in Full Fat's own folder
        made = launcher.create(folder, desktop=here)[1]
    if made.suffix == ".desktop":
        cmd = shlex.split(next(x[5:] for x in made.read_text().splitlines() if x.startswith("Exec=")))
        assert f"\nPath={folder}\n" in made.read_text()
    else:
        cmd = [str(made)]
    subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL, timeout=30)
    assert json.loads(seen.read_text()) == ["launch", "--dir", str(folder)]


@pytest.mark.real_connector
def test_connector_with_spaces_everywhere(tmp_path):
    from full_fat import connector
    folder = tmp_path / "Full Fat"
    folder.mkdir()
    script = folder / "fake server.py"
    script.write_text('import sys\nsys.stdin.readline()\nassert sys.argv[1:] == ["mcp<2", "name @ url"]\n'
                      'print(\'{"id": 1, "result": {}}\', flush=True)\n')
    server = {"command": sys.executable, "args": [str(script), "mcp<2", "name @ url"]}
    assert connector.warm(server, folder, 30) == (True, "")


def test_configs_keep_spaces():
    uvx = "/Users/a b/.local/bin/uvx"
    assert tomllib.loads(workspace.codex_config(uvx, "127.0.0.1", 1, False))["mcp_servers"]["jasp"]["command"] == uvx
    assert workspace.mcp_server(uvx, "127.0.0.1", 1)["command"] == uvx
    home = Path("/Users/a b")
    assert workspace.read_rule(home / "Full Fat", home) == "Read(~/Full Fat/**)"
    assert workspace.read_rule(Path("C:/Users/a b/Full Fat"), Path("/elsewhere")) == "Read(//c/Users/a b/Full Fat/**)"
