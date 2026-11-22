import subprocess
import sys
import uuid

import pytest

from full_fat import jasp
from full_fat.jasp import Store


def test_defaults_store_commands(monkeypatch, tmp_path):
    calls = []
    values = {}

    def fake_run(cmd, timeout=20):
        calls.append(cmd)
        if cmd[1] == "read":
            v = values.get(cmd[3])
            return subprocess.CompletedProcess(cmd, 0 if v is not None else 1, stdout=f"{v}\n" if v else "", stderr="")
        if cmd[1] == "write":
            values[cmd[3]] = "1" if cmd[5] == "true" else "0"
        if cmd[1] == "delete":
            values.pop(cmd[3], None)
        if cmd[1] == "export":
            (tmp_path / "bk").mkdir(exist_ok=True)
            open(cmd[3], "w").write("plist")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(jasp, "run", fake_run)
    monkeypatch.setattr(Store, "exists", lambda self: True)
    s = Store("defaults", "JASP", domain=jasp.MAC_DOMAIN)
    assert not s.enabled()
    assert s.backup(tmp_path / "bk").name.endswith(".plist")
    s.set("rpcServerEnabled", True)
    assert ["defaults", "write", "org.jasp-stats.JASP", "rpcServerEnabled", "-bool", "true"] in calls
    assert s.enabled() and s.get("rpcServerEnabled") == "true"
    s.remove("rpcServerEnabled")
    assert not s.enabled()


@pytest.mark.skipif(sys.platform != "darwin", reason="needs macOS defaults")
def test_real_defaults_roundtrip(tmp_path):
    domain = f"org.full-fat.test-{uuid.uuid4().hex[:8]}"
    s = Store("defaults", "test", domain=domain)
    try:
        assert s.get("rpcServerEnabled") is None
        s.set("rpcServerEnabled", True)
        assert s.enabled()
        subprocess.run(["defaults", "write", domain, "rpcServerPort", "-int", "48164"], check=True)
        assert s.get("rpcServerPort") == "48164"
        assert s.backup(tmp_path).is_file()
        s.set("rpcServerEnabled", False)
        assert not s.enabled()
    finally:
        subprocess.run(["defaults", "delete", domain], capture_output=True)


def _make_app(root, version="0.99.0.0", short="0.99"):
    import plistlib
    app = root / "Applications" / "JASP.app"
    (app / "Contents").mkdir(parents=True)
    with open(app / "Contents" / "Info.plist", "wb") as f:
        plistlib.dump({"CFBundleName": "JASP", "CFBundleVersion": version,
                       "CFBundleShortVersionString": short, "CFBundleIdentifier": "org.jaspstats.jasp"}, f)
    return app


def test_mac_bundle_version_uses_full_version(tmp_path):
    app = _make_app(tmp_path)
    assert jasp.mac_bundle_version(app) == "0.99.0.0"


def test_detect_mac_in_home_applications(tmp_path, monkeypatch):
    _make_app(tmp_path, "0.98.1.0")
    monkeypatch.setattr(jasp, "mac_app_paths", lambda home: [tmp_path / "nowhere.app", home / "Applications" / "JASP.app"])
    j = jasp.detect_mac(tmp_path)
    assert j.found and j.flavour == "mac" and j.version == "0.98.1.0" and j.version_ok()
    assert j.stores[0].domain == "org.jasp-stats.JASP"
    assert j.plot_dirs == [tmp_path / "Library" / "Application Support" / "JASP" / "JASP" / "temp"]
    assert j.open_cmd[0] == "open"


def test_detect_mac_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(jasp, "mac_app_paths", lambda home: [])
    monkeypatch.setattr(jasp, "run", lambda cmd, timeout=20: None)
    assert not jasp.detect_mac(tmp_path).found
