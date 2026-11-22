"""Full Fat's own settings folder: remembered answers and backups of JASP's settings."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def config_dir() -> Path:
    env = os.environ.get("FULL_FAT_CONFIG")
    if env:
        return Path(env)
    if sys.platform.startswith("win"):
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "full-fat"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "full-fat"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    return (Path(xdg) if xdg and os.path.isabs(xdg) else Path.home() / ".config") / "full-fat"


def backup_dir() -> Path:
    return config_dir() / "jasp-settings-backup"


def state_file() -> Path:
    return config_dir() / "state.json"


def load() -> dict:
    try:
        data = json.loads(state_file().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data: dict) -> None:
    p = state_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    old = load()
    old.update(data)  # keep fields this version doesn't know about
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(old, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def default_workspace() -> Path:
    return Path.home() / "JASP-AI"
