"""End-to-end check against a real, running JASP (used by CI; read-only, safe on a real JASP too).

1. waits until JASP answers a JSON-RPC ping on its connection
2. calls rpc_discover and checks the methods
3. starts jasp-mcp exactly as the generated .mcp.json says, lists its tools over MCP and calls
   jasp_analyses_list

Usage: python tests/e2e_check_jasp.py WORKSPACE [--wait SECONDS]
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path


def rpc(url: str, method: str, timeout: float = 10):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": {}}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


class Mcp:
    def __init__(self, server: dict, cwd: Path):
        env = dict(os.environ, **server.get("env", {}))
        self.p = subprocess.Popen([server["command"], *server["args"]], cwd=cwd, env=env, text=True,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=1)
        self.q: queue.Queue = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()
        self.n = 0

    def _read(self):
        for line in self.p.stdout:
            self.q.put(line)

    def send(self, method: str, params: dict | None = None, notify: bool = False):
        msg = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if not notify:
            self.n += 1
            msg["id"] = self.n
        self.p.stdin.write(json.dumps(msg) + "\n")
        self.p.stdin.flush()
        if notify:
            return None
        deadline = time.monotonic() + 300  # the first run downloads jasp-mcp
        while time.monotonic() < deadline:
            try:
                line = self.q.get(timeout=5)
            except queue.Empty:
                if self.p.poll() is not None:
                    raise SystemExit(f"jasp-mcp exited with {self.p.returncode}")
                continue
            data = json.loads(line)
            if data.get("id") == self.n:
                if "error" in data:
                    raise SystemExit(f"MCP error on {method}: {data['error']}")
                return data["result"]
        raise SystemExit(f"no MCP answer to {method}")

    def close(self):
        self.p.terminate()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace", type=Path)
    ap.add_argument("--wait", type=float, default=600)
    a = ap.parse_args()
    server = json.loads((a.workspace / ".mcp.json").read_text())["mcpServers"]["jasp"]
    url = server["env"]["JASP_RPC_URL"]

    start = time.monotonic()
    while True:
        try:
            print("ping:", rpc(url, "ping", timeout=5)["result"], flush=True)
            break
        except OSError as e:
            if time.monotonic() - start > a.wait:
                print(f"JASP did not answer on {url} within {a.wait:.0f} s: {e}", flush=True)
                return 1
            time.sleep(5)
    print(f"JASP answered after {time.monotonic() - start:.0f} s", flush=True)
    methods = [m["name"] for m in rpc(url, "rpc_discover")["result"]["methods"]]
    print("rpc_discover:", ", ".join(methods), flush=True)
    assert "analyses_list" in methods and "analysis_create" in methods

    mcp = Mcp(server, a.workspace)
    try:
        init = mcp.send("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                       "clientInfo": {"name": "full-fat-ci", "version": "1"}})
        print("MCP server:", init.get("serverInfo"), flush=True)
        mcp.send("notifications/initialized", notify=True)
        tools = []
        for _ in range(40):  # jasp-mcp finds JASP's methods within a few seconds
            tools = [t["name"] for t in mcp.send("tools/list").get("tools", [])]
            if tools:
                break
            time.sleep(3)
        print("MCP tools:", ", ".join(tools), flush=True)
        assert "jasp_analyses_list" in tools, "jasp-mcp listed no JASP tools"
        res = mcp.send("tools/call", {"name": "jasp_analyses_list", "arguments": {}})
        print("jasp_analyses_list:", json.dumps(res)[:500], flush=True)
        assert not res.get("isError"), res
    finally:
        mcp.close()
    print("OK: JASP, its connection and jasp-mcp all work.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
