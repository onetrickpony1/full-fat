"""The AI apps: Claude Code and Codex CLI (finding, installing, sign-in, folder trust) and the ChatGPT desktop app.

Install commands are the providers' official ones (checked 2026-11-22):
- Claude Code, https://code.claude.com/docs/en/setup: `curl -fsSL https://claude.ai/install.sh | bash`
  (macOS, Linux) and `irm https://claude.ai/install.ps1 | iex` (Windows). Installs to ~/.local/bin/claude.
  Git for Windows is optional (without it Claude Code uses PowerShell).
- Codex CLI, https://developers.openai.com/codex/cli: `curl -fsSL https://chatgpt.com/codex/install.sh | sh`
  (macOS, Linux; installs to ~/.local/bin/codex). Windows: https://chatgpt.com/codex/install.ps1 , the
  same installer for PowerShell, installs to %LOCALAPPDATA%\\Programs\\OpenAI\\Codex\\bin. Neither needs
  npm or Homebrew. CODEX_NON_INTERACTIVE=1 skips its "Start Codex now?" question.
Sign-in: `claude auth status` and `codex login status` exit with 0 when signed in.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import tomllib

from . import workspace


@dataclass(frozen=True)
class App:
    key: str
    name: str        # what the user pays for
    product: str     # the app's name
    exe: str
    status: tuple[str, ...]
    login: tuple[str, ...]
    install_posix: str
    install_windows: str

    def candidates(self) -> list[Path]:
        home = Path.home()
        if os.name == "nt":
            local = Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local")
            out = [home / ".local" / "bin" / f"{self.exe}.exe"]
            if self.key == "codex":
                out.append(local / "Programs" / "OpenAI" / "Codex" / "bin" / "codex.exe")
            return out
        return [home / ".local" / "bin" / self.exe, Path("/opt/homebrew/bin") / self.exe,
                Path("/usr/local/bin") / self.exe]


CLAUDE = App("claude", "Claude (Pro or Max)", "Claude Code", "claude", ("auth", "status"),
             ("auth", "login", "--claudeai"),
             "curl -fsSL https://claude.ai/install.sh | bash",
             "irm https://claude.ai/install.ps1 | iex")
CODEX = App("codex", "ChatGPT (Plus or Pro)", "Codex", "codex", ("login", "status"), ("login",),
            "curl -fsSL https://chatgpt.com/codex/install.sh | sh",
            "irm https://chatgpt.com/codex/install.ps1 | iex")
APPS = {"claude": CLAUDE, "codex": CODEX}


def find(app: App) -> str | None:
    env = os.environ.get(f"FULL_FAT_{app.key.upper()}")
    if env:
        return env if Path(env).is_file() else None
    exe = shutil.which(app.exe)
    if exe:
        return exe
    return next((str(c) for c in app.candidates() if c.is_file()), None)


def install(app: App) -> bool:
    """Run the provider's official installer in this window."""
    env = dict(os.environ, CODEX_NON_INTERACTIVE="1")
    if os.name == "nt":
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", app.install_windows]
    else:
        shell = "/bin/bash" if "| bash" in app.install_posix else "/bin/sh"
        cmd = [shell, "-c", app.install_posix]
    try:
        r = subprocess.run(cmd, env=env)
    except OSError:
        return False
    return r.returncode == 0 and find(app) is not None


def signed_in(app: App, exe: str) -> bool | None:
    try:
        r = subprocess.run([exe, *app.status], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.returncode == 0


def sign_in(app: App, exe: str) -> bool:
    try:
        subprocess.run([exe, *app.login])
    except OSError:
        return False
    return bool(signed_in(app, exe))


# Words in Codex's error when it can't load a settings file (an older Codex refuses keys it doesn't know)
CODEX_CONFIG_ERROR = ("config", "toml", "parse", "invalid", "unknown field", "unknown variant", "transport")


def codex_folder_problem(exe: str, folder: Path, timeout: float = 30) -> str | None:
    """Does this Codex CLI load the chat folder's settings? The folder's .codex/config.toml uses keys that only
    newer Codex versions know (features.apps, plugins, node_repl switched off; checked with Codex 0.169), and
    Codex refuses the whole file when it can't read it. `codex mcp list` in the folder loads the settings
    without starting anything. Returns Codex's error when it refused them, None when they load or when the
    answer is unclear (no Codex, a timeout, another error)."""
    try:
        r = subprocess.run([exe, "mcp", "list"], cwd=folder, capture_output=True, text=True, timeout=timeout,
                           stdin=subprocess.DEVNULL, errors="replace")
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode == 0:
        return None
    text = ((r.stderr or "") + "\n" + (r.stdout or "")).strip()
    return text[-500:] if any(w in text.lower() for w in CODEX_CONFIG_ERROR) else None


# ---------------------------------------------------------------------------- Codex folder trust

def codex_home() -> Path:
    v = os.environ.get("CODEX_HOME")
    return Path(v) if v else Path.home() / ".codex"


def read_keep(path: Path) -> str:
    """A text file exactly as it is, line endings included."""
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def write_keep(path: Path, text: str) -> None:
    """Replace a settings file safely: through a symlink to the real file, keeping its permissions."""
    real = Path(os.path.realpath(path))
    real.parent.mkdir(parents=True, exist_ok=True)
    tmp = real.with_name(real.name + ".full-fat-tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    if real.exists():
        shutil.copymode(real, tmp)
    os.replace(tmp, real)


def _newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def _toml_key(path: str) -> str:
    if "'" not in path:
        return f"'{path}'"
    return '"' + path.replace("\\", "\\\\").replace('"', '\\"') + '"'


def codex_trust_state(config_text: str, folder: str) -> str | None:
    """'trusted', 'untrusted', None (no entry), or 'unreadable' (the file doesn't parse)."""
    try:
        data = tomllib.loads(config_text)
    except tomllib.TOMLDecodeError:
        return "unreadable"
    projects = data.get("projects") or {}
    want = os.path.normcase(os.path.normpath(folder))
    for k, v in projects.items():
        if os.path.normcase(os.path.normpath(k)) == want and isinstance(v, dict):
            return str(v.get("trust_level") or "") or None
    return None


def codex_trust_text(config_text: str, folder: str) -> str | None:
    """The config with a trust entry for folder appended, or None when nothing should change.

    Only appends a new [projects."<folder>"] table: other projects' entries and everything else stay
    byte for byte. Codex's own documented setting: projects.<path>.trust_level = "trusted".
    """
    state = codex_trust_state(config_text, folder)
    if state is not None:
        return None
    nl = _newline(config_text)
    if not config_text or config_text.endswith(nl + nl):
        sep = ""
    else:
        sep = nl if config_text.endswith(nl) else nl + nl
    return config_text + sep + trust_block(folder, nl)


def trust_codex_folder(folder: Path) -> str:
    """Mark the folder as trusted for Codex. Returns 'added', 'already', 'untrusted' or 'skipped'."""
    cfg = codex_home() / "config.toml"
    text = read_keep(cfg) if cfg.is_file() else ""
    state = codex_trust_state(text, str(folder))
    if state == "trusted":
        return "already"
    if state == "untrusted":
        return "untrusted"
    if state == "unreadable":
        return "skipped"
    new = codex_trust_text(text, str(folder))
    if new is None:
        return "already"
    try:  # never write a file Codex can't read
        if codex_trust_state(new, str(folder)) != "trusted":
            return "skipped"
    except Exception:  # noqa: BLE001
        return "skipped"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    backup = cfg.with_name("config.toml.before-full-fat")
    if cfg.is_file() and not backup.exists():
        shutil.copy2(cfg, backup)
    write_keep(cfg, new)
    return "added"


def trust_block(folder: str, nl: str = "\n") -> str:
    return f"[projects.{_toml_key(folder)}]{nl}trust_level = \"trusted\"{nl}"


def untrust_codex_folder(folder: str) -> str:
    """Remove the trust entry Full Fat added, and nothing else. Returns 'removed', 'absent' or 'left'."""
    cfg = codex_home() / "config.toml"
    if not cfg.is_file():
        return "absent"
    text = read_keep(cfg)
    nl = _newline(text)
    block = trust_block(folder, nl)
    if block not in text:
        return "absent" if codex_trust_state(text, folder) is None else "left"
    i = text.rindex(block)
    before, after = text[:i], text[i + len(block):]
    # Keys written below the block belong to its table. Removing the header would move them into the table
    # above, so the block is only removed when a new table or the end of the file follows it.
    rest = [ln.strip() for ln in after.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if rest and not rest[0].startswith("["):
        return "left"
    new = before.rstrip("\r\n") + (nl if before.strip() else "") + after
    try:
        if codex_trust_state(new, folder) is not None or tomllib.loads(new) != _without(tomllib.loads(text), folder):
            return "left"
    except tomllib.TOMLDecodeError:
        return "left"
    write_keep(cfg, new)
    return "removed"


def _without(data: dict, folder: str) -> dict:
    out = dict(data)
    projects = {k: v for k, v in (out.get("projects") or {}).items() if k != folder}
    if projects:
        out["projects"] = projects
    else:
        out.pop("projects", None)
    return out


# ---------------------------------------------------------------------------- starting the chat

def claude_settings_files(folder: Path) -> list[Path]:
    """Claude Code's settings that can choose the model: the user's own, then the chat folder's."""
    user = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    return [user / "settings.json", folder / ".claude" / "settings.json", folder / ".claude" / "settings.local.json"]


def _json_keys(paths: list[Path]) -> set[str]:
    keys: set[str] = set()
    for p in paths:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            keys |= set(data)
    return keys


def _toml_keys(paths: list[Path]) -> set[str]:
    keys: set[str] = set()
    for p in paths:
        try:
            keys |= set(tomllib.loads(p.read_text(encoding="utf-8")))
        except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError):
            continue
    return keys


def launch_command(app: App, exe: str, intro: str, folder: Path | None = None,
                   remote_name: str | None = None) -> list[str]:
    """The chat app's command. It starts on the top model at high effort, unless a settings file already
    chooses the model or effort (for example after /model or /effort saved a default): then that one wins.
    remote_name (Claude Code only): also open the chat on claude.ai/code under that name (Remote Control)."""
    folder = Path(folder) if folder else Path.cwd()
    cmd = [exe]
    if app.key == "claude":
        have = _json_keys(claude_settings_files(folder))
        if "model" not in have:
            cmd += ["--model", workspace.CLAUDE_MODEL]
        if "effortLevel" not in have:
            cmd += ["--effort", workspace.CLAUDE_EFFORT]
        if remote_name:
            cmd += ["--remote-control", remote_name]
    else:
        have = _toml_keys([codex_home() / "config.toml", folder / ".codex" / "config.toml"])
        if "model" not in have:
            cmd += ["-m", workspace.CODEX_MODEL]
        if "model_reasoning_effort" not in have:
            cmd += ["-c", f'model_reasoning_effort="{workspace.CODEX_EFFORT}"']
    return cmd + [intro]


# ---------------------------------------------------------------------------- the ChatGPT desktop app
#
# The ChatGPT desktop app (macOS, Windows, Linux) has a ChatGPT side and a Codex side. Only the Codex side uses the
# chat folder's .codex/config.toml and AGENTS.md (checked with chatgpt-bin 26.1111 and its bundled Codex 0.169 on
# Linux). The app keeps Codex's codex:// link for compatibility; codex://threads/new opens a new chat, `path` (an
# absolute folder) is the folder it works in and `prompt` the first message
# (https://learn.chatgpt.com/docs/reference/commands). `mode=codex` opens it on the Codex side.

DESKTOP_APP = "the ChatGPT app"
MAC_APP_DIRS = ("/Applications", "~/Applications")
MAC_APP_NAMES = ("ChatGPT.app", "Codex.app")


def deep_link(folder: Path, prompt: str) -> str:
    """The link that opens a new chat on the app's Codex side in folder, with prompt as its first message.
    Everything is percent-encoded, so a space ("Full Fat") becomes %20 and never a +."""
    from urllib.parse import quote  # noqa: PLC0415
    params = {"path": str(folder), "mode": "codex", "prompt": prompt}
    return "codex://threads/new?" + "&".join(f"{k}={quote(v, safe='')}" for k, v in params.items())


def _mac_bundle_has_codex_link(bundle: Path) -> bool:
    import plistlib  # noqa: PLC0415
    try:
        with open(bundle / "Contents" / "Info.plist", "rb") as f:
            info = plistlib.load(f)
    except (OSError, ValueError, plistlib.InvalidFileException):
        return False
    for t in info.get("CFBundleURLTypes") or []:
        if isinstance(t, dict) and "codex" in [str(s).lower() for s in t.get("CFBundleURLSchemes") or []]:
            return True
    return False


def _mac_handler() -> bool:
    """Ask macOS which app opens codex:// links (the app may live somewhere other than /Applications)."""
    script = ('ObjC.import("AppKit"); var u = $.NSWorkspace.sharedWorkspace.URLForApplicationToOpenURL('
              '$.NSURL.URLWithString("codex://threads/new")); u.isNil() ? "" : u.path.js')
    try:
        r = subprocess.run(["osascript", "-l", "JavaScript", "-e", script], capture_output=True, text=True,
                           timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and r.stdout.strip().endswith(".app")


def _linux_handler() -> bool:
    try:
        r = subprocess.run(["xdg-mime", "query", "default", "x-scheme-handler/codex"], capture_output=True,
                           text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and bool(r.stdout.strip())


def _windows_handler() -> bool:
    try:
        import winreg  # noqa: PLC0415
    except ImportError:
        return False
    for root, key in ((winreg.HKEY_CURRENT_USER, r"Software\Classes\codex"), (winreg.HKEY_CLASSES_ROOT, "codex")):
        try:
            with winreg.OpenKey(root, key) as k:
                winreg.QueryValueEx(k, "URL Protocol")
                return True
        except OSError:
            continue
    return False


def desktop_app_found(platform: str | None = None) -> bool:
    """Is a ChatGPT desktop app installed that opens codex:// links? FULL_FAT_CHATGPT_APP=none says no (tests,
    CI, or to keep the chat in the Terminal), any other value yes."""
    env = os.environ.get("FULL_FAT_CHATGPT_APP")
    if env:
        return env.lower() not in ("none", "0", "no")
    platform = platform or sys.platform
    if platform == "darwin":
        bundles = [Path(d).expanduser() / n for d in MAC_APP_DIRS for n in MAC_APP_NAMES]
        return any(_mac_bundle_has_codex_link(b) for b in bundles if b.is_dir()) or _mac_handler()
    if platform.startswith("win"):
        return _windows_handler()
    return _linux_handler()


def open_desktop_app(url: str, platform: str | None = None, wait: float = 20) -> bool:
    """Hand the codex:// link to the system, which opens the app. False when that fails (no app takes it)."""
    return open_link(url, platform, wait)


def open_link(url: str, platform: str | None = None, wait: float = 20) -> bool:
    """Hand a link to the system, which opens it in the app for it (the browser for https). False when that
    fails (no app takes the link)."""
    platform = platform or sys.platform
    try:
        if platform.startswith("win"):
            os.startfile(url)  # type: ignore[attr-defined]  # raises OSError when no app takes the link
            return True
        cmd = ["open", url] if platform == "darwin" else ["xdg-open", url]
        # its own session, so closing the Terminal window afterwards can't stop the app
        p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
    except (OSError, AttributeError):
        return False
    try:
        return p.wait(timeout=wait) == 0
    except subprocess.TimeoutExpired:
        return True  # still handing the link over (some systems wait for the app): it was accepted
