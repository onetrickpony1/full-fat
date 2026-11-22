import json
import tomllib
from pathlib import Path

import pytest

from conftest import make_fetcher
from full_fat import workspace
from full_fat.prompts import load_prompts


@pytest.fixture
def p(fake_github):
    return load_prompts("0.98.1", make_fetcher(fake_github))


def build(folder, p, careful=False, persona="alfred", home=None, model="opus"):
    return workspace.build(folder, p, persona, careful, "127.0.0.1", 48164,
                           [Path("/home/u/.var/app/org.jaspstats.JASP/data/JASP/JASP/temp")],
                           uvx="/home/u/.local/bin/uvx", home=home or Path("/home/u"), platform="linux",
                           claude_model=model)


def test_files(tmp_path, p):
    build(tmp_path, p)
    for f in ["AGENTS.md", "CLAUDE.md", ".mcp.json", ".claude/settings.json", ".claude/commands/annotate.md",
              ".codex/config.toml", "jasp/system-prompt.md", "jasp/annotate-prompt.md",
              "jasp/personas/alfred.md", "jasp/source.txt", ".full-fat.json"]:
        assert (tmp_path / f).is_file(), f
    assert (tmp_path / "CLAUDE.md").read_text() == "@AGENTS.md\n"
    assert "v0.98.1 (AGPL-3.0)" in (tmp_path / "jasp/source.txt").read_text()


def test_agents_md_layout(tmp_path, p):
    build(tmp_path, p)
    text = (tmp_path / "AGENTS.md").read_text()
    env = workspace.template("environment.md")
    assert text.startswith(env + p.system + "\n")
    assert text.endswith("\n\nPersona Prompt:\n  Your name is: Alfred the Assistant\n\n"
                         "  Your name is Alfred.\n  Line two.\n")
    build(tmp_path, p, persona="none")
    assert "Persona Prompt" not in (tmp_path / "AGENTS.md").read_text()
    with pytest.raises(ValueError):
        build(tmp_path, p, persona="zelda")


def test_mcp_and_codex(tmp_path, p):
    build(tmp_path, p)
    mcp = json.loads((tmp_path / ".mcp.json").read_text())["mcpServers"]["jasp"]
    assert mcp["command"] == "/home/u/.local/bin/uvx"
    assert mcp["args"] == ["--with", "mcp<2", "--from",
                           "jasp-mcp @ https://github.com/jasp-stats/jasp-mcp/archive/"
                           "72d9d7be9c003b9681b40871ee5850795108e5ab.zip", "jasp-mcp"]
    assert not any("git+" in a for a in mcp["args"])
    assert mcp["env"] == {"JASP_RPC_URL": "http://127.0.0.1:48164/rpc"}
    codex = tomllib.loads((tmp_path / ".codex/config.toml").read_text())
    assert codex["model"] == "gpt-6.2-astra" and codex["model_reasoning_effort"] == "high"
    assert codex["sandbox_mode"] == "read-only" and codex["features"]["shell_tool"] is False
    assert codex["approvals_reviewer"] == "user"
    srv = codex["mcp_servers"]["jasp"]
    assert srv["args"] == mcp["args"] and srv["env"] == mcp["env"]
    assert srv["default_tools_approval_mode"] == "prompt"
    assert set(srv["tools"]) == set(workspace.DEFAULT_TOOLS)
    assert "jasp_data_load" not in srv["tools"] and "jasp_write_report" in srv["tools"]


def test_codex_careful(tmp_path, p):
    build(tmp_path, p, careful=True)
    srv = tomllib.loads((tmp_path / ".codex/config.toml").read_text())["mcp_servers"]["jasp"]
    assert tomllib.loads((tmp_path / ".codex/config.toml").read_text())["approvals_reviewer"] == "user"
    assert srv["default_tools_approval_mode"] == "prompt"
    assert set(srv["tools"]) == set(workspace.READ_ONLY_TOOLS)
    assert all(v == {"approval_mode": "approve"} for v in srv["tools"].values())


def test_codex_windows_path_quoting():
    text = workspace.codex_config(r"C:\Users\me\.local\bin\uvx.exe", "127.0.0.1", 48164, False)
    assert tomllib.loads(text)["mcp_servers"]["jasp"]["command"] == r"C:\Users\me\.local\bin\uvx.exe"
    text = workspace.codex_config("/Users/o'neil/.local/bin/uvx", "127.0.0.1", 48164, False)
    assert tomllib.loads(text)["mcp_servers"]["jasp"]["command"] == "/Users/o'neil/.local/bin/uvx"


def test_claude_settings_modes(tmp_path, p):
    build(tmp_path, p)
    s = json.loads((tmp_path / ".claude/settings.json").read_text())
    assert s["model"] == "opus" and s["effortLevel"] == "high" and s["enabledMcpjsonServers"] == ["jasp"]
    assert s["env"]["MAX_MCP_OUTPUT_TOKENS"] == "100000"
    assert "mcp__jasp__jasp_analysis_create" in s["permissions"]["allow"]
    assert "mcp__jasp__jasp_data_load" not in s["permissions"]["allow"]
    assert "mcp__jasp" not in s["permissions"]["allow"]
    assert "Read(~/.var/app/org.jaspstats.JASP/data/JASP/JASP/temp/**)" in s["permissions"]["allow"]
    assert "Read(~/.local/share/JASP/JASP/temp/**)" in s["permissions"]["allow"]
    assert set(s["permissions"]["deny"]) == {"Bash", "PowerShell", "Edit", "Write", "NotebookEdit"}
    build(tmp_path, p, careful=True)
    s = json.loads((tmp_path / ".claude/settings.json").read_text())
    assert "mcp__jasp__jasp_analyses_list" in s["permissions"]["allow"]
    assert "mcp__jasp__jasp_analysis_create" not in s["permissions"]["allow"]


def test_rerun_keeps_user_files_and_settings(tmp_path, p):
    build(tmp_path, p)
    (tmp_path / "my-notes.txt").write_text("mine")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "study.csv").write_text("a,b\n")
    s = json.loads((tmp_path / ".claude/settings.json").read_text())
    s["model"] = "sonnet"
    s["permissions"]["allow"].append("WebSearch")
    s["permissions"]["deny"].append("WebFetch")
    s["hooks"] = {"x": 1}
    (tmp_path / ".claude/settings.json").write_text(json.dumps(s))
    mcp = json.loads((tmp_path / ".mcp.json").read_text())
    mcp["mcpServers"]["other"] = {"command": "x"}
    (tmp_path / ".mcp.json").write_text(json.dumps(mcp))
    res = build(tmp_path, p)
    assert (tmp_path / "my-notes.txt").read_text() == "mine"
    assert (tmp_path / "data" / "study.csv").exists()
    s = json.loads((tmp_path / ".claude/settings.json").read_text())
    assert s["model"] == "sonnet" and s["hooks"] == {"x": 1}
    assert "WebSearch" in s["permissions"]["allow"] and "WebFetch" in s["permissions"]["deny"]
    assert s["permissions"]["allow"].count("mcp__jasp__jasp_analysis_run") == 1
    assert s["permissions"]["deny"].count("Bash") == 1
    assert "other" in json.loads((tmp_path / ".mcp.json").read_text())["mcpServers"]
    assert res.kept_old == []


def test_rerun_keeps_edited_text_file(tmp_path, p):
    build(tmp_path, p)
    (tmp_path / "AGENTS.md").write_text("my own rules\n")
    res = build(tmp_path, p)
    assert len(res.kept_old) == 1 and Path(res.kept_old[0]).read_text() == "my own rules\n"
    assert (tmp_path / "AGENTS.md").read_text().startswith("# JASP workspace")


def test_old_setup_sh_workspace_is_updated_without_backups(tmp_path, p):
    # a folder from the old setup.sh: no .full-fat.json, files with the old content
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".claude" / "commands").mkdir(parents=True)
    (tmp_path / "AGENTS.md").write_text("# JASP workspace\n\nold\n")
    (tmp_path / "CLAUDE.md").write_text("@AGENTS.md\n")
    (tmp_path / ".codex/config.toml").write_text("# Full Fat: Codex settings\nmodel = \"x\"\n")
    (tmp_path / ".claude/commands/annotate.md").write_text("---\ndescription: Annotate a JASP analysis in x\n---\n")
    (tmp_path / ".claude/settings.json").write_text(json.dumps({"model": "opus", "permissions": {"allow": [
        "mcp__jasp__jasp_ping", "Read(~/.local/share/JASP/JASP/temp/**)"]}}))
    res = build(tmp_path, p)
    assert res.kept_old == []
    allow = json.loads((tmp_path / ".claude/settings.json").read_text())["permissions"]["allow"]
    assert allow.count("mcp__jasp__jasp_ping") == 1 and allow.count("Read(~/.local/share/JASP/JASP/temp/**)") == 1


def test_broken_json_is_kept(tmp_path, p):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude/settings.json").write_text("{not json")
    res = build(tmp_path, p)
    assert any(x.endswith(tuple("0123456789")) for x in res.kept_old)
    assert json.loads((tmp_path / ".claude/settings.json").read_text())["model"] == "opus"


def test_read_rules():
    home = Path("/Users/me")
    assert workspace.read_rule(Path("/Users/me/Library/Application Support/JASP/JASP/temp"), home) == \
        "Read(~/Library/Application Support/JASP/JASP/temp/**)"
    assert workspace.read_rule(Path("/opt/jasp/temp"), home) == "Read(//opt/jasp/temp/**)"
    rules = workspace.plot_rules([Path("/Users/me/Library/Application Support/JASP/JASP/temp")], home, "mac")
    assert rules == ["Read(~/Library/Application Support/JASP/JASP/temp/**)"]
    rules = workspace.plot_rules([], home, "windows")
    assert any("JASP-Stats-MSIX" in r for r in rules)


def test_no_annotation_prompt(tmp_path, p):
    p.annotate = None
    build(tmp_path, p)
    assert not (tmp_path / ".claude/commands/annotate.md").exists()


def test_model_by_plan(tmp_path, p):
    build(tmp_path, p, model=None)  # Pro: Claude Code's own default
    s = json.loads((tmp_path / ".claude/settings.json").read_text())
    assert "model" not in s and s["effortLevel"] == "high"
    build(tmp_path, p, model="opus")  # now Max
    assert json.loads((tmp_path / ".claude/settings.json").read_text())["model"] == "opus"
    build(tmp_path, p, model=None)  # back to Pro: Full Fat's own "opus" goes again
    assert "model" not in json.loads((tmp_path / ".claude/settings.json").read_text())
    s = json.loads((tmp_path / ".claude/settings.json").read_text())
    s["model"] = "sonnet"  # the user's own choice is never touched
    (tmp_path / ".claude/settings.json").write_text(json.dumps(s))
    build(tmp_path, p, model="opus")
    assert json.loads((tmp_path / ".claude/settings.json").read_text())["model"] == "sonnet"


def test_jasp_assistant_tools_match_capabilities():
    # Resources/JASP_Capabilities.json (v0.98.1, development): every method of every capability
    caps = ["modules_list", "analysis_create", "analysis_run", "get_analyses_state", "write_report",
            "analysis_createAnnotation", "analyses_list", "get_analyses_state", "analysis_results",
            "analysis_context", "data_info"]
    assert set(workspace.JASP_ASSISTANT_TOOLS) == {"jasp_" + c for c in caps}
