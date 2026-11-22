import json
import sys

import pytest

from full_fat import connector

FAKE = r'''
import json, sys
line = sys.stdin.readline()
msg = json.loads(line)
print("starting", file=sys.stderr, flush=True)
print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": {"serverInfo": {"name": "fake"}}}), flush=True)
sys.stdin.read()
'''


@pytest.mark.real_connector
def test_warm_ok(tmp_path):
    script = tmp_path / "fake.py"
    script.write_text(FAKE)
    ok, detail = connector.warm({"command": sys.executable, "args": [str(script)], "env": {"X": "1"}}, tmp_path, 30)
    assert ok and detail == ""


@pytest.mark.real_connector
def test_warm_failure_reports_last_line(tmp_path):
    script = tmp_path / "bad.py"
    script.write_text('import sys\nprint("error: git is not installed", file=sys.stderr)\nsys.exit(2)\n')
    ok, detail = connector.warm({"command": sys.executable, "args": [str(script)]}, tmp_path, 30)
    assert not ok and "git is not installed" in detail


@pytest.mark.real_connector
def test_warm_missing_program(tmp_path):
    ok, detail = connector.warm({"command": str(tmp_path / "nope"), "args": []}, tmp_path, 5)
    assert not ok
