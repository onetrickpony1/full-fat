"""CI check of JASP's connection setting with the real JASP (macOS and Windows).

  off WORKSPACE        the setting is off (or absent) on disk while JASP still answers
  restart WORKSPACE    quit JASP, check the setting is still off on disk, start JASP again without Full Fat,
                       and check it never answers while it runs

Exit code 0 means the check passed.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from full_fat import jasp, state, workspace  # noqa: E402


def store_and_port(ws: Path):
    st = state.load()
    j = jasp.detect(st.get("settings_file"), st.get("jasp_version"))
    m = workspace.read_manifest(ws)
    return j, j.write_store(), m.get("host") or "127.0.0.1", int(m.get("port") or 48164)


def off_on_disk(store) -> bool:
    v = store.get(jasp.KEY_ENABLED)
    print(f"rpcServerEnabled on disk: {v!r}", flush=True)
    return (v or "").lower() not in ("true", "1")


def quit_jasp() -> None:
    if sys.platform == "darwin":
        subprocess.run(["osascript", "-e", 'quit app "JASP"'], timeout=60)
    else:  # ask the window to close, as a click on its X does
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-Process JASPDesktop -ErrorAction SilentlyContinue | ForEach-Object { $_.CloseMainWindow() }"],
                       timeout=60)
    for _ in range(120):
        if not jasp.running():
            print("JASP has quit", flush=True)
            return
        time.sleep(1)
    raise SystemExit("JASP did not quit")


def start_jasp(j) -> None:
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-a", "/Applications/JASP.app"])
    else:
        exe = next(Path(sys.argv[3]).rglob("JASPDesktop.exe"))
        subprocess.Popen([str(exe)])


def main() -> int:
    what, ws = sys.argv[1], Path(sys.argv[2])
    j, store, host, port = store_and_port(ws)
    if what == "off":
        if not jasp.ping(host, port):
            raise SystemExit("JASP does not answer")
        print("JASP answers", flush=True)
        if not off_on_disk(store):
            raise SystemExit("the setting is still on while JASP runs")
        return 0
    quit_jasp()
    time.sleep(3)
    if not off_on_disk(store):
        raise SystemExit("JASP wrote the setting back when it quit")
    start_jasp(j)
    seen_running, deadline = 0.0, time.monotonic() + 600
    while time.monotonic() < deadline:
        if jasp.ping(host, port):
            raise SystemExit("JASP started without Full Fat answers on its port")
        if jasp.running():
            seen_running += 2
            if seen_running >= 240:  # well past the time the first start needed to answer
                print(f"JASP ran for {seen_running:.0f} s without answering: no connection", flush=True)
                return 0
        time.sleep(2)
    raise SystemExit("JASP did not start again")


if __name__ == "__main__":
    sys.exit(main())
