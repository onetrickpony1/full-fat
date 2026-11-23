"""Build the icon files Full Fat installs, from the SVGs in this folder.

Run from anywhere: python3 -I assets/icon/build.py
Needs rsvg-convert (librsvg) and magick (ImageMagick 7). Writes src/full_fat/icons/:
- full-fat-<size>.png for 16, 32, 48, 64, 128, 256 and 512 (Linux icon theme sizes),
- full-fat.ico (Windows: 16, 32, 48 and 64 as bitmaps, 128 and 256 as PNG),
- full-fat.icns (macOS: 16 to 1024, PNG entries, written here without extra tools).

ff-icon.svg is the main drawing (128 grid). ff-icon-64.svg, -32 and -16 are redrawn for small sizes, so 48 and
64 come from the 64 drawing and 16 and 32 from their own. gen.py and gen_small.py write the SVGs. The "FF"
letters are outlines of Inter Black (SIL Open Font License 1.1, see OFL-Inter.txt).
"""

from __future__ import annotations

import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent.parent / "src" / "full_fat" / "icons"
SOURCE = {16: "ff-icon-16.svg", 32: "ff-icon-32.svg", 48: "ff-icon-64.svg", 64: "ff-icon-64.svg"}
PNG_SIZES = [16, 32, 48, 64, 128, 256, 512]
ICO_BITMAP = [16, 32, 48, 64]  # stored as bitmaps, which every Windows reads
ICO_PNG = [128, 256]  # stored as PNG (Windows Vista and newer), which keeps the file small
# ICNS entry types holding PNG data, by pixel size (Apple's icns format; @2x entries reuse the bigger PNG)
ICNS_TYPES = [("icp4", 16), ("icp5", 32), ("icp6", 64), ("ic07", 128), ("ic08", 256), ("ic09", 512),
              ("ic10", 1024), ("ic11", 32), ("ic12", 64), ("ic13", 256), ("ic14", 512)]


def render(size: int, out: Path) -> None:
    svg = HERE / SOURCE.get(size, "ff-icon.svg")
    subprocess.run(["rsvg-convert", "-w", str(size), "-h", str(size), str(svg), "-o", str(out)], check=True)


def icns(pngs: dict[int, bytes]) -> bytes:
    body = b"".join(kind.encode("ascii") + struct.pack(">I", 8 + len(pngs[size])) + pngs[size]
                    for kind, size in ICNS_TYPES)
    return b"icns" + struct.pack(">I", 8 + len(body)) + body


def ico(bitmaps: bytes, pngs: list[bytes]) -> bytes:
    """An .ico with the entries of an existing .ico followed by PNG entries."""
    count = struct.unpack("<H", bitmaps[4:6])[0]
    images = []
    for i in range(count):
        entry = bitmaps[6 + 16 * i:22 + 16 * i]
        size, offset = struct.unpack("<II", entry[8:16])
        images.append((entry[:8], bitmaps[offset:offset + size]))
    for png in pngs:
        w, h = struct.unpack(">II", png[16:24])
        images.append((bytes([w % 256, h % 256, 0, 0]) + struct.pack("<HH", 1, 32), png))
    head = struct.pack("<HHH", 0, 1, len(images))
    offset = len(head) + 16 * len(images)
    table, data = b"", b""
    for start, img in images:
        table += start + struct.pack("<II", len(img), offset + len(data))
        data += img
    return head + table + data


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        pngs: dict[int, bytes] = {}
        for size in sorted(set(PNG_SIZES) | {s for _, s in ICNS_TYPES}):
            p = Path(tmp) / f"{size}.png"
            render(size, p)
            pngs[size] = p.read_bytes()
        for size in PNG_SIZES:
            (OUT / f"full-fat-{size}.png").write_bytes(pngs[size])
        small = Path(tmp) / "small.ico"  # classic bitmap entries for the small sizes, from ImageMagick
        subprocess.run(["magick", *[str(Path(tmp) / f"{s}.png") for s in ICO_BITMAP], str(small)], check=True)
        (OUT / "full-fat.ico").write_bytes(ico(small.read_bytes(), [pngs[s] for s in ICO_PNG]))
        (OUT / "full-fat.icns").write_bytes(icns(pngs))
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
