"""Fetch the real prompts from GitHub. Run locally with: pytest -m network"""
import pytest

import urllib.request

from full_fat import workspace
from full_fat.prompts import load_prompts


@pytest.mark.network
def test_pinned_connector_archive_downloads():
    # The pin is a pull request's commit (jasp-stats/jasp-mcp #2): GitHub must still serve it by hash from the
    # jasp-stats link, or setup's connector start fails for everyone.
    with urllib.request.urlopen(workspace.JASP_MCP_URL, timeout=60) as r:
        assert r.status == 200
        assert r.read(4) == b"PK\x03\x04"


@pytest.mark.network
@pytest.mark.parametrize("version", ["0.98.0", "0.98.1", "0.98.8", "0.99.0", "1.0.0", None])
def test_real_prompts(version):
    p = load_prompts(version)
    assert p.system.startswith("You are JASP AI")
    assert "\\n" not in p.system and "\\\"" not in p.system
    assert p.annotate and p.annotate.startswith("Annotate only")
    assert {"alfred", "socrates", "evelyn"} <= set(p.personas)
    if version in ("1.0.0", None):
        assert p.ref == "development"
    else:
        assert p.ref == f"v{version}" and not p.notes
