# Full Fat: notes for AI assistants

Project-specific rules. General repo rules are in the owner's conventions file.

## Ground rules (never change these)

- **Never put JASP's prompts in this repository.** They are AGPL-3.0 text from jasp-stats/jasp-desktop. They are
  downloaded at setup time (`src/full_fat/prompts.py`) into the user's chat folder, with `jasp/source.txt`
  saying where they came from. Test fixtures use made-up text shaped like JASP's.
- **JASP's connection setting is on only while Full Fat opens JASP** (`link.py`). While `rpcServerEnabled` is on,
  any program on the computer can reach JASP, so it must never stay on. `full-fat launch` switches it on, starts
  JASP, waits until JASP answers, and switches it off again, also when it fails or is stopped (`cli.connect`'s
  `finally`). Setup only backs up JASP's settings, records the original value and leaves it off. A user who had
  it on before Full Fat keeps it (`link.users_own`). Only the key `rpcServerEnabled` is ever changed. Changing it
  while JASP runs is safe: JASP reads it once at start-up and writes back only keys it changed itself (see the
  end of `jasp.py`'s docstring for the source lines). On macOS go through `defaults` (cfprefsd caches plists).
  Never describe what an open connection could be used for in any public file, commit or log; the README and
  LEGAL say only that other programs on the computer can reach JASP while it is on.
- **Full Fat never handles logins or tokens.** Sign-in is the apps' own (`claude auth login`, `codex login`);
  Full Fat reads their exit codes (`claude auth status`, `codex login status`), and from Claude's status only
  the kind of sign-in (`authMethod`, `apiProvider`), never names, emails or tokens.
- **Never wipe user files.** A rerun merges `.mcp.json` and `.claude/settings.json`, and keeps an edited text file
  as `<name>.old-<date>`. `.full-fat.json` holds the hashes of what Full Fat wrote. Folders made by the old
  `setup.sh` (no manifest) are recognised by `workspace.MARKERS`. Uninstall touches only a folder with a
  manifest, deletes only listed files whose hash still matches, then the folders it made if they are empty.
  Questions that delete or install take closed input as No (`ui.yes_no(on_eof=False)`).
- **Nothing is installed without a yes.** `--yes` and the installer's no-terminal fallback never install Claude
  Code or Codex; `--install-apps` is the explicit switch. Setup exits 1 (not "Done") when no chat app is ready.
- **Settings files keep their form.** Writes to `~/.codex/config.toml` and JASP's INI go through symlinks to the
  real file, keep its permissions and its line endings (`apps.write_keep`, `jasp._atomic_write`). Removing the
  trust block is refused when keys follow it in its table.
- **Codex trust**: only append a `[projects."<chat folder>"]` table to `~/.codex/config.toml` when there is no
  entry for that folder, the file parses and the new text parses too. Never touch other entries. Uninstall
  removes exactly the block Full Fat appended (state key `codex_trust_added`). Claude Code has no supported trust
  setting, so don't edit `~/.claude.json`.
- **The chat folder's name has a space** (`Full Fat`). Quote it in every script and command, and wrap paths in
  `ui.keep()` in messages, or the line wrapping splits them.
- **Launchers are only removed or replaced if the state key `launchers` records them** and they still hold
  Full Fat's mark (`launcher.MARKS`; a Windows `.lnk` holds it in its UTF-16 description). Icon pictures
  Full Fat installs (Linux hicolor PNGs, the Windows `.ico`) are recorded there too and removed only while they
  are byte for byte Full Fat's. Never look for launchers by name.
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
  out while uvx downloads about 30 packages. Setup fails (exit 1) if that fails, with a message from
  `connector.explain`.
- **Compiled packages come only as wheels** (`workspace.WHEEL_ONLY`, `--no-build-package` for each): cryptography
  50.0.2 has no Intel Mac wheel, and building it needs Rust. uvx has no `--only-binary`, and `--no-build` would
  also refuse to build jasp-mcp's own source archive. CI's `connector-intel-mac` job checks it.
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
- The server starts at the end of the main window's constructor (`Desktop/mainwindow.cpp` v0.99.0 line 216), after
  `checkForUpdates()` (224-244), which on first start shows a blocking "Check for updates" dialog
  (`checkUpdatesAskUser`, default true). Until the user answers, JASP does not answer on its port. Full Fat tells the
  user; it does not change that setting. CI pre-answers it (found by `e2e-macos` on 2026-11-22).
- Windows program `JASPDesktop.exe` (`Desktop/CMakeLists.txt` v0.99.0 line 103); MSIX package names in
  `Tools/windows/msix/AppxManifest-*.xml.in`; macOS `Tools/macOS/Info.plist.in` (CFBundleVersion is the full version,
  CFBundleShortVersionString only major.minor).

Researched from source but **not tried on a real machine**: everything Windows and macOS (paths, MSIX redirection
under `%LOCALAPPDATA%\Packages\<family>\LocalCache`, the `org.jasp-stats.JASP` defaults domain, version detection).
What CI proves, and only this:
- `test`: the unit tests on three systems.
- `installer`: `install.sh` / `install.ps1` from the checked-out code (`FULL_FAT_SOURCE`, not the published
  link), git hidden, stand-in JASP settings, stand-in chat apps (`tests/make_stand_in_apps.py`), `--yes`. The
  icon starts a stand-in chat in the folder (a fake JASP answers the ping; on Windows through the shortcut's
  target), `doctor` must exit 0, uninstall must leave nothing (the Linux carton and the Windows shortcut too). `install.cmd` is not run.
- `connector-intel-mac`: setup's connector start on an Intel Mac.
- `e2e-macos` (Apple Silicon) and `e2e-windows`: the real JASP 0.99.0, first-start dialog pre-answered.
  `full-fat launch` switches the setting on and JASP starts with its connection (macOS: Full Fat opens it;
  Windows ZIP: CI opens it while Full Fat waits). Then `tests/e2e_check_link.py`: the setting is off on disk while
  JASP answers; after JASP quits it is still off; JASP started again without Full Fat never answers. jasp-mcp talks
  to JASP, the double-clicked icon starts the stand-in chat, `doctor` must exit 0. No real Claude or Codex.
- Flatpak JASP can report an older version than it is (its appdata file lags), so the version is never treated as
  certain; `--jasp-version` overrides it.

## Generated files (the user's chat folder, default "~/Full Fat")

- `AGENTS.md`: `templates/environment.md` + JASP's system prompt + "Persona Prompt:", "  Your name is: <name>" and
  the persona indented two spaces, exactly as `aiBridge.cpp` (v0.98.1 569-590) builds it.
- `CLAUDE.md`: `@AGENTS.md`, from `templates/claude-md.txt` (the repo itself must not have a CLAUDE.md).
- `.mcp.json`: starts jasp-mcp for Claude Code.
- `.claude/settings.json`: `enabledMcpjsonServers: [jasp]`, `MAX_MCP_OUTPUT_TOKENS` 100000,
  `permissions.defaultMode` "default" (fresh Claude Code 2.1.330 otherwise starts the folder in auto mode, which
  approves tools itself), allow `workspace.run_tools()` (`DEFAULT_TOOLS`, careful: `READ_ONLY_TOOLS`) and Read on
  JASP's plot folders, ask for every other JASP tool, deny Bash/PowerShell/Edit/Write/NotebookEdit. **No model or
  effortLevel**: project settings override what `/model` saves to the user's settings. `apps.launch_command`
  passes `--model opus --effort high` (Codex: `-m gpt-6.2-astra -c model_reasoning_effort="high"`) only when no
  user or folder settings file sets them. Values an earlier Full Fat wrote are removed on rerun.
- Tools that ask in every mode: `workspace.ASKING_TOOLS` (`write_report`, `analysis_createAnnotation`,
  `analysis_composeResults`, `data_load`). They put text into JASP's results page or replace JASP's data
  (`data_load` opens any file path, `Desktop/mainwindow.cpp` 1460). `JASP_ASSISTANT_TOOLS` is every method in JASP's
  `Resources/JASP_Capabilities.json` (`Desktop/gui/aipersonamodel.cpp` v0.98.1 402-433); everything there except the
  asking tools runs without asking.
- `.claude/commands/annotate.md`: `/annotate` with JASP's annotation prompt.
- `.codex/config.toml`: no model (see above) but `model_reasoning_effort = "high"`, because the ChatGPT app gets
  no command-line options (this wins over an effort in the user's own config; the in-chat picker still changes
  it per chat). Read-only sandbox, `approval_policy = "on-request"`,
  `features.shell_tool = false`, `web_search = "disabled"` (removes `web__run` from code mode, checked with Codex
  0.169), `approvals_reviewer = "user"` (a user-level `guardian_subagent` reviewer would otherwise approve for them).
  `view_image` stays: `features.view_image` can only switch it off, not limit its folders, and Codex needs it to
  see plots. Then
  `mcp_servers.jasp` with `default_tools_approval_mode = "prompt"` and `tools.<tool>.approval_mode = "approve"` for
  `run_tools()`. Keys from https://developers.openai.com/codex/config-reference
  (now served at learn.chatgpt.com/docs/config-file/config-reference), checked with Codex 0.169: "prompt" blocks
  in `codex exec`, "approve" runs, and the project file's `approvals_reviewer` is honoured.
  At the end, the ChatGPT app's extra tools are off: `features.apps = false`, `[mcp_servers.node_repl]` with
  `enabled = false` **and a placeholder `command`** (without one, Codex 0.169 refuses the whole file with
  "invalid transport" where the app isn't installed), and `[plugins."<name>"] enabled = false` for
  `workspace.DESKTOP_PLUGINS_OFF`. Checked with Codex 0.169 (bundled with chatgpt-bin 26.1111): `codex mcp list`
  and app-server `config/read` load the file with an empty CODEX_HOME and with the app's own config, and a chat
  opened in the app had none of those tools and ran at high effort.
- `jasp/`: the downloaded prompts and `source.txt`. `.full-fat.json`: the manifest.
- `plots/` (only while or after a browser chat): copies of JASP's plot PNGs, made by `plots.Copier` in the
  Remote Control helper (`remote.watch`), at their path below JASP's temp folder (`.../temp/4/resources/1/x.png`
  becomes `plots/4/resources/1/x.png`). `plots/.full-fat-plots.json` lists them with hashes. Never a symlink,
  never over a file Full Fat didn't copy. The next browser chat and uninstall delete unchanged copies. Checked
  in claude.ai/code on 2026-11-23: a link to a real file in the folder opens (relative or absolute path); JASP's
  own path shows "Couldn't load this file"; a symlink in the folder does nothing, and Read asks for it as
  outside the folder. So copy, don't link, and don't widen Claude's write access. `templates/environment.md`
  tells the assistant to read the copy and link to it.

## The ChatGPT app route

The ChatGPT desktop app has a ChatGPT side and a Codex side. Only the Codex side uses the folder's
`.codex/config.toml` and `AGENTS.md` (the ChatGPT side asks before every JASP tool and searches the web). With
state `chatgpt_in = "app"` (setup's default when `apps.desktop_app_found()`), `full-fat launch` does the usual
`connect` (link on, JASP, ping, link off) and only then opens `apps.deep_link()` with `apps.open_desktop_app()`.
Not found or not opened: the Terminal chat, as before. The app route doesn't need the Codex CLI or its sign-in.
- The `prompt` parameter only fills the message box: the user presses Enter (checked on Linux). Say so.
- "Approve for me" in the app uses an automatic reviewer that overrides `approvals_reviewer = "user"`. The
  owner accepted this for the app route; the Terminal route still asks the user.
- JASP is started in its own session and the app by the system, so closing the Terminal afterwards stops
  nothing. Launch waits for Enter so a Linux or Windows window doesn't vanish before it can be read.
- Tried on Linux only (chatgpt-bin 26.1111). macOS and Windows detection is from documentation and the
  platforms' usual link registration, not from a real machine. Tests set `FULL_FAT_CHATGPT_APP=none` so the
  real app is never opened.

## Claude in the browser (Remote Control)

State `claude_in` ("browser", the default, or "terminal"; `--open-in browser|terminal`, and `--open-in
terminal` also sets `chatgpt_in`). `full-fat launch` adds `--remote-control "Full Fat"` before the greeting
when `remote.unavailable()` says yes: no API-key or provider variables, `claude auth status` JSON with
`authMethod` "claude.ai" and `apiProvider` "firstParty" (only those two fields are read), and `--remote-control`
in `claude --help`. Otherwise the chat stays in the Terminal with a plain message. Checked with Claude Code
2.1.330 (Max): the session is listed as "Full Fat" at claude.ai/code, approvals are buttons there, `/exit`
archives it, closing the Terminal ends it, and the flag left `remoteEnabled` (Claude's "all sessions" setting)
false.
- Opening the browser: Full Fat execs Claude Code (same PID), so just before that `remote.start_detached` double
  forks a helper that polls `<CLAUDE_CONFIG_DIR or ~/.claude>/sessions/<pid>.json` for `bridgeSessionId` and
  opens `https://claude.ai/code/<id>` with the system's opener, then exits with Claude Code. That file is
  Claude Code's internal record: if it changes, nothing opens and the Terminal text says where to look. Reading
  Claude's printed link instead would need a pty proxy between Claude Code and the Terminal. Windows uses a
  thread while Full Fat waits for Claude Code.
- A session record only exists for a top-level Claude Code: started from inside another Claude Code session
  (CLAUDECODE and friends set), none is written. Unset those variables for a live test.
- The browser opens in the default browser. If that browser isn't signed in to claude.ai it shows a sign-in
  page, so the Terminal text always says to sign in and where to find the chat.

## Code

- `cli.py`: the commands (setup, launch, doctor, uninstall) and every message. `ui.py`: questions, `--yes`.
  `link.py`: JASP's connection setting (on only while Full Fat opens JASP). `apps.py` also finds and opens the
  ChatGPT desktop app.
- `jasp.py`: detection per OS, the INI editor and the `Store` (INI file or macOS defaults domain), running and ping.
- The icon: `assets/icon/` has the SVG sources, their generators and Inter's licence (the "FF" outlines are
  Inter Black, OFL 1.1). `python3 -I assets/icon/build.py` (rsvg-convert, magick) writes `src/full_fat/icons/`
  (PNGs, `.ico`, `.icns`), which ships as package data. Linux: hicolor PNGs, `Icon=` is the absolute path of
  the 256 one. Windows: `Full Fat.lnk` on the Desktop (PowerShell WScript.Shell, paths passed as environment
  variables) opening `Full Fat.cmd` and the `.ico` in `state.config_dir()`; `.cmd` on the Desktop if that
  fails. macOS: NSWorkspace `setIcon` through `osascript -l JavaScript`, which nobody has seen work on a real
  Mac yet (CI only prints the file's extended attributes).
- `prompts.py`: download and C++ string literal parsing. `workspace.py`: the chat folder. `apps.py`: Claude Code
  and Codex. `launcher.py`: the Full Fat icon. `state.py`: Full Fat's own folder (answers, backups).

## Tests

`pip install -e ".[test]"`, then `pytest -q` (offline). `pytest -m network` fetches the real prompts for every
0.98.x tag, 0.99.0 and development. `python tests/e2e_check_jasp.py "$HOME/Full Fat"` checks a running JASP read-only.
Default arguments must not capture `jasp.running` or `jasp.ping` at import time: tests monkeypatch them.

## Choices that look like mistakes

- **No `install.command`** for Macs, although the conventions prefer a double-click installer: a browser
  download loses the executable bit (and gets quarantined), so a downloaded `.command` won't run. The Terminal
  line works on every Mac.
- **The chat app gets a real terminal as its input** (`cli.real_terminal_input`): the install line runs setup
  with `< /dev/tty`, and on macOS programs that watch input with kqueue fail on the `/dev/tty` alias.
