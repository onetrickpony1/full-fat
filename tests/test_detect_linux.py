import subprocess
from pathlib import Path

from full_fat import jasp

FLATPAK_INFO = """
JASP - A complete statistical package

          ID: org.jaspstats.JASP
         Ref: app/org.jaspstats.JASP/x86_64/stable
        Arch: x86_64
      Branch: stable
     Version: 0.98.1
     License: AGPL-3.0-or-later
"""


def test_flatpak(tmp_path):
    runner = lambda cmd, timeout=20: subprocess.CompletedProcess(cmd, 0, stdout=FLATPAK_INFO, stderr="")
    j = jasp.detect_linux(tmp_path, {}, runner=runner, which=lambda n: None)
    assert j.flavour == "flatpak" and j.version == "0.98.1"
    assert j.stores[0].path == tmp_path / ".var/app/org.jaspstats.JASP/config/JASP/JASP.conf"
    assert j.plot_dirs == [tmp_path / ".var/app/org.jaspstats.JASP/data/JASP/JASP/temp"]
    assert j.open_cmd == ["flatpak", "run", "org.jaspstats.JASP"]


def test_native_uses_xdg(tmp_path):
    runner = lambda cmd, timeout=20: subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")
    j = jasp.detect_linux(tmp_path, {"XDG_CONFIG_HOME": str(tmp_path / "cfg")}, runner=runner,
                          which=lambda n: "/usr/bin/jasp" if n == "jasp" else None)
    assert j.flavour == "linux" and j.version is None and j.version_ok() is None
    assert j.stores[0].path == tmp_path / "cfg" / "JASP" / "JASP.conf"


def test_not_found(tmp_path):
    j = jasp.detect_linux(tmp_path, {}, runner=lambda c, timeout=20: None, which=lambda n: None)
    assert not j.found


def test_version_ok():
    assert jasp.Jasp(version="0.97.1").version_ok() is False
    assert jasp.Jasp(version="0.98.0").version_ok() is True
    assert jasp.Jasp(version="1.0.0.0").version_ok() is True


def test_settings_file_override(tmp_path):
    j = jasp.detect(str(tmp_path / "JASP.conf"), "0.99.0")
    assert j.found and j.flavour == "custom" and j.version == "0.99.0"
    assert j.stores[0].path == tmp_path / "JASP.conf"


def test_host_port_from_settings(tmp_path):
    conf = tmp_path / "JASP.conf"
    conf.write_text("[General]\nrpcServerIp=127.0.0.2\nrpcServerPort=5000\n")
    j = jasp.detect(str(conf), "0.99.0")
    assert j.host_port() == ("127.0.0.2", 5000)
    conf.write_text("[General]\nrpcServerPort=bad\n")
    assert j.host_port() == ("127.0.0.1", 48164)
