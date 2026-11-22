"""The AI apps: Claude Code and Codex CLI. Finding, installing, sign-in and folder trust.

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
from dataclasses import dataclass
from pathlib import Path

import tomllib


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


# ---------------------------------------------------------------------------- Codex folder trust

def codex_home() -> Path:
    v = os.environ.get("CODEX_HOME")
    return Path(v) if v else Path.home() / ".codex"


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
    sep = "" if not config_text or config_text.endswith("\n\n") else ("\n" if config_text.endswith("\n") else "\n\n")
    return config_text + sep + trust_block(folder)


def trust_codex_folder(folder: Path) -> str:
    """Mark the folder as trusted for Codex. Returns 'added', 'already', 'untrusted' or 'skipped'."""
    cfg = codex_home() / "config.toml"
    text = cfg.read_text(encoding="utf-8") if cfg.is_file() else ""
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
    tmp = cfg.with_name("config.toml.full-fat-tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    os.replace(tmp, cfg)
    return "added"


def trust_block(folder: str) -> str:
    return f"[projects.{_toml_key(folder)}]\ntrust_level = \"trusted\"\n"


def untrust_codex_folder(folder: str) -> str:
    """Remove the trust entry Full Fat added, and nothing else. Returns 'removed', 'absent' or 'left'."""
    cfg = codex_home() / "config.toml"
    if not cfg.is_file():
        return "absent"
    text = cfg.read_text(encoding="utf-8")
    block = trust_block(folder)
    if block not in text:
        return "absent" if codex_trust_state(text, folder) is None else "left"
    i = text.rindex(block)
    new = text[:i].rstrip("\n") + ("\n" if text[:i].strip() else "") + text[i + len(block):]
    if codex_trust_state(new, folder) not in (None,):
        return "left"
    tmp = cfg.with_name("config.toml.full-fat-tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    os.replace(tmp, cfg)
    return "removed"


def launch_command(app: App, exe: str, intro: str) -> list[str]:
    return [exe, intro]
