"""Copies of JASP's plot images in the chat folder, so the browser can show them.

JASP writes each plot as a PNG file below its temp folder (jasp.Jasp.plot_dirs). In a Claude chat that is also
open at claude.ai/code, the browser opens only files inside the folder the chat runs in: a link to JASP's own
file shows "Couldn't load this file", and a link inside the folder that points elsewhere (a symlink) does nothing
(checked with Claude Code 2.1.330 on 2026-11-23). So while such a chat runs, Full Fat copies every PNG below
JASP's temp folder to plots/ in the chat folder, at the same path below it: <temp>/a/b.png becomes plots/a/b.png.
The assistant's instructions (templates/environment.md) say to link to the copy.

Only Full Fat copies; the chat itself still can't write files. Never a symlink, never over a file Full Fat did
not copy. plots/.full-fat-plots.json lists the copies with their hashes, so `full-fat uninstall` deletes only
those that are unchanged, as with the other files Full Fat writes. A new chat never deletes them: an earlier or
still running chat may link to them. A copy that went missing is made again.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

FOLDER = "plots"
INDEX = ".full-fat-plots.json"
MAX_BYTES = 50 * 1024 * 1024  # a plot is far smaller; anything bigger is not copied


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_new(path: Path, data: bytes) -> None:
    """Write data to a new file at path: never through a link, never into a file that is already there. A
    regular file left at path (an interrupted copy) is replaced; a link there is refused (OSError)."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    if path.is_symlink():
        raise OSError(f"{path} is a link")
    if path.exists():
        if not path.is_file():
            raise OSError(f"{path} is not a file")
        path.unlink()
    fd = os.open(path, flags, 0o644)
    with os.fdopen(fd, "wb") as f:
        f.write(data)


def _inside(path: Path, root: Path) -> bool:
    try:
        return path.resolve().is_relative_to(root.resolve())
    except OSError:
        return False


class Copier:
    def __init__(self, sources: list[Path], folder: Path):
        self.sources = [Path(s) for s in sources]
        self.folder = Path(folder)
        self.dest = self.folder / FOLDER
        self.seen: dict[Path, tuple[int, int]] = {}
        self.index = self._load()

    def _load(self) -> dict[str, str]:
        try:
            data = json.loads((self.dest / INDEX).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)} \
            if isinstance(data, dict) else {}

    def _save(self) -> None:
        tmp = self.dest / (INDEX + ".tmp")
        _write_new(tmp, (json.dumps(self.index, indent=1, sort_keys=True) + "\n").encode("utf-8"))
        os.replace(tmp, self.dest / INDEX)

    def _safe_dest(self) -> bool:
        """plots/ is a real folder inside the chat folder (made if missing), not a link to somewhere else."""
        if self.dest.is_symlink() or not self.folder.is_dir():
            return False
        self.dest.mkdir(exist_ok=True)
        return self.dest.is_dir() and _inside(self.dest, self.folder)

    def sync(self) -> list[str]:
        """Copy new and changed plots. Returns the paths copied (relative to plots/, with /)."""
        copied: list[str] = []
        for root in self.sources:
            if not root.is_dir():
                continue
            try:
                found = list(root.rglob("*.png"))
            except OSError:
                continue
            for src in found:
                try:
                    if src.is_symlink() or not src.is_file():
                        continue
                    st = src.stat()
                    key = (st.st_mtime_ns, st.st_size)
                    rel = src.relative_to(root).as_posix()
                    if st.st_size > MAX_BYTES or (self.seen.get(src) == key and (self.dest / rel).is_file()):
                        continue  # too big, or copied already and the copy is still there
                    self.seen[src] = key
                    if self._copy(src, rel):
                        copied.append(rel)
                except (OSError, ValueError):
                    continue
        if copied:
            self._save()
        return copied

    def _copy(self, src: Path, rel: str) -> bool:
        if not self._safe_dest():
            return False
        out = self.dest / rel
        if out.is_symlink() or (out.exists() and not self._ours(rel)):
            return False  # never replace a link or a file Full Fat did not copy
        if not _inside(out.parent, self.dest):  # before making folders: a linked subfolder leads elsewhere
            return False
        out.parent.mkdir(parents=True, exist_ok=True)
        if not _inside(out.parent, self.dest):
            return False
        data = src.read_bytes()
        if not data.startswith(b"\x89PNG"):
            return False
        tmp = out.with_name(out.name + ".full-fat-tmp")
        _write_new(tmp, data)
        os.replace(tmp, out)
        self.index[rel] = _sha(data)
        return True

    def _ours(self, rel: str) -> bool:
        p = self.dest / rel
        try:
            return rel in self.index and p.is_file() and _sha(p.read_bytes()) == self.index[rel]
        except OSError:
            return False

    def remove_copies(self) -> int:
        """For uninstall: delete the copies that nobody changed, then the folders that are left empty (plots/
        itself too). Returns how many files were deleted."""
        if self.dest.is_symlink() or not self.dest.is_dir():
            return 0
        gone = 0
        for rel in list(self.index):
            p = self.dest / rel
            if self._ours(rel) and _inside(p, self.dest):
                try:
                    p.unlink()
                    gone += 1
                except OSError:
                    continue
            if not p.exists():
                del self.index[rel]
        if self.index:
            self._save()
        else:
            try:
                (self.dest / INDEX).unlink()
            except OSError:
                pass
        for d in sorted((x for x in self.dest.rglob("*") if x.is_dir() and not x.is_symlink()),
                        key=lambda x: len(x.parts), reverse=True) + [self.dest]:
            try:
                d.rmdir()  # only when empty
            except OSError:
                pass
        return gone


def copies(folder: Path) -> list[Path]:
    """The unchanged copies Full Fat made in folder, and its list of them."""
    c = Copier([], folder)
    if c.dest.is_symlink() or not (c.dest / INDEX).is_file():
        return []
    return [c.dest / rel for rel in c.index if c._ours(rel)] + [c.dest / INDEX]


def clear(folder: Path) -> int:
    """For uninstall: delete the plot copies Full Fat made in folder."""
    return Copier([], folder).remove_copies()
