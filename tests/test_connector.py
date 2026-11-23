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


def test_pick_url_falls_back_only_when_github_says_the_pin_is_gone():
    from full_fat import workspace
    assert connector.pick_url(lambda url: False) == workspace.JASP_MCP_URL
    assert connector.pick_url(lambda url: url == workspace.JASP_MCP_URL) == workspace.JASP_MCP_FALLBACK_URL
    assert connector.pick_url(lambda url: True) == workspace.JASP_MCP_URL  # both gone: keep the pin, warm explains


@pytest.mark.real_connector
def test_archive_gone_only_on_404(monkeypatch):
    import io
    import urllib.error
    def raising(exc):
        def opener(req, timeout=30):
            raise exc
        return opener
    for exc, gone in [(urllib.error.HTTPError("u", 404, "Not Found", {}, io.BytesIO()), True),
                      (urllib.error.HTTPError("u", 503, "Unavailable", {}, io.BytesIO()), False),
                      (urllib.error.URLError("offline"), False), (TimeoutError(), False)]:
        monkeypatch.setattr(connector.urllib.request, "urlopen", raising(exc))
        assert connector.archive_gone("https://example.invalid/x.zip") is gone
