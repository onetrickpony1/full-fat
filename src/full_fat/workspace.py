"""Build the folder that Claude Code and Codex open in.

Generated files and what each is for:
- AGENTS.md: the instructions both apps read. templates/environment.md (how this setup differs from the chat
  inside JASP), then JASP's system prompt, then "Persona Prompt:" with the persona indented, as
  Desktop/ai/aiBridge.cpp (v0.98.1 lines 569-590) builds JASP's own request.
- CLAUDE.md: one line, @AGENTS.md, so Claude Code reads AGENTS.md too.
- .mcp.json: tells Claude Code how to start jasp-mcp.
- .claude/settings.json: Claude Code's model, effort, which JASP tools run without asking, and the tools
  that are switched off (shell, file edits).
- .claude/commands/annotate.md: the /annotate command, with JASP's annotation prompt.
- .codex/config.toml: the same for Codex (used once the folder is trusted).
- jasp/: the downloaded prompts and where they came from (source.txt).
- .full-fat.json: what Full Fat wrote, so a rerun can tell your own changes from its own files.

A rerun never deletes anything. JSON settings are merged. A text file you changed is kept next to the new
one as <name>.old-<date>.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from . import __version__
from .prompts import Prompts

JASP_MCP_SHA = "72d9d7be9c003b9681b40871ee5850795108e5ab"  # jasp-stats/jasp-mcp, 2026-05-13
# jasp-mcp crashes with the MCP Python SDK 2.x ("'Server' object has no attribute 'list_tools'"),
# so uvx is told to use mcp<2. It is fetched as a GitHub archive, not git+https, because fresh Macs and
# Windows PCs have no git (on a Mac, calling git opens Apple's "install developer tools" dialog instead).
JASP_MCP_URL = f"https://github.com/jasp-stats/jasp-mcp/archive/{JASP_MCP_SHA}.zip"
UVX_ARGS = ["--with", "mcp<2", "--from", f"jasp-mcp @ {JASP_MCP_URL}", "jasp-mcp"]

# JASP RPC methods that only read (from rpc_discover on JASP 0.98.1).
READ_ONLY_TOOLS = [
    "jasp_ping", "jasp_rpc_discover", "jasp_modules_list", "jasp_analyses_list", "jasp_get_analyses_state",
    "jasp_analysis_results", "jasp_analysis_context", "jasp_data_info", "jasp_data_load_status",
]
# The tools JASP's own assistant gets with every shipped persona (enabledCapabilities ["*"]): all methods in
# Resources/JASP_Capabilities.json (v0.98.1 and development), resolved in Desktop/gui/aipersonamodel.cpp
# (v0.98.1 lines 402-433). They change only what is inside JASP: write_report makes a report in the results
# pane (Desktop/analysis/analyses.cpp line 1697), not a file. These run without asking by default.
JASP_ASSISTANT_TOOLS = [
    "jasp_modules_list", "jasp_analysis_create", "jasp_analysis_run", "jasp_get_analyses_state",
    "jasp_write_report", "jasp_analysis_createAnnotation", "jasp_analyses_list", "jasp_analysis_results",
    "jasp_analysis_context", "jasp_data_info",
]
# Not given to JASP's own assistant, so they always ask: jasp_data_load (opens a data file from any path and
# replaces the data in JASP, Desktop/mainwindow.cpp line 1460) and jasp_analysis_composeResults.
DEFAULT_TOOLS = JASP_ASSISTANT_TOOLS + [t for t in READ_ONLY_TOOLS if t not in JASP_ASSISTANT_TOOLS]
# Claude Code tools the JASP assistant has no use for. JASP's own assistant has none of them.
BLOCKED_CLAUDE_TOOLS = ["Bash", "PowerShell", "Edit", "Write", "NotebookEdit"]
MANIFEST = ".full-fat.json"
MARKERS = {  # how to recognise a file written by an older Full Fat (before .full-fat.json existed)
    "AGENTS.md": "# JASP workspace",  # setup.sh's heading: do not rename, it only matches those old files
    ".codex/config.toml": "# Full Fat",
    ".claude/commands/annotate.md": "description: Annotate a JASP analysis",
}


def template(name: str) -> str:
    return resources.files("full_fat").joinpath("templates", name).read_text(encoding="utf-8")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def find_uvx() -> str:
    exe = shutil.which("uvx")
    if exe:
        return exe
    name = "uvx.exe" if os.name == "nt" else "uvx"
    for c in (Path.home() / ".local" / "bin" / name, Path.home() / ".cargo" / "bin" / name):
        if c.is_file():
            return str(c)
    return "uvx"


def toml_str(s: str) -> str:
    """A TOML string: literal ('...') when possible, so Windows paths need no escaping."""
    if "'" not in s and "\n" not in s:
        return f"'{s}'"
    return json.dumps(s)


def read_rule(path: Path, home: Path) -> str:
    """A Claude Code Read rule for everything under a folder (~/... or //c/... on Windows)."""
    try:
        rel = path.relative_to(home)
        return f"Read(~/{rel.as_posix()}/**)"
    except ValueError:
        p = path.as_posix()
        if len(p) > 1 and p[1] == ":":
            p = "/" + p[0].lower() + p[2:]
        return f"Read(/{p if p.startswith('/') else '/' + p}/**)"


def plot_rules(plot_dirs: list[Path], home: Path, platform: str | None = None) -> list[str]:
    platform = platform or ("windows" if sys.platform.startswith("win") else
                            "mac" if sys.platform == "darwin" else "linux")
    dirs = list(plot_dirs)
    if platform == "linux":  # both kinds, so switching between Flatpak and a native build keeps working
        dirs += [home / ".var/app/org.jaspstats.JASP/data/JASP/JASP/temp", home / ".local/share/JASP/JASP/temp"]
    rules = []
    for d in dirs:
        r = read_rule(d, home)
        if r not in rules:
            rules.append(r)
    if platform == "windows":
        r = "Read(~/AppData/Local/Packages/*JASP*/LocalCache/Local/JASP-Stats-MSIX/JASPDesktop/temp/**)"
        if r not in rules:
            rules.append(r)
    return rules


def agents_md(prompts: Prompts, persona: str) -> str:
    text = template("environment.md") + prompts.system + "\n"
    if persona != "none":
        _, prompt = prompts.personas[persona]
        name, _ = prompts.personas[persona]
        # as Desktop/ai/aiBridge.cpp (v0.98.1 lines 587-589) builds it
        text += ("\nPersona Prompt:\n" + f"  Your name is: {name}\n\n"
                 + "".join("  " + line + "\n" for line in prompt.strip().split("\n")))
    return text


def mcp_server(uvx: str, host: str, port: int) -> dict:
    return {"command": uvx, "args": list(UVX_ARGS), "env": {"JASP_RPC_URL": f"http://{host}:{port}/rpc"}}


def codex_config(uvx: str, host: str, port: int, careful: bool) -> str:
    args = ", ".join(json.dumps(a) for a in UVX_ARGS)
    lines = [
        "# Full Fat: Codex settings for this folder (used once you trust the folder).",
        'model = "gpt-6.2-astra"',
        'model_reasoning_effort = "high"',
        "# Codex may read files but not change them or run programs that change things.",
        'sandbox_mode = "read-only"',
        "# No shell: JASP's own assistant has none, and the chat doesn't need one.",
        "features.shell_tool = false",
        "# You answer approval questions yourself, not Codex's automatic reviewer.",
        'approvals_reviewer = "user"',
    ]
    lines += [
        "",
        "[mcp_servers.jasp]",
        f"command = {toml_str(uvx)}",
        f"args = [{args}]",
        f'env = {{ JASP_RPC_URL = "http://{host}:{port}/rpc" }}',
    ]
    if careful:
        lines += ["# Careful mode: ask before anything that changes JASP. Reading runs without asking."]
    else:
        lines += ["# Like the chat inside JASP: its tools run without asking. Loading a data file asks."]
    lines += ['default_tools_approval_mode = "prompt"']
    for t in (READ_ONLY_TOOLS if careful else DEFAULT_TOOLS):
        lines += ["", f"[mcp_servers.jasp.tools.{t}]", 'approval_mode = "approve"']
    return "\n".join(lines) + "\n"


def merge_claude_settings(old: dict, careful: bool, read_rules: list[str], model: str | None = "opus",
                          model_was_ours: bool = False) -> dict:
    """model: what to set, or None to leave Claude Code's default.
    model_was_ours: the current value was written by Full Fat, so it may be changed or removed."""
    new = json.loads(template("claude-settings.json"))
    out = dict(old)
    ours = model_was_ours
    if model:
        if "model" not in out or ours:
            out["model"] = model
    elif ours and "model" in out:
        del out["model"]
    out.setdefault("effortLevel", new["effortLevel"])
    servers = list(out.get("enabledMcpjsonServers") or [])
    if "jasp" not in servers:
        servers.append("jasp")
    out["enabledMcpjsonServers"] = servers
    env = dict(out.get("env") or {})
    for k, v in new["env"].items():
        env.setdefault(k, v)
    out["env"] = env
    perms = dict(out.get("permissions") or {})

    def ours_allow(rule: str) -> bool:
        return rule.startswith("mcp__jasp") or (rule.startswith("Read(") and "JASP" in rule and "temp" in rule)

    allow = [r for r in perms.get("allow") or [] if not ours_allow(r)]
    allow += ["mcp__jasp__" + t for t in (READ_ONLY_TOOLS if careful else DEFAULT_TOOLS)] + read_rules
    deny = [r for r in perms.get("deny") or [] if r not in BLOCKED_CLAUDE_TOOLS]
    deny += BLOCKED_CLAUDE_TOOLS
    perms["allow"] = allow
    perms["deny"] = deny
    out["permissions"] = perms
    return out


def annotate_md(prompts: Prompts) -> str | None:
    return None if prompts.annotate is None else template("annotate-head.md") + prompts.annotate + "\n"


@dataclass
class Result:
    written: list[str] = field(default_factory=list)
    kept_old: list[str] = field(default_factory=list)


def _load_json(path: Path, result: Result, stamp: str) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except ValueError:
        pass
    old = path.with_name(f"{path.name}.old-{stamp}")
    shutil.copy2(path, old)
    result.kept_old.append(str(old))
    return {}


def build(folder: Path, prompts: Prompts, persona: str, careful: bool, host: str, port: int,
          plot_dirs: list[Path], uvx: str | None = None, home: Path | None = None,
          platform: str | None = None, claude_model: str | None = "opus") -> Result:
    folder = Path(folder)
    home = home or Path.home()
    uvx = uvx or find_uvx()
    if persona != "none" and persona not in prompts.personas:
        raise ValueError(f"No persona '{persona}'. Choose: {', '.join(list(prompts.personas) + ['none'])}")
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    result = Result()
    manifest_path = folder / MANIFEST
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        manifest = {}
    old_hashes = manifest.get("files", {}) if isinstance(manifest, dict) else {}
    new_hashes: dict[str, str] = {}

    def write_text(rel: str, content: str) -> None:
        path = folder / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            cur = path.read_text(encoding="utf-8", errors="replace")
            if cur == content:
                new_hashes[rel] = sha(content)
                return
            ours = (old_hashes.get(rel) == sha(cur)) or (
                rel not in old_hashes and rel in MARKERS and MARKERS[rel] in cur[:400])
            if not ours:
                old = path.with_name(f"{path.name}.old-{stamp}")
                shutil.copy2(path, old)
                result.kept_old.append(str(old))
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        new_hashes[rel] = sha(content)
        result.written.append(rel)

    # jasp/: the downloaded prompts
    write_text("jasp/system-prompt.md", prompts.system + "\n")
    if prompts.annotate is not None:
        write_text("jasp/annotate-prompt.md", prompts.annotate + "\n")
    for slug, (name, prompt) in prompts.personas.items():
        write_text(f"jasp/personas/{slug}.md", f"Persona: {name}\n\n{prompt.strip()}\n")
    src = [f"Downloaded from jasp-stats/jasp-desktop at {prompts.ref} (AGPL-3.0).",
           "Files: Desktop/utilities/settings.cpp, Resources/defaultPersonas.json"]
    src += [f"Note: {n}" for n in prompts.notes]
    write_text("jasp/source.txt", "\n".join(src) + "\n")

    write_text("AGENTS.md", agents_md(prompts, persona))
    claude_md = folder / "CLAUDE.md"
    if claude_md.exists() and "@AGENTS.md" in claude_md.read_text(encoding="utf-8", errors="replace"):
        pass  # yours or ours: either way it already pulls in AGENTS.md
    else:
        write_text("CLAUDE.md", template("claude-md.txt"))
    ann = annotate_md(prompts)
    if ann is not None:
        write_text(".claude/commands/annotate.md", ann)
    write_text(".codex/config.toml", codex_config(uvx, host, port, careful))

    # JSON settings: merged, so anything else in them stays
    mcp_path = folder / ".mcp.json"
    mcp = _load_json(mcp_path, result, stamp)
    servers = dict(mcp.get("mcpServers") or {})
    servers["jasp"] = mcp_server(uvx, host, port)
    mcp["mcpServers"] = servers
    _write_json(mcp_path, mcp)
    result.written.append(".mcp.json")

    settings_path = folder / ".claude" / "settings.json"
    settings = _load_json(settings_path, result, stamp)
    rules = plot_rules(plot_dirs, home, platform)
    if isinstance(manifest, dict) and "claude_model" in manifest:
        was_ours = settings.get("model") == manifest.get("claude_model") and "model" in settings
    else:  # no manifest: the old setup.sh always wrote "opus"
        was_ours = settings.get("model") == "opus"
    _write_json(settings_path, merge_claude_settings(settings, careful, rules, claude_model, was_ours))
    result.written.append(".claude/settings.json")

    _write_json(manifest_path, {"full_fat": __version__, "jasp_ref": prompts.ref, "persona": persona,
                                "careful": careful, "host": host, "port": port, "claude_model": claude_model,
                                "files": new_hashes})
    return result


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def read_manifest(folder: Path) -> dict:
    try:
        data = json.loads((Path(folder) / MANIFEST).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def missing_files(folder: Path) -> list[str]:
    need = ["AGENTS.md", "CLAUDE.md", ".mcp.json", ".claude/settings.json", ".codex/config.toml"]
    return [n for n in need if not (Path(folder) / n).is_file()]
