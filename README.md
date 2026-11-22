# Full Fat

Full Fat lets you talk to Claude or ChatGPT about your JASP analyses, using a subscription you already pay
for (Claude Pro or Max through Claude Code, or ChatGPT Plus or Pro through Codex). The chat inside JASP needs a
paid API key or uses small free models. With Full Fat, the full models read your data and results, run
analyses and write annotations in JASP through JASP's own connection for AI apps (its MCP server). Full Fat is
a setup tool: it downloads JASP's own AI instructions for the JASP version you have, makes a chat folder plus a
"Full Fat" icon on your Desktop, and opens JASP with that connection switched on whenever you start a chat.

```
$ full-fat
Full Fat sets up a chat with Claude or ChatGPT that can see and work with JASP.
It uses the subscription you already pay for. It asks a few simple questions on the way.

== JASP
  OK: JASP found (it reports version 0.99.0; use --jasp-version if that is wrong).
  OK: JASP is ready. Full Fat switches on its connection for chats only while it opens JASP for you.

== Chat app
Which do you pay for?
  1) Claude (Pro or Max)
  2) ChatGPT (Plus or Pro)
  3) Both
Type a number and press Enter [1]: 1
  OK: Claude Code is installed.
  OK: You are signed in to Claude Code.

== Chat folder
  OK: Chat folder ready: /Users/you/Full Fat (JASP instructions from v0.99.0, persona alfred).
  Getting the link between the chat and JASP ready (the first time this takes a minute)...
  OK: The chat can reach JASP's tools.
  OK: "Full Fat" icon: /Users/you/Desktop/Full Fat.command

== Done
To chat about your JASP work:
  Double-click "Full Fat" on your Desktop.
  Full Fat opens JASP for you. If JASP is already open, it may ask you to close it first, so save your
  work in JASP before you start.
The first time you start a chat:
  - Claude shows a few welcome screens (for example a choice of colours). Press Enter on each.
  - Claude asks whether you trust the chat folder. Press the Down arrow once, so that "Yes, I trust this
  folder" is picked, then press Enter. (Enter alone picks "No, exit".)
  - Before the chat loads a data file, or writes a report or an annotation into JASP, it asks you. To let
  it, choose the first option ("Yes" in Claude, "Allow" in ChatGPT) and press Enter.
  - If your Mac offers to install "command line developer tools", click Cancel. The chat doesn't need them.
Start a chat now? [Y/n]
```

## Features

- **One install line, then plain questions.** It installs what is missing (uv, and, when you say yes, Claude
  Code or Codex with the provider's own installer), starts the sign-in, and never asks you to edit a file.
- **Opens JASP connected.** It finds JASP's settings on Linux (also Flatpak), Windows (also the Microsoft Store
  version) and macOS and makes a backup. When you start a chat it switches JASP's connection for AI apps on,
  opens JASP, and switches the setting off again as soon as JASP answers. If JASP is open without the
  connection, it asks you to close it and waits.
- **JASP's own instructions.** The system prompt, the annotation prompt and the personas (Alfred, Socrates,
  Evelyn) come from JASP's source for the version you have installed, so the chat behaves like JASP's own
  assistant. `/annotate` in Claude Code writes an annotation into the JASP output.
- **"Full Fat" icon.** It opens JASP connected (or reconnects to it), then starts the chat with a short
  greeting that says what you can ask.
- **Top model at high effort from the start**: Claude Opus in Claude Code, GPT-6.2 Astra in Codex. A model
  you pick with `/model` and save as your default is kept for the next chats.
- **Analyses without asking, the rest asks first.** Creating and running analyses and reading results run
  without asking, as in JASP's own assistant. Writing a report or an annotation, recombining results and
  loading a data file ask first. `--careful` makes it ask before every change to JASP.
- **`full-fat doctor`** checks everything and says how to fix each problem. `full-fat uninstall` removes the
  icon and the files Full Fat made in the chat folder, and puts JASP's setting back.
- **Safe to run again.** It updates the chat folder without deleting anything you put there.

## Install

You need JASP 0.98 or newer ([download](https://jasp-stats.org/download/)) and a Claude Pro or Max, or ChatGPT
Plus or Pro, subscription.

### Windows

1. Press the Windows key, type `PowerShell` and press Enter. A window with text opens.
2. Copy this whole line, paste it into that window (right-click pastes) and press Enter:

   ```
   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/onetrickpony1/full-fat/main/install.ps1 | iex"
   ```
3. Answer the questions.

If someone gave you `install.cmd`, you can double-click it instead. Windows may warn that it comes from the
internet or that it "protected your PC": click More info, then Run anyway.

### macOS

1. Press Cmd+Space, type `Terminal` and press Return. A window with text opens.
2. Copy this whole line, paste it into that window (Cmd+V) and press Return:

   ```
   curl -LsSf https://raw.githubusercontent.com/onetrickpony1/full-fat/main/install.sh | sh
   ```
3. Answer the questions. When your Mac asks whether Terminal may use your Desktop folder, click Allow.

### Linux

```
curl -LsSf https://raw.githubusercontent.com/onetrickpony1/full-fat/main/install.sh | sh
```

Running the same line again updates Full Fat and runs the setup again.

## Use

### For friends: 3 steps

1. **Install.** Follow the steps under Install for your computer, and answer the questions.
2. **Sign in.** When it says so, a browser window opens. Sign in with your Claude or ChatGPT account (the one
   you pay for), allow access, and go back to the window with text.
3. **Chat.** Double-click "Full Fat" on your Desktop. It opens JASP for you (the first time, JASP asks about
   checking for updates: answer it). If JASP is already open, Full Fat may ask you to close it first (on a
   Mac: Cmd+Q in JASP), so save your work. The first time, press Enter on Claude's welcome screens. When
   Claude asks whether you trust the folder, press the Down arrow once ("Yes, I trust this folder"), then
   Enter. Then type your questions, for example "What analysis fits my data?" or "Explain the t-test
   results". Before the chat loads a data file, or writes a report or an annotation into JASP, it asks: choose
   the first option ("Yes" in Claude, "Allow" in ChatGPT) and press Enter.

Close the window when you are done. Everything the chat creates is in JASP's results.

### Commands

```
full-fat                  set up, or update (same as full-fat setup)
full-fat launch           open JASP connected, then start the chat (the icon runs this)
full-fat doctor           check everything and say how to fix problems
full-fat uninstall        remove the icon and Full Fat's files, put JASP's setting back
```

Setup options:

```
--app claude|codex|both   which chat app to set up (asked if not given)
--persona NAME            JASP persona: alfred (default), socrates, evelyn or none
--careful / --no-careful  ask before every change to JASP (remembered)
--dir DIR                 chat folder (default "~/Full Fat")
--jasp-version X.Y.Z      use these JASP instructions instead of the installed version's
--yes                     ask nothing and never wait (for scripts); never installs the chat apps
--install-apps            install Claude Code or Codex without asking, also with --yes
--no-install-apps, --no-sign-in, --no-launcher, --no-trust, --no-start
```

You can also open the chat folder yourself: `cd "$HOME/Full Fat"` (the quotes matter, because of the space),
then `claude` or `codex`. Started that way, the chat can't reach JASP unless JASP was opened by the Full Fat
icon. In Claude Code, `/model` and `/effort` change the model and effort. In Codex, `/model` does both.
`full-fat` works in any Terminal window opened after the install. Setup prints the full path to use in the
window it ran in.

## Notes

- **JASP versions.** JASP 0.98.0 was the first with the connection for AI apps and the AI prompts. Older versions
  are refused with a link to the download page. A version with no release tag (a nightly) uses the newest
  instructions from JASP's development branch. Full Fat uses the version JASP reports, which can be behind: on
  Linux the Flatpak version of JASP can report an older version than it is. Use `--jasp-version` to set it.
- **JASP's first start** asks whether it should check for updates. Answer it: JASP only connects to the chat
  after that. Full Fat reminds you when you start a chat.
- **What changes in JASP.** Only one setting: `rpcServerEnabled`, the "Enable MCP server" box under
  Preferences > AI > MCP. Full Fat switches JASP's AI link on only while a Full Fat chat has JASP open,
  because while it is on, other programs on the computer can reach JASP. JASP reads the setting once, when
  it starts, so Full Fat switches it on, opens JASP, and switches it off again as soon as JASP answers. That
  JASP stays connected until you close it, and JASP opened in the usual way has no connection. If you had
  ticked the box yourself before Full Fat, it stays on. A backup of JASP's settings is kept in Full Fat's
  own folder, and `full-fat uninstall` puts the old value back.
- **Which tools ask.** Without asking: creating and running analyses, and reading data, analyses and results.
  Always asking: writing a report (`write_report`), writing an annotation (`analysis_createAnnotation`),
  recombining results (`analysis_composeResults`) and loading a data file (`data_load`). With `--careful`,
  everything that changes JASP asks. In Claude Code the folder sets the "default" permission mode, so these
  questions appear even where Claude Code would otherwise start in its automatic mode, and shell commands and
  file edits are switched off. In Codex, the shell tool and web search are off, the folder is read-only and
  `approval_policy` is "on-request", so Codex asks before it changes a file. Codex uses its documented per-tool
  approvals (`default_tools_approval_mode`, `tools.<tool>.approval_mode`) with `approvals_reviewer = "user"`,
  so you answer, not Codex's automatic reviewer
  ([config reference](https://developers.openai.com/codex/config-reference)). Codex can still look at image
  files (its `view_image` tool, which it needs to see JASP's plots): its settings can switch that on or off,
  but not limit it to some folders.
- **Models.** The icon starts the chat on Opus (Claude Code) or GPT-6.2 Astra (Codex) at high effort, by
  passing them when it starts the app. It leaves them out when your own settings already choose a model or
  an effort: when you pick a model with `/model` in Claude Code, Claude saves it as your default, and the
  next chats use it. Each chat starts at high effort unless Claude Code's settings set an effort level. The
  chat folder's own settings don't set a model, so they never override yours. High effort on the top model
  uses a plan's limits faster: if you hit your limit, type `/model` to pick a lighter model or `/effort` to
  lower the effort. If Codex says your plan can't use its model, type `/model` and pick another one.
- **Folder trust.** Codex only uses the folder's settings when the folder is trusted, so setup adds a trust
  entry for the chat folder to `~/.codex/config.toml` (and nothing else), and `full-fat uninstall` removes it
  again. Claude Code has no supported way to do that, so it asks once. Its question starts on "No, exit":
  press the Down arrow, then Enter.
- **Tested on** Linux (JASP 0.98.1 Flatpak) with Claude Code and Codex. Nobody has tried Full Fat on a real
  Windows PC or Mac yet. What CI checks, on every push:
  - unit tests on Linux, macOS and Windows (Python 3.11 and the newest);
  - the install lines (`install.sh`, `install.ps1`, from the checked-out code, not the published link), with
    git hidden as on a new computer, a stand-in JASP settings file, stand-in chat apps and `--yes`; then the
    icon starts a stand-in chat app in the chat folder, `full-fat doctor` must pass, and uninstall must leave
    nothing behind. `install.cmd` is not run;
  - on macOS (Apple Silicon) and Windows, the real JASP 0.99.0 is installed and its first-start question
    answered ahead. `full-fat launch` switches the connection on and JASP starts with it (on macOS Full Fat
    opens JASP; on Windows CI opens the ZIP copy while Full Fat waits), and jasp-mcp talks to it. The setting must
    be off again on disk while JASP still answers, and a second JASP start without Full Fat must have no
    connection. The chat app is a stand-in;
  - on an Intel Mac, the connector starts (its packages install there).
- **Not affiliated with JASP.** Full Fat is not made or endorsed by the JASP team. JASP's prompts are
  downloaded from [jasp-stats/jasp-desktop](https://github.com/jasp-stats/jasp-desktop) (AGPL-3.0) when you
  run setup. The connector is the official [jasp-mcp](https://github.com/jasp-stats/jasp-mcp), pinned to a
  tested commit. See [LEGAL.md](LEGAL.md).

## License

GPL-3.0-or-later. See [LICENSE](LICENSE) and [LEGAL.md](LEGAL.md).
