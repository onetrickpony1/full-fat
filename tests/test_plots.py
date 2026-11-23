import json
import os

import pytest

from full_fat import plots
from test_cli import env  # noqa: F401  (a fixture)

PNG = b"\x89PNG\r\n\x1a\n" + b"plot"


def jasp_temp(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    temp = tmp_path / "JASP" / "temp"
    (temp / "resources" / "3").mkdir(parents=True)
    (temp / "resources" / "3" / "_5.png").write_bytes(PNG + b"1")
    (temp / "resources" / "notes.txt").write_text("not a plot")
    folder = tmp_path / "Full Fat"
    folder.mkdir()
    return temp, folder


def test_copies_plots_into_the_chat_folder_at_the_same_path(tmp_path):
    temp, folder = jasp_temp(tmp_path)
    c = plots.Copier([temp, tmp_path / "missing"], folder)
    assert c.sync() == ["resources/3/_5.png"]
    assert (folder / "plots" / "resources" / "3" / "_5.png").read_bytes() == PNG + b"1"
    assert not (folder / "plots" / "resources" / "notes.txt").exists()
    assert c.sync() == []  # unchanged: not copied again
    (temp / "resources" / "3" / "_5.png").write_bytes(PNG + b"22")  # JASP redraws the plot
    os.utime(temp / "resources" / "3" / "_5.png", ns=(1, 1))
    assert c.sync() == ["resources/3/_5.png"]
    assert (folder / "plots" / "resources" / "3" / "_5.png").read_bytes() == PNG + b"22"
    index = json.loads((folder / "plots" / plots.INDEX).read_text())
    assert list(index) == ["resources/3/_5.png"]


def test_never_replaces_a_file_full_fat_did_not_copy(tmp_path):
    temp, folder = jasp_temp(tmp_path)
    mine = folder / "plots" / "resources" / "3" / "_5.png"
    mine.parent.mkdir(parents=True)
    mine.write_bytes(b"my own picture")
    assert plots.Copier([temp], folder).sync() == []
    assert mine.read_bytes() == b"my own picture"


@pytest.mark.skipif(os.name == "nt", reason="symlinks need extra rights on Windows")
def test_never_writes_through_a_link(tmp_path):
    temp, folder = jasp_temp(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (folder / "plots").symlink_to(elsewhere)
    assert plots.Copier([temp], folder).sync() == []
    assert list(elsewhere.iterdir()) == []


@pytest.mark.skipif(os.name == "nt", reason="symlinks need extra rights on Windows")
def test_skips_links_and_files_that_are_not_png(tmp_path):
    temp, folder = jasp_temp(tmp_path)
    secret = tmp_path / "secret.png"
    secret.write_bytes(PNG)
    (temp / "link.png").symlink_to(secret)
    (temp / "fake.png").write_text("not really a picture")
    assert plots.Copier([temp], folder).sync() == ["resources/3/_5.png"]


def test_the_next_chat_and_uninstall_delete_only_unchanged_copies(tmp_path):
    temp, folder = jasp_temp(tmp_path)
    (temp / "resources" / "4").mkdir()
    (temp / "resources" / "4" / "_1.png").write_bytes(PNG + b"4")
    plots.Copier([temp], folder).sync()
    edited = folder / "plots" / "resources" / "4" / "_1.png"
    edited.write_bytes(PNG + b"edited by you")
    (folder / "plots" / "yours.txt").write_text("keep me")
    assert plots.Copier([temp], folder).clear_earlier() == 1
    assert not (folder / "plots" / "resources" / "3").exists()
    assert edited.exists() and (folder / "plots" / "yours.txt").exists()
    edited.unlink()
    (folder / "plots" / "yours.txt").unlink()
    assert plots.clear(folder) == 0
    assert not (folder / "plots").exists()  # empty folders go too


def test_uninstall_removes_the_plot_copies_and_the_folder(env):
    from full_fat import cli  # noqa: PLC0415
    from test_cli import setup_args  # noqa: PLC0415
    tmp_path, conf = env
    cli.main(setup_args(tmp_path, conf))
    temp, _ = jasp_temp(tmp_path / "j")
    plots.Copier([temp], tmp_path / "ws").sync()
    assert (tmp_path / "ws" / "plots" / "resources" / "3" / "_5.png").is_file()
    assert cli.main(["uninstall", "--yes"]) == 0
    assert not (tmp_path / "ws").exists()


def test_the_browser_helper_copies_plots_while_the_chat_runs(tmp_path, monkeypatch):
    from full_fat import remote  # noqa: PLC0415
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfg"))
    temp, folder = jasp_temp(tmp_path)
    ticks = iter(range(4))

    def running():
        n = next(ticks)
        if n == 2:  # JASP draws a plot during the chat
            (temp / "resources" / "7").mkdir()
            (temp / "resources" / "7" / "_1.png").write_bytes(PNG + b"7")
        return n < 3
    remote.watch(1, folder, [temp], 0, still_running=running, open_link=lambda u: None, sleep=lambda s: None)
    assert (folder / "plots" / "resources" / "7" / "_1.png").is_file()
    assert (folder / "plots" / "resources" / "3" / "_5.png").is_file()
