from pathlib import Path

from full_fat.jasp import Store, ini_get, ini_remove, ini_set

REAL = "[General]\naiEnabled=true\ncheckUpdates=true\nrecentFolders=/a, /b\nshowRSyntax=false\n\n[Other]\nrpcServerEnabled=false\n"


def test_get_only_general():
    assert ini_get(REAL, "rpcServerEnabled") is None
    assert ini_get(REAL, "recentFolders") == "/a, /b"
    assert ini_get('[General]\nrpcServerIp="10.0.0.1"\n', "rpcServerIp") == "10.0.0.1"


def test_set_inserts_sorted_and_keeps_rest():
    out = ini_set(REAL, "rpcServerEnabled", "true")
    assert out == REAL.replace("recentFolders=/a, /b\n", "recentFolders=/a, /b\nrpcServerEnabled=true\n")
    assert ini_get(out, "rpcServerEnabled") == "true"
    # setting again replaces, not duplicates
    again = ini_set(out, "rpcServerEnabled", "false")
    assert again.count("rpcServerEnabled") == 2 and ini_get(again, "rpcServerEnabled") == "false"


def test_set_keeps_crlf():
    text = REAL.replace("\n", "\r\n")
    out = ini_set(text, "rpcServerEnabled", "true")
    assert "\r\nrpcServerEnabled=true\r\n" in out and "\n" not in out.replace("\r\n", "")


def test_set_without_general_or_empty():
    assert ini_set("", "rpcServerEnabled", "true").splitlines() == ["[General]", "rpcServerEnabled=true"]
    out = ini_set("[Other]\nx=1\n", "rpcServerEnabled", "true")
    assert out.startswith("[General]\nrpcServerEnabled=true\n\n[Other]")


def test_remove():
    out = ini_remove(ini_set(REAL, "rpcServerEnabled", "true"), "rpcServerEnabled")
    assert out == REAL


def test_store_backup_set_remove(tmp_path):
    conf = tmp_path / "JASP" / "JASP.conf"
    conf.parent.mkdir()
    conf.write_text(REAL)
    s = Store("ini", "JASP", path=conf)
    assert s.exists() and not s.enabled()
    b = s.backup(tmp_path / "bk")
    s.set("rpcServerEnabled", True)
    assert s.enabled() and b.read_text() == REAL
    s.backup(tmp_path / "bk")  # a second backup never replaces the original
    assert b.read_text() == REAL
    s.remove("rpcServerEnabled")
    assert conf.read_text() == REAL
    assert Store.from_json(s.to_json()) == s


def test_store_creates_missing_file(tmp_path):
    s = Store("ini", "JASP", path=tmp_path / "new" / "JASP.ini")
    assert s.backup(tmp_path / "bk") is None
    s.set("rpcServerEnabled", True)
    assert s.enabled()
