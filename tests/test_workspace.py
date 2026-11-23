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


def build(folder, p, careful=False, persona="alfred", home=None):
    return workspace.build(folder, p, persona, careful, "127.0.0.1", 48164,
                           [Path("/home/u/.var/app/org.jaspstats.JASP/data/JASP/JASP/temp")],
                           uvx="/home/u/.local/bin/uvx", home=home or Path("/home/u"), platform="linux")


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
    wheels = [a for p in ("cryptography", "cffi", "pydantic-core", "rpds-py") for a in ("--no-build-package", p)]
    assert mcp["args"] == wheels + ["--with", "mcp<2", "--from",
                                    "jasp-mcp @ https://github.com/jasp-stats/jasp-mcp/archive/"
                                    "6f675f63977073d342a5f1998fe99c3511190924.zip", "jasp-mcp"]
    assert "--no-build" not in mcp["args"]  # jasp-mcp itself must still be built from its archive
    assert not any("git+" in a for a in mcp["args"])
    assert mcp["env"] == {"JASP_RPC_URL": "http://127.0.0.1:48164/rpc"}
    codex = tomllib.loads((tmp_path / ".codex/config.toml").read_text())
    assert "model" not in codex  # so a model picked with /model lasts
    assert codex["model_reasoning_effort"] == "high"  # the ChatGPT app gets no effort flag, so the folder sets it
    # the ChatGPT app's extra tools are off; node_repl has a command so the file loads where the app is missing
    assert codex["mcp_servers"]["node_repl"] == {"command": "node_repl", "enabled": False}
    assert codex["features"]["apps"] is False
    assert {k: v["enabled"] for k, v in codex["plugins"].items()} == {
        "unified-computer-use@openai-bundled": False, "browser@openai-bundled": False,
        "chrome@openai-bundled": False}
    assert codex["sandbox_mode"] == "read-only" and codex["features"]["shell_tool"] is False
    assert codex["approvals_reviewer"] == "user" and codex["approval_policy"] == "on-request"
    assert codex["web_search"] == "disabled"
    srv = codex["mcp_servers"]["jasp"]
    assert srv["args"] == mcp["args"] and srv["env"] == mcp["env"]
    # longer than jasp-mcp's own fixed 60 s, so its answer reaches Codex (Codex's default is 60 s)
    assert srv["tool_timeout_sec"] == 120 and "timeout" not in mcp
    assert srv["default_tools_approval_mode"] == "prompt"
    assert set(srv["tools"]) == set(workspace.DEFAULT_TOOLS)
    for t in ("jasp_data_load", "jasp_write_report", "jasp_analysis_createAnnotation", "jasp_analysis_composeResults"):
        assert t not in srv["tools"]  # these ask (default_tools_approval_mode)
    assert "jasp_analysis_run" in srv["tools"]


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
    assert "model" not in s and "effortLevel" not in s and s["enabledMcpjsonServers"] == ["jasp"]
    assert s["env"]["MAX_MCP_OUTPUT_TOKENS"] == "100000"
    assert s["permissions"]["defaultMode"] == "default"
    assert "mcp__jasp__jasp_analysis_create" in s["permissions"]["allow"]
    asking = {"mcp__jasp__jasp_" + t for t in ("data_load", "write_report", "analysis_createAnnotation",
                                                 "analysis_composeResults")}
    assert set(s["permissions"]["ask"]) == asking and not asking & set(s["permissions"]["allow"])
    assert "mcp__jasp" not in s["permissions"]["allow"]
    assert "Read(~/.var/app/org.jaspstats.JASP/data/JASP/JASP/temp/**)" in s["permissions"]["allow"]
    assert "Read(~/.local/share/JASP/JASP/temp/**)" in s["permissions"]["allow"]
    assert set(s["permissions"]["deny"]) == {"Bash", "PowerShell", "Edit", "Write", "NotebookEdit"}
    build(tmp_path, p, careful=True)
    s = json.loads((tmp_path / ".claude/settings.json").read_text())
    assert "mcp__jasp__jasp_analyses_list" in s["permissions"]["allow"]
    assert "mcp__jasp__jasp_analysis_create" not in s["permissions"]["allow"]
    assert "mcp__jasp__jasp_analysis_create" in s["permissions"]["ask"]
    s["permissions"]["defaultMode"] = "plan"  # the user's own choice of mode stays
    s["permissions"]["ask"].append("Read(/secret/**)")
    (tmp_path / ".claude/settings.json").write_text(json.dumps(s))
    build(tmp_path, p)
    s = json.loads((tmp_path / ".claude/settings.json").read_text())
    assert s["permissions"]["defaultMode"] == "plan" and "Read(/secret/**)" in s["permissions"]["ask"]


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
    assert (tmp_path / "AGENTS.md").read_text().startswith("# Full Fat\n")


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
    assert json.loads((tmp_path / ".claude/settings.json").read_text())["permissions"]["defaultMode"] == "default"


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


def test_model_and_effort_left_to_the_user(tmp_path, p):
    # an earlier Full Fat wrote model "opus" and effortLevel "high": both are taken back out
    build(tmp_path, p)
    sp, mp = tmp_path / ".claude/settings.json", tmp_path / ".full-fat.json"
    s = json.loads(sp.read_text())
    s.update(model="opus", effortLevel="high")
    sp.write_text(json.dumps(s))
    m = json.loads(mp.read_text())
    m["claude_model"] = "opus"
    mp.write_text(json.dumps(m))
    build(tmp_path, p)
    s = json.loads(sp.read_text())
    assert "model" not in s and "effortLevel" not in s
    s.update(model="sonnet", effortLevel="low")  # the user's own choices are never touched
    sp.write_text(json.dumps(s))
    build(tmp_path, p)
    s = json.loads(sp.read_text())
    assert s["model"] == "sonnet" and s["effortLevel"] == "low"


def test_manifest_lists_the_json_files(tmp_path, p):
    build(tmp_path, p)
    files = json.loads((tmp_path / ".full-fat.json").read_text())["files"]
    for rel in (".mcp.json", ".claude/settings.json", "AGENTS.md"):
        assert files[rel] == workspace.sha((tmp_path / rel).read_text())


def test_jasp_assistant_tools_match_capabilities():
    # Resources/JASP_Capabilities.json (v0.98.1, development): every method of every capability
    caps = ["modules_list", "analysis_create", "analysis_run", "get_analyses_state", "write_report",
            "analysis_createAnnotation", "analyses_list", "get_analyses_state", "analysis_results",
            "analysis_context", "data_info"]
    assert set(workspace.JASP_ASSISTANT_TOOLS) == {"jasp_" + c for c in caps}


def test_guidance_names_real_tools_that_run_without_asking():
    # The assistant is told to read option descriptions and check options it got back: those tools must exist
    # and run without asking, or the advice costs the user an approval every time.
    import re
    env = workspace.template("environment.md")
    named = set(re.findall(r"`(jasp_[A-Za-z_]+)`", env))
    assert {"jasp_analysis_create", "jasp_get_analyses_state", "jasp_analysis_run"} <= named
    assert named <= set(workspace.ALL_TOOLS)
    assert {"jasp_analysis_create", "jasp_get_analyses_state", "jasp_analysis_run"} <= set(workspace.DEFAULT_TOOLS)
    # get_analyses_state's parameter in JASP's Resources/JASP_RPC.json (v0.99.0)
    assert "`include_descriptions`" in env


def test_guidance_on_tools_that_vanish_mid_chat():
    # jasp-mcp drops every tool for about 2 s when its ping meets JASP busy with another call; the restart
    # advice is only for a chat that starts without tools.
    env = workspace.template("environment.md")
    assert "available at the start of the chat" in env
    assert "disappear in the middle of a chat" in env and "come back on their own" in env
    assert "compare the options it returns with what you sent" in env


def test_guidance_on_one_call_at_a_time_state_and_slow_calls():
    # The pinned jasp-mcp sends parallel calls straight to JASP (which refuses all but one), its 2 s ping uses
    # up JASP's notes about the user's own edits, and it gives up on a call after a fixed 60 s.
    env = " ".join(workspace.template("environment.md").split())
    assert "one at a time, never in parallel" in env
    # get_analyses_state needs analysisIds (Resources/JASP_RPC.json v0.99.0), so the IDs come first
    assert "get its ID from `jasp_analyses_list`" in env and "(it needs `analysisIds`)" in env
    assert "If the user says they changed something, read it again before you act." in env
    assert "Keep `timeoutMs` at 45000 or lower, even for slow analyses and data loading" in env
    # status names from Desktop/analysis/analysis.cpp statusToString; finished = analysis.h isFinished (v0.99.0)
    assert 'finished when the status is "complete", "validationError" or "fatalError"' in env
    for status in ("running", "empty", "runningImg", "aborted"):
        assert f'"{status}"' in env
    assert 'JASP says "complete" (not "success"' in env
    assert 'after three checks, tell the user it is still working and ask them to send "continue"' in env
    assert 'If the status is "aborted", read it once more with `jasp_get_analyses_state`' in env
    assert "check again with `jasp_analysis_results`" in env
    assert "read it with `jasp_get_analyses_state`, giving its ID and `include_results` true" in env
    assert "Don't run it again blindly, and don't tell the user to restart." in env
    assert {"jasp_get_analyses_state", "jasp_analysis_results", "jasp_analyses_list"} <= set(workspace.READ_ONLY_TOOLS)


def test_guidance_on_a_busy_jasp():
    env = " ".join(workspace.template("environment.md").split())
    assert 'If a JASP tool answers "Procedure call already in flight"' in env
    assert "Don't call it again in a loop." in env
    assert "Try again" not in env  # vanished tools: ask for "continue" instead of retrying blindly
    assert 'Tell the user that JASP was busy and ask them to send "continue".' in env
