# Full Fat: notes for AI assistants

Project-specific rules. General repo rules are in the owner's conventions file.

## Ground rules (never change these)

- **Never put JASP's prompts in this repository.** They are AGPL-3.0 text from jasp-stats/jasp-desktop. They are
  downloaded at setup time (`src/full_fat/prompts.py`) into the user's chat folder, with `jasp/source.txt`
  saying where they came from. Test fixtures use made-up text shaped like JASP's.
- **JASP's settings are only changed while JASP is closed**, after a backup, and only the key `rpcServerEnabled`
  (`cli.switch_on`). JASP writes its whole settings file when it quits, so an edit made while it runs is lost or
  overwrites the user's changes. On macOS go through `defaults` (cfprefsd caches plists; editing the file
  directly can be lost). `--yes` never waits for JASP to close: it leaves the settings alone and says so.
- **Full Fat never handles logins or tokens.** Sign-in is the apps' own (`claude auth login`, `codex login`);
  Full Fat only reads their exit codes (`claude auth status`, `codex login status`).
- **Never wipe user files.** A rerun merges `.mcp.json` and `.claude/settings.json`, and keeps an edited text file
  as `<name>.old-<date>`. `.full-fat.json` holds the hashes of what Full Fat wrote. Folders made by the old
  `setup.sh` (no manifest) are recognised by `workspace.MARKERS`.
- **Codex trust**: only append a `[projects."<chat folder>"]` table to `~/.codex/config.toml` when there is no
  entry for that folder, the file parses and the new text parses too. Never touch other entries. Uninstall
  removes exactly the block Full Fat appended (state key `codex_trust_added`). Claude Code has no supported trust
  setting, so don't edit `~/.claude.json`.
- Plain English in every message a user sees. No "MCP", "RPC" or "config" in setup messages (README Notes and
  code comments may use them).

## jasp-mcp

Pinned to `72d9d7be9c003b9681b40871ee5850795108e5ab` (`workspace.JASP_MCP_SHA`) and run as
`uvx --with "mcp<2" --from "jasp-mcp @ https://github.com/jasp-stats/jasp-mcp/archive/<sha>.zip" jasp-mcp`.
- **Never use `git+https`**: it needs git, which new Macs and Windows PCs lack (on a Mac it opens Apple's
  "install developer tools" dialog). The archive builds with hatchling and no git. CI's installer job hides git
  to keep this true.
- jasp-mcp crashes with the MCP Python SDK 2.x (`'Server' object has no attribute 'list_tools'`), hence `mcp<2`.
- Setup starts the connector once (`connector.warm`: MCP `initialize`, then stop) so the first chat doesn't time
  out while uvx downloads about 30 packages. Setup fails (exit 1) if that fails.
- Before moving the pin, run `tests/e2e_check_jasp.py` against a running JASP. The uvx path is written as an
  absolute path when found, so the apps work even before the shell's PATH is updated.

## What JASP's source says (checked 2026-11-22 at v0.98.0, v0.98.1, v0.98.8, v0.99.0, development)

Use `git show <tag>:<path>` in a jasp-desktop clone. `jasp.py` and `prompts.py` cite these at the top.
- First version with the MCP server and AI prompts: **0.98.0** (v0.97.1 has neither). `jasp.MIN_VERSION`.
- Settings: `Desktop/main.cpp` (v0.98.1 424-440, v0.99.0 284-300) sets the Qt organisation/application
  (`JASP`/`JASP`, Windows MSIX `JASP-Stats-MSIX`/`JASPDesktop`, domain `jasp-stats.org`) and `IniFormat` on Windows.
  `Desktop/utilities/settings.cpp` v0.98.1 156-158 has the keys and defaults; 176-200 the Windows policy and
  legacy-registry order. Development adds `forced.json` and macOS managed preferences above the user's value.
- Plot folder: `Common/dirs.cpp` (tempDir, v0.98.1 52-104) is `AppLocalDataLocation/temp`.
- Prompts: `settings.cpp` entries `aiCommonSystemPrompt` and `aiAnnotationPrompt`; personas in
  `Resources/defaultPersonas.json`; JASP builds its system message in `Desktop/ai/aiBridge.cpp` (v0.98.1 569-590)
  and opens the chat with the hidden message "Give a short introduction." (line 312).
- Windows program `JASPDesktop.exe` (`Desktop/CMakeLists.txt` v0.99.0 line 103); MSIX package names in
  `Tools/windows/msix/AppxManifest-*.xml.in`; macOS `Tools/macOS/Info.plist.in` (CFBundleVersion is the full version,
  CFBundleShortVersionString only major.minor).

Researched from source but **not tried on a real machine**: everything Windows and macOS (paths, MSIX redirection
under `%LOCALAPPDATA%\Packages\<family>\LocalCache`, the `org.jasp-stats.JASP` defaults domain, version detection).
CI's `e2e-macos` and `e2e-windows` jobs are the only real check: they install the real JASP and talk to it.

## Generated files (the user's chat folder, default ~/JASP-AI)

- `AGENTS.md`: `templates/environment.md` + JASP's system prompt + "Persona Prompt:", "  Your name is: <name>" and
  the persona indented two spaces, exactly as `aiBridge.cpp` (v0.98.1 569-590) builds it.
- `CLAUDE.md`: `@AGENTS.md`, from `templates/claude-md.txt` (the repo itself must not have a CLAUDE.md).
- `.mcp.json`: starts jasp-mcp for Claude Code.
- `.claude/settings.json`: model opus only for Claude Max (Pro: no model, Claude Code's default; the plan comes
  from `claude auth status` subscriptionType, else asked, and is remembered), effortLevel high,
  `enabledMcpjsonServers: [jasp]`, `MAX_MCP_OUTPUT_TOKENS` 100000, allow `workspace.DEFAULT_TOOLS` (careful:
  `READ_ONLY_TOOLS`), Read on JASP's plot folders, deny Bash/PowerShell/Edit/Write/NotebookEdit.
- Tool parity: `JASP_ASSISTANT_TOOLS` is every method in JASP's `Resources/JASP_Capabilities.json`, which is what
  a persona with `enabledCapabilities ["*"]` gets (`Desktop/gui/aipersonamodel.cpp` v0.98.1 402-433). `write_report`
  only makes a report inside JASP (`Desktop/analysis/analyses.cpp` 1697). `data_load` opens any file path and replaces
  JASP's data (`Desktop/mainwindow.cpp` 1460) and is not in the capabilities, so it always asks, as does
  `analysis_composeResults`.
- `.claude/commands/annotate.md`: `/annotate` with JASP's annotation prompt.
- `.codex/config.toml`: model gpt-6.2-astra, effort high, read-only sandbox, `features.shell_tool = false`,
  `approvals_reviewer = "user"` (a user-level `guardian_subagent` reviewer would otherwise approve for them),
  `mcp_servers.jasp` with `default_tools_approval_mode = "prompt"` and `tools.<tool>.approval_mode = "approve"` for
  `DEFAULT_TOOLS` (careful: `READ_ONLY_TOOLS`). Keys from https://developers.openai.com/codex/config-reference
  (now served at learn.chatgpt.com/docs/config-file/config-reference), checked with Codex 0.169: "prompt" blocks
  in `codex exec`, "approve" runs, and the project file's `approvals_reviewer` is honoured.
- `jasp/`: the downloaded prompts and `source.txt`. `.full-fat.json`: the manifest.

## Code

- `cli.py`: the commands (setup, launch, doctor, uninstall) and every message. `ui.py`: questions, `--yes`.
- `jasp.py`: detection per OS, the INI editor and the `Store` (INI file or macOS defaults domain), running and ping.
- `prompts.py`: download and C++ string literal parsing. `workspace.py`: the chat folder. `apps.py`: Claude Code
  and Codex. `launcher.py`: the Talk to JASP icon. `state.py`: Full Fat's own folder (answers, backups).

## Tests

`pip install -e ".[test]"`, then `pytest -q` (offline). `pytest -m network` fetches the real prompts for every
0.98.x tag, 0.99.0 and development. `python tests/e2e_check_jasp.py ~/JASP-AI` checks a running JASP read-only.
Default arguments must not capture `jasp.running` or `jasp.ping` at import time: tests monkeypatch them.
