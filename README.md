# Full Fat

Full Fat lets you talk to Claude or ChatGPT about your JASP analyses, using a subscription you already pay
for (Claude Pro or Max through Claude Code, or ChatGPT Plus or Pro through Codex). The chat inside JASP needs a
paid API key or uses small free models; with Full Fat the full models read your data and results, run
analyses and write annotations in JASP through JASP's own connection for AI apps (its MCP server). Full Fat is
a setup tool: it switches that connection on, downloads JASP's own AI instructions for the JASP version you
have, and makes a chat folder plus a "Talk to JASP" icon on your Desktop.

```
$ full-fat
Full Fat sets up a chat with Claude or ChatGPT that can see and work with JASP.

== JASP
  OK: JASP 0.99.0 found.
JASP is open. Full Fat needs to switch on one JASP setting, and that only works while JASP is closed.
  Save your work in JASP, then close JASP. Full Fat waits here until it has closed.
  OK: Switched on JASP's connection for AI apps.

== Chat app
Which do you pay for?
  1) Claude (Pro or Max)
  2) ChatGPT (Plus or Pro)
  3) Both
Type a number and press Enter [1]: 1
  OK: Claude Code is installed.
  OK: You are signed in to Claude Code.

== Chat folder
  OK: Chat folder ready: /Users/you/JASP-AI (JASP instructions from v0.99.0, persona alfred).
  OK: "Talk to JASP" icon: /Users/you/Desktop/Talk to JASP.command

== Done
To chat about your JASP work:
  1. Open JASP.
  2. Double-click "Talk to JASP" on your Desktop.
```

## Features

- **One install line, then plain questions.** It installs what is missing (uv, and Claude Code or Codex with
  the provider's own installer), starts the sign-in, and never asks you to edit a file.
- **Switches on JASP's connection for you.** It finds JASP's settings on Linux (also Flatpak), Windows (also
  the Microsoft Store version) and macOS, makes a backup, and only changes them while JASP is closed. If JASP
  is open it asks you to close it and waits.
- **JASP's own instructions.** The system prompt, the annotation prompt and the personas (Alfred, Socrates,
  Evelyn) come from JASP's source for the version you have installed, so the chat behaves like JASP's own
  assistant. `/annotate` in Claude Code writes an annotation into the JASP output.
- **"Talk to JASP" icon.** It checks that JASP is open and answering (and opens JASP or fixes the setting if
  not), then starts the chat with a short greeting that says what you can ask.
- **Strongest model at high effort** to start with (Claude Opus, GPT-6.2 Astra). Change it in the app.
- **Same freedom as JASP's own assistant.** The JASP tools run without asking, as they do in JASP. Shell
  commands and file edits are switched off in the chat folder. `--careful` makes it ask before every change
  to JASP instead.
- **`full-fat doctor`** checks everything and says how to fix each problem. `full-fat uninstall` removes the
  icon and chat folder and puts JASP's setting back.
- **Safe to run again.** It updates the chat folder without deleting anything you put there.

## Install

You need JASP 0.98 or newer ([download](https://jasp-stats.org/download/)) and a Claude Pro or Max, or ChatGPT
Plus or Pro, subscription.

### Windows

Double-click `install.cmd` (download it from this page), or open PowerShell and run:

```
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/onetrickpony1/full-fat/main/install.ps1 | iex"
```

### macOS

1. Press Cmd+Space, type `Terminal` and press Return. A window with text opens.
2. Copy this whole line, paste it into that window (Cmd+V) and press Return:

   ```
   curl -LsSf https://raw.githubusercontent.com/onetrickpony1/full-fat/main/install.sh | sh
   ```
3. Answer the questions. When your Mac asks whether Terminal may use your Desktop folder, click Allow.

You can also download `install.command` and double-click it. Downloaded scripts are often blocked by macOS
("Apple could not verify..."): then open System Settings > Privacy & Security, scroll down, click Open Anyway
and enter your password. If it says you don't have permission to open it, use the Terminal line above.

### Linux

```
curl -LsSf https://raw.githubusercontent.com/onetrickpony1/full-fat/main/install.sh | sh
```

Running the same line again updates Full Fat and runs the setup again.

## Use

### For friends: 3 steps

1. **Install.** Run the install line above (on a Mac: step by step in Terminal). Answer its questions.
2. **Sign in.** When it says so, a browser window opens. Sign in with your Claude or ChatGPT account (the one
   you pay for), allow access, and go back to the Terminal window.
3. **Chat.** Double-click "Talk to JASP" on your Desktop. The first time, Claude asks whether you trust the
   folder: press Enter. Then type your questions, for example "What analysis fits my data?" or "Explain the
   t-test results".

Close the window when you are done. Everything the chat creates is in JASP's results.

### Commands

```
full-fat                  set up, or update (same as full-fat setup)
full-fat launch           check JASP, then start the chat (the icon runs this)
full-fat doctor           check everything and say how to fix problems
full-fat uninstall        remove the icon and chat folder, put JASP's setting back
```

Setup options:

```
--app claude|codex|both   which chat app to set up (asked if not given)
--persona NAME            JASP persona: alfred (default), socrates, evelyn or none
--careful / --no-careful  ask before every change to JASP (remembered)
--dir DIR                 chat folder (default ~/JASP-AI)
--jasp-version X.Y.Z      use these JASP instructions instead of the installed version's
--yes                     ask nothing and never wait (for scripts)
--no-install-apps, --no-sign-in, --no-launcher, --no-trust, --no-start
```

You can also open the chat folder yourself: `cd ~/JASP-AI`, then `claude` or `codex`. In Claude Code, `/model`
and `/effort` change the model and effort. In Codex, `/model` does both.

## Notes

- **JASP versions.** JASP 0.98.0 was the first with the connection for AI apps and the AI prompts. Older versions
  are refused with a link to the download page. A version with no release tag (a nightly) uses the newest
  instructions from JASP's development branch.
- **What changes in JASP.** Only one setting: `rpcServerEnabled`, the "Enable MCP server" box under
  Preferences > AI > MCP. JASP reads it when it starts, so it has to restart once. A backup of JASP's settings
  is kept in Full Fat's own folder, and `full-fat uninstall` puts the old value back.
- **Approvals.** By default the JASP tools run without asking in both apps, as in JASP's own assistant (every
  shipped persona has all capabilities). With `--careful`, Claude Code asks before anything that changes JASP,
  and Codex does the same through its per-tool approval settings (`default_tools_approval_mode = "prompt"`
  with the reading tools set to `"approve"`, and `approvals_reviewer = "user"` so you answer, not Codex's
  automatic reviewer). Codex works in a read-only sandbox in this folder.
- **Folder trust.** Codex only uses the folder's settings when the folder is trusted, so setup adds a trust
  entry for the chat folder to `~/.codex/config.toml` (and nothing else). Claude Code has no supported way to
  do that, so it asks once.
- **Tested on** Linux (JASP 0.98.1 Flatpak) with Claude Code and Codex. Windows and macOS are checked only by
  CI: unit tests, the installers, and a job that installs the real JASP, opens it and talks to it through
  jasp-mcp. Nobody has tried them on a real Windows PC or Mac yet.
- **Not affiliated with JASP.** Full Fat is not made or endorsed by the JASP team. JASP's prompts are
  downloaded from [jasp-stats/jasp-desktop](https://github.com/jasp-stats/jasp-desktop) (AGPL-3.0) when you
  run setup. The connector is the official [jasp-mcp](https://github.com/jasp-stats/jasp-mcp), pinned to a
  tested commit. See [LEGAL.md](LEGAL.md).

## License

GPL-3.0-or-later. See [LICENSE](LICENSE) and [LEGAL.md](LEGAL.md).
