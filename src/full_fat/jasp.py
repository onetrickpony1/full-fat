"""Find JASP, its version, its settings and its plot folder, on Linux, Windows and macOS.

Everything here comes from JASP's own source (jasp-stats/jasp-desktop, checked at v0.98.0, v0.98.1,
v0.98.8, v0.99.0 and development on 2026-11-22):

- Desktop/main.cpp (v0.98.1 lines 424-440, v0.99.0 lines 284-300): on Windows the Qt organisation and
  application are "JASP" / "JASP", or "JASP-Stats-MSIX" / "JASPDesktop" for the Microsoft Store (MSIX)
  package, and settings use QSettings::IniFormat. On Linux and macOS they are "JASP" / "JASP" with the
  domain "jasp-stats.org" and the native format.
  So the settings are:
    Linux:   $XDG_CONFIG_HOME/JASP/JASP.conf (INI). Flatpak: ~/.var/app/org.jaspstats.JASP/config/JASP/JASP.conf
    Windows: %APPDATA%\\JASP\\JASP.ini (INI). MSIX: %APPDATA%\\JASP-Stats-MSIX\\JASPDesktop.ini, which
             Windows redirects to %LOCALAPPDATA%\\Packages\\<package family>\\LocalCache\\Roaming\\...
    macOS:   the preferences domain org.jasp-stats.JASP (Qt reverses the organisation domain and adds the
             application name), in ~/Library/Preferences/org.jasp-stats.JASP.plist. Edited with `defaults`.
- Desktop/utilities/settings.cpp (v0.98.1 lines 156-158): keys rpcServerEnabled (default false),
  rpcServerIp ("127.0.0.1") and rpcServerPort (48164). Lines 176-200: on Windows, group policy under
  HKLM/HKCU\\Software\\Policies\\JASP wins over the user's file, and the old registry key
  HKCU\\Software\\JASP\\JASP is read only when the INI file lacks the key. Development adds forced.json and
  macOS managed preferences above the user's settings.
- Common/dirs.cpp (v0.98.1 lines 52-104) and QMLComponents/utilities/appdirs.cpp (lines 174-180): plots
  and other results go to <AppLocalDataLocation>/temp/, which is ~/.local/share/JASP/JASP/temp (Flatpak:
  ~/.var/app/org.jaspstats.JASP/data/JASP/JASP/temp), %LOCALAPPDATA%\\JASP\\JASP\\temp (MSIX:
  %LOCALAPPDATA%\\Packages\\<family>\\LocalCache\\Local\\JASP-Stats-MSIX\\JASPDesktop\\temp) and
  ~/Library/Application Support/JASP/JASP/temp.
- Desktop/CMakeLists.txt (v0.99.0 line 103): the Windows program is JASPDesktop.exe.
- Tools/macOS/Info.plist.in: CFBundleExecutable JASP, CFBundleVersion is the full version and
  CFBundleShortVersionString only major.minor.
- Tools/windows/msix/AppxManifest-*.xml.in: package names 45842JASP.JASP (Store), 45842JASP.JASPBeta,
  JASP.STANDALONE and JASP.SIDELOAD.NIGHTLY; application id JASP.
"""

from __future__ import annotations

import json
import os
import plistlib
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from .prompts import parse_version

MIN_VERSION = (0, 98, 0)
DOWNLOAD_URL = "https://jasp-stats.org/download/"
FLATPAK_ID = "org.jaspstats.JASP"
MAC_DOMAIN = "org.jasp-stats.JASP"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 48164
KEY_ENABLED = "rpcServerEnabled"
MSIX_NAMES = ("45842JASP.JASP", "45842JASP.JASPBeta", "JASP.STANDALONE", "JASP.SIDELOAD.NIGHTLY")
WINDOWS_EXES = ("JASPDesktop.exe", "JASP.exe")


def system() -> str:
    """'linux', 'windows' or 'mac'."""
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "mac"
    return "linux"


def run(cmd: list[str], timeout: float = 20) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None


# ---------------------------------------------------------------------------- Qt INI files

def _newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def _general_bounds(lines: list[str]) -> tuple[int, int] | None:
    """(header index, end index) of the [General] section, or None."""
    start = None
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            if start is not None:
                return start, i
            if s == "[General]":
                start = i
    return (start, len(lines)) if start is not None else None


def ini_get(text: str, key: str) -> str | None:
    lines = text.splitlines()
    b = _general_bounds(lines)
    # Qt writes top-level keys under [General]; keys before any section count too.
    ranges = []
    first_section = next((i for i, ln in enumerate(lines) if ln.strip().startswith("[")), len(lines))
    ranges.append((0, first_section))
    if b:
        ranges.append((b[0] + 1, b[1]))
    for lo, hi in ranges:
        for line in lines[lo:hi]:
            k, sep, v = line.partition("=")
            if sep and k.strip() == key:
                v = v.strip()
                if len(v) >= 2 and v[0] == v[-1] == '"':
                    v = v[1:-1]
                return v
    return None


def ini_set(text: str, key: str, value: str) -> str:
    """Set key=value in the [General] section, keeping everything else exactly as it was."""
    nl = _newline(text) if text else os.linesep if os.name == "nt" else "\n"
    lines = text.splitlines()
    b = _general_bounds(lines)
    if b:
        for i in range(b[0] + 1, b[1]):
            k, sep, _ = lines[i].partition("=")
            if sep and k.strip() == key:
                lines[i] = f"{key}={value}"
                return nl.join(lines) + nl
        # insert in sorted position among the keys, as Qt does, else at the end of the section
        insert = b[1]
        while insert > b[0] + 1 and not lines[insert - 1].strip():
            insert -= 1
        for i in range(b[0] + 1, insert):
            k, sep, _ = lines[i].partition("=")
            if sep and k.strip() > key:
                insert = i
                break
        lines.insert(insert, f"{key}={value}")
        return nl.join(lines) + nl
    head = ["[General]", f"{key}={value}"]
    if lines:
        head.append("")
    return nl.join(head + lines) + nl


def ini_remove(text: str, key: str) -> str:
    nl = _newline(text)
    lines = text.splitlines()
    b = _general_bounds(lines)
    if not b:
        return text
    keep = [ln for i, ln in enumerate(lines)
            if not (b[0] < i < b[1] and ln.partition("=")[1] and ln.partition("=")[0].strip() == key)]
    return nl.join(keep) + nl


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".full-fat-tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------- settings stores

@dataclass
class Store:
    """One place where JASP keeps its settings."""
    kind: str                 # "ini" or "defaults"
    label: str
    path: Path | None = None  # INI file
    domain: str | None = None  # macOS preferences domain

    def ident(self) -> str:
        return str(self.path) if self.kind == "ini" else f"defaults:{self.domain}"

    def exists(self) -> bool:
        if self.kind == "ini":
            return self.path is not None and self.path.is_file()
        plist = Path.home() / "Library" / "Preferences" / f"{self.domain}.plist"
        return plist.is_file()

    def get(self, key: str) -> str | None:
        if self.kind == "ini":
            try:
                return ini_get(self.path.read_text(encoding="utf-8", errors="replace"), key)
            except OSError:
                return None
        r = run(["defaults", "read", self.domain, key])
        if r is None or r.returncode != 0:
            return None
        v = r.stdout.strip()
        return {"1": "true", "0": "false"}.get(v, v)

    def enabled(self) -> bool:
        return (self.get(KEY_ENABLED) or "").lower() in ("true", "1")

    def backup(self, folder: Path) -> Path | None:
        """Copy the whole settings to the backup folder (once: the first copy is the original)."""
        folder.mkdir(parents=True, exist_ok=True)
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", self.ident()).strip("_")[-120:]
        if self.kind == "ini":
            dest = folder / (name + ".bak")
            if not dest.exists() and self.exists():
                shutil.copy2(self.path, dest)
            return dest if dest.exists() else None
        dest = folder / (name + ".plist")
        if not dest.exists() and self.exists():
            r = run(["defaults", "export", self.domain, str(dest)])
            if r is None or r.returncode != 0:
                return None
        return dest if dest.exists() else None

    def set(self, key: str, value: bool) -> None:
        if self.kind == "ini":
            text = self.path.read_text(encoding="utf-8") if self.exists() else ""
            _atomic_write(self.path, ini_set(text, key, "true" if value else "false"))
            return
        r = run(["defaults", "write", self.domain, key, "-bool", "true" if value else "false"])
        if r is None or r.returncode != 0:
            raise OSError(f"defaults write failed: {r.stderr if r else 'not found'}")

    def remove(self, key: str) -> None:
        if self.kind == "ini":
            if self.exists():
                _atomic_write(self.path, ini_remove(self.path.read_text(encoding="utf-8"), key))
            return
        run(["defaults", "delete", self.domain, key])

    def to_json(self) -> dict:
        return {"kind": self.kind, "label": self.label,
                "path": str(self.path) if self.path else None, "domain": self.domain}

    @staticmethod
    def from_json(d: dict) -> "Store":
        return Store(kind=d["kind"], label=d.get("label", ""),
                     path=Path(d["path"]) if d.get("path") else None, domain=d.get("domain"))


# ---------------------------------------------------------------------------- the JASP install

@dataclass
class Jasp:
    found: bool = False
    flavour: str = "unknown"   # flatpak, linux, msix, msi, zip, mac, custom
    version: str | None = None
    stores: list[Store] = field(default_factory=list)
    plot_dirs: list[Path] = field(default_factory=list)
    open_cmd: list[str] | None = None
    notes: list[str] = field(default_factory=list)

    def version_ok(self) -> bool | None:
        v = parse_version(self.version)
        return None if v is None else v >= MIN_VERSION

    def write_store(self) -> Store | None:
        """The store to switch on: the first one that exists, else the first candidate."""
        for s in self.stores:
            if s.exists():
                return s
        return self.stores[0] if self.stores else None

    def host_port(self) -> tuple[str, int]:
        s = self.write_store()
        host = (s.get("rpcServerIp") if s else None) or DEFAULT_HOST
        try:
            port = int((s.get("rpcServerPort") if s else None) or DEFAULT_PORT)
        except ValueError:
            port = DEFAULT_PORT
        return host, port

    def enabled(self) -> bool:
        s = self.write_store()
        return bool(s and s.enabled())  # not exists(): cfprefsd may not have written the plist yet


def _xdg(env: dict, name: str, default: Path) -> Path:
    v = env.get(name)
    return Path(v) if v and os.path.isabs(v) else default


def detect_linux(home: Path, env: dict, runner=run, which=shutil.which) -> Jasp:
    j = Jasp()
    r = runner(["flatpak", "info", FLATPAK_ID])
    if r is not None and r.returncode == 0:
        j.found, j.flavour = True, "flatpak"
        m = re.search(r"^\s*Version:\s*(\S+)", r.stdout, re.M)
        j.version = m.group(1) if m else None
        base = home / ".var" / "app" / FLATPAK_ID
        j.stores = [Store("ini", "JASP (Flatpak)", path=base / "config" / "JASP" / "JASP.conf")]
        j.plot_dirs = [base / "data" / "JASP" / "JASP" / "temp"]
        j.open_cmd = ["flatpak", "run", FLATPAK_ID]
        return j
    conf = _xdg(env, "XDG_CONFIG_HOME", home / ".config") / "JASP" / "JASP.conf"
    data = _xdg(env, "XDG_DATA_HOME", home / ".local" / "share") / "JASP" / "JASP"
    exe = which("jasp") or which("JASP")
    if exe or conf.is_file():
        j.found, j.flavour = True, "linux"
        j.stores = [Store("ini", "JASP", path=conf)]
        j.plot_dirs = [data / "temp"]
        j.open_cmd = [exe] if exe else None
    return j


def _winreg():
    import winreg  # noqa: PLC0415 (Windows only)
    return winreg


def _reg_subkeys(reg, root, path: str) -> list[str]:
    try:
        with reg.OpenKey(root, path) as k:
            out, i = [], 0
            while True:
                try:
                    out.append(reg.EnumKey(k, i))
                except OSError:
                    return out
                i += 1
    except OSError:
        return []


def _reg_value(reg, root, path: str, name: str):
    try:
        with reg.OpenKey(root, path) as k:
            return reg.QueryValueEx(k, name)[0]
    except OSError:
        return None


APPMODEL = r"Software\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel\Repository\Packages"
UNINSTALL = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
UNINSTALL_WOW = r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"


def msix_packages(reg) -> list[tuple[str, str, str]]:
    """[(package name, version, family name)] of installed JASP MSIX packages for this user.

    Package full names look like 45842JASP.JASP_0.98.1.0_x64__abcdef1234567; the family name is
    <name>_<publisher id>.
    """
    out = []
    for full in _reg_subkeys(reg, reg.HKEY_CURRENT_USER, APPMODEL):
        m = re.match(r"^([^_]+)_([\d.]+)_[^_]*_[^_]*_([^_]+)$", full)
        if m and m.group(1) in MSIX_NAMES:
            out.append((m.group(1), m.group(2), f"{m.group(1)}_{m.group(3)}"))
    out.sort(key=lambda t: (MSIX_NAMES.index(t[0]), [-x for x in parse_version(t[1]) or (0,)]))
    return out


def msi_installs(reg) -> list[tuple[str, str | None]]:
    """[(version, install folder)] from the uninstall entries whose name starts with JASP."""
    out = []
    for root in (reg.HKEY_LOCAL_MACHINE, reg.HKEY_CURRENT_USER):
        for base in (UNINSTALL, UNINSTALL_WOW):
            for sub in _reg_subkeys(reg, root, base):
                p = base + "\\" + sub
                name = _reg_value(reg, root, p, "DisplayName")
                if isinstance(name, str) and re.match(r"^JASP\b", name.strip()):
                    ver = _reg_value(reg, root, p, "DisplayVersion")
                    loc = _reg_value(reg, root, p, "InstallLocation")
                    if ver:
                        out.append((str(ver), str(loc) if loc else None))
    out.sort(key=lambda t: parse_version(t[0]) or (0,), reverse=True)
    return out


def windows_policy(reg) -> str | None:
    """The value an administrator forces for rpcServerEnabled, if any (settings.cpp v0.98.1 lines 179-189)."""
    for root in (reg.HKEY_LOCAL_MACHINE, reg.HKEY_CURRENT_USER):
        v = _reg_value(reg, root, r"Software\Policies\JASP", KEY_ENABLED)
        if v is not None:
            return str(v).lower()
    return None


def detect_windows(env: dict, reg=None, home: Path | None = None) -> Jasp:
    reg = reg or _winreg()
    home = home or Path.home()
    appdata = Path(env.get("APPDATA") or home / "AppData" / "Roaming")
    local = Path(env.get("LOCALAPPDATA") or home / "AppData" / "Local")
    j = Jasp()
    pkgs = msix_packages(reg)
    msis = msi_installs(reg)
    if pkgs:
        name, ver, family = pkgs[0]
        j.found, j.flavour, j.version = True, "msix", ver
        cache = local / "Packages" / family / "LocalCache"
        j.stores = [
            Store("ini", "JASP (Microsoft Store)", path=cache / "Roaming" / "JASP-Stats-MSIX" / "JASPDesktop.ini"),
            Store("ini", "JASP (Microsoft Store, unredirected)", path=appdata / "JASP-Stats-MSIX" / "JASPDesktop.ini"),
        ]
        j.plot_dirs = [cache / "Local" / "JASP-Stats-MSIX" / "JASPDesktop" / "temp",
                       local / "JASP-Stats-MSIX" / "JASPDesktop" / "temp"]
        j.open_cmd = ["explorer.exe", f"shell:AppsFolder\\{family}!JASP"]
    if msis:
        ver, loc = msis[0]
        if not j.found or (parse_version(ver) or (0,)) > (parse_version(j.version) or (0,)):
            # The installed (MSI) JASP uses %APPDATA%\JASP\JASP.ini
            j.found, j.flavour, j.version = True, "msi", ver
            j.stores = [Store("ini", "JASP", path=appdata / "JASP" / "JASP.ini")] + j.stores
            j.plot_dirs = [local / "JASP" / "JASP" / "temp"] + j.plot_dirs
            exe = next((Path(loc) / n for n in WINDOWS_EXES if loc and (Path(loc) / n).is_file()), None)
            j.open_cmd = [str(exe)] if exe else j.open_cmd
    if not j.found and (appdata / "JASP" / "JASP.ini").is_file():
        # A ZIP copy, or one we can't see in the registry.
        j.found, j.flavour = True, "zip"
        j.stores = [Store("ini", "JASP", path=appdata / "JASP" / "JASP.ini")]
        j.plot_dirs = [local / "JASP" / "JASP" / "temp"]
    if j.found:
        pol = windows_policy(reg)
        if pol is not None and pol not in ("true", "1"):
            j.notes.append("Your organisation's Windows settings keep the JASP connection switched off. "
                           "Ask whoever manages this computer to allow it.")
    return j


def mac_app_paths(home: Path) -> list[Path]:
    return [Path("/Applications/JASP.app"), home / "Applications" / "JASP.app"]


def mac_bundle_version(app: Path) -> str | None:
    try:
        with open(app / "Contents" / "Info.plist", "rb") as f:
            info = plistlib.load(f)
    except (OSError, plistlib.InvalidFileException, ValueError):
        return None
    return str(info.get("CFBundleVersion") or info.get("CFBundleShortVersionString") or "") or None


def detect_mac(home: Path) -> Jasp:
    j = Jasp()
    app = next((p for p in mac_app_paths(home) if p.is_dir()), None)
    if app is None:
        # Spotlight finds it anywhere else
        r = run(["mdfind", "kMDItemCFBundleIdentifier == 'org.jaspstats.jasp'"])
        hits = [Path(x) for x in (r.stdout.splitlines() if r and r.returncode == 0 else []) if x.endswith(".app")]
        app = hits[0] if hits else None
    prefs = home / "Library" / "Preferences" / f"{MAC_DOMAIN}.plist"
    if app or prefs.is_file():
        j.found, j.flavour = True, "mac"
        j.version = mac_bundle_version(app) if app else None
        j.stores = [Store("defaults", "JASP", domain=MAC_DOMAIN)]
        j.plot_dirs = [home / "Library" / "Application Support" / "JASP" / "JASP" / "temp"]
        j.open_cmd = ["open", str(app)] if app else ["open", "-a", "JASP"]
    return j


def detect(settings_file: str | None = None, version: str | None = None) -> Jasp:
    """Find JASP on this computer. settings_file points at a stand-in INI file (for tests and CI)."""
    home = Path.home()
    if settings_file:
        p = Path(settings_file).expanduser()
        j = Jasp(found=True, flavour="custom", stores=[Store("ini", "JASP", path=p)],
                 plot_dirs=[p.parent / "temp"])
        osj = _detect_os(home)
        j.open_cmd = osj.open_cmd
        j.version = version or osj.version
        return j
    j = _detect_os(home)
    if version:
        j.version = version
    return j


def _detect_os(home: Path) -> Jasp:
    s = system()
    if s == "windows":
        return detect_windows(dict(os.environ), home=home)
    if s == "mac":
        return detect_mac(home)
    return detect_linux(home, dict(os.environ))


# ---------------------------------------------------------------------------- running and reachable

def parse_tasklist(csv_text: str) -> bool:
    names = {n.lower() for n in WINDOWS_EXES}
    for line in csv_text.splitlines():
        first = line.split(",")[0].strip().strip('"').lower()
        if first in names:
            return True
    return False


def running() -> bool:
    """Is JASP open?"""
    s = system()
    if s == "windows":
        r = run(["tasklist", "/FO", "CSV", "/NH"])
        return bool(r and parse_tasklist(r.stdout))
    if s == "mac":
        r = run(["pgrep", "-x", "JASP"])
        return bool(r and r.returncode == 0)
    proc = Path("/proc")
    try:
        for d in proc.iterdir():
            if d.name.isdigit():
                try:
                    if (d / "comm").read_text().strip() in ("JASP", "jasp"):
                        return True
                except OSError:
                    continue
    except OSError:
        r = run(["pgrep", "-x", "JASP"])
        return bool(r and r.returncode == 0)
    return False


def ping(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = 3) -> bool:
    """Does JASP answer on its connection? (JSON-RPC ping, as jasp-mcp does.)"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except OSError:
        return False
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}}).encode()
    req = urllib.request.Request(f"http://{host}:{port}/rpc", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        return "result" in data
    except (OSError, ValueError):
        return False


def open_jasp(j: Jasp) -> bool:
    if not j.open_cmd:
        return False
    try:
        kw = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "stdin": subprocess.DEVNULL}
        if os.name == "nt":
            kw["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        else:
            kw["start_new_session"] = True
        subprocess.Popen(j.open_cmd, **kw)
        return True
    except OSError:
        return False


def wait_closed(poll: float = 2.0, timeout: float | None = None, is_running=running) -> bool:
    start = time.monotonic()
    while is_running():
        if timeout is not None and time.monotonic() - start > timeout:
            return False
        time.sleep(poll)
    return True
