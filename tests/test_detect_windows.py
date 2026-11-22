from pathlib import Path

from full_fat import jasp


class FakeReg:
    """Enough of winreg for the detection code. tree: {(root, path): {"keys": [...], "values": {...}}}"""
    HKEY_CURRENT_USER = "HKCU"
    HKEY_LOCAL_MACHINE = "HKLM"

    def __init__(self, tree):
        self.tree = {(r, p.lower()): v for (r, p), v in tree.items()}

    class _Key:
        def __init__(self, node):
            self.node = node

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def OpenKey(self, root, path):
        node = self.tree.get((root, path.lower()))
        if node is None:
            raise OSError("no key")
        return self._Key(node)

    def EnumKey(self, key, i):
        keys = key.node.get("keys", [])
        if i >= len(keys):
            raise OSError("no more")
        return keys[i]

    def QueryValueEx(self, key, name):
        if name not in key.node.get("values", {}):
            raise OSError("no value")
        return key.node["values"][name], 1


ENV = {"APPDATA": r"C:\Users\me\AppData\Roaming", "LOCALAPPDATA": r"C:\Users\me\AppData\Local"}


def test_msix_store_package():
    reg = FakeReg({("HKCU", jasp.APPMODEL): {"keys": [
        "Microsoft.Something_1.0.0.0_x64__abc",
        "45842JASP.JASP_0.98.1.0_x64__mmd5dc4ns5ztr",
        "45842JASP.JASP_0.98.8.0_x64__mmd5dc4ns5ztr",
    ]}})
    assert jasp.msix_packages(reg)[0] == ("45842JASP.JASP", "0.98.8.0", "45842JASP.JASP_mmd5dc4ns5ztr")
    j = jasp.detect_windows(ENV, reg=reg, home=Path(r"C:\Users\me"))
    assert j.flavour == "msix" and j.version == "0.98.8.0"
    first = str(j.stores[0].path).replace("\\", "/")
    assert first.endswith("Packages/45842JASP.JASP_mmd5dc4ns5ztr/LocalCache/Roaming/JASP-Stats-MSIX/JASPDesktop.ini")
    assert str(j.plot_dirs[0]).replace("\\", "/").endswith(
        "LocalCache/Local/JASP-Stats-MSIX/JASPDesktop/temp")
    assert j.open_cmd == ["explorer.exe", r"shell:AppsFolder\45842JASP.JASP_mmd5dc4ns5ztr!JASP"]


def test_msi_install_and_policy():
    sub = jasp.UNINSTALL + r"\{GUID-1}"
    reg = FakeReg({
        ("HKLM", jasp.UNINSTALL): {"keys": ["{GUID-1}", "Other"]},
        ("HKLM", sub): {"values": {"DisplayName": "JASP", "DisplayVersion": "0.99.0.0",
                                    "InstallLocation": r"C:\Program Files\JASP"}},
        ("HKLM", jasp.UNINSTALL + r"\Other"): {"values": {"DisplayName": "JASPer tools", "DisplayVersion": "1"}},
        ("HKCU", r"Software\Policies\JASP"): {"values": {"rpcServerEnabled": "false"}},
    })
    assert jasp.msi_installs(reg) == [("0.99.0.0", r"C:\Program Files\JASP")]
    j = jasp.detect_windows(ENV, reg=reg, home=Path(r"C:\Users\me"))
    assert j.flavour == "msi" and j.version == "0.99.0.0"
    assert str(j.stores[0].path).replace("\\", "/").endswith("Roaming/JASP/JASP.ini")
    assert str(j.plot_dirs[0]).replace("\\", "/").endswith("Local/JASP/JASP/temp")
    assert any("organisation" in n for n in j.notes)


def test_nothing_installed(tmp_path):
    j = jasp.detect_windows({"APPDATA": str(tmp_path), "LOCALAPPDATA": str(tmp_path)}, reg=FakeReg({}), home=tmp_path)
    assert not j.found


def test_zip_copy_found_by_settings(tmp_path):
    (tmp_path / "JASP").mkdir()
    (tmp_path / "JASP" / "JASP.ini").write_text("[General]\n")
    j = jasp.detect_windows({"APPDATA": str(tmp_path), "LOCALAPPDATA": str(tmp_path)}, reg=FakeReg({}), home=tmp_path)
    assert j.found and j.flavour == "zip" and j.version is None


def test_tasklist():
    out = '"System","4","Services","0","1,234 K"\n"JASPDesktop.exe","9000","Console","1","300,000 K"\n'
    assert jasp.parse_tasklist(out)
    assert not jasp.parse_tasklist('"notepad.exe","1","Console","1","1 K"\n')
    assert not jasp.parse_tasklist("INFO: No tasks are running which match the specified criteria.")
