# Changelog

## Unreleased

### Features
- **Set up a chat with Claude or ChatGPT that works with JASP, on Windows, macOS and Linux.** One install line
  installs Full Fat and starts a guided setup. It asks whether you pay for Claude or ChatGPT, installs Claude
  Code or Codex with the provider's own installer if you say yes, and starts the sign-in. Setup only says it is
  done when a chat app is ready.
- **JASP opens connected when you start a chat, and its connection setting stays off otherwise.** Full Fat
  finds JASP and its settings (also the Flatpak and Microsoft Store versions) and backs them up. The icon
  switches JASP's connection for AI apps on, opens JASP, and switches the setting off again as soon as JASP
  answers, because while it is on other programs on the computer can reach JASP. If you had switched it on
  yourself, it stays on.
- **JASP's own instructions and personas**, downloaded for the JASP version you have (0.98.0 or newer;
  nightlies use the newest ones). `/annotate` in Claude Code writes an annotation into the JASP output.
- **"Full Fat" icon on the Desktop.** It opens JASP connected (or asks you to close a JASP that was opened
  without the connection), then starts the chat with a greeting that says what you can ask.
- **Analyses run without asking; reports, annotations and loading data ask first**, in Claude Code and Codex,
  also where Claude Code would otherwise start in its automatic mode. `--careful` asks before every change to
  JASP. Shell commands and web search are off in the chat folder.
- **Starts on the top model at high effort**: Opus in Claude Code, GPT-6.2 Astra in Codex. A model you save as
  your default with `/model` is kept for the next chats.
- **Works on Intel Macs**: the parts the chat needs to reach JASP are installed as ready-made packages.
- **Clear first-chat steps**: the trust question in Claude Code needs the Down arrow, then Enter.
- **`full-fat doctor` and `full-fat uninstall`.** Doctor checks every part and says how to fix it. Uninstall
  asks first, removes the icon and only the files Full Fat made in the chat folder (the folder too if nothing
  else is in it), puts JASP's setting back and removes Codex's trust entry for the folder. It never deletes a
  folder Full Fat did not make.
- **Leaves your settings files as they are.** Codex's and JASP's settings keep their line endings, their
  permissions and any link to where they really live.
- **The chat lives in a "Full Fat" folder in your home folder.** Use `--dir` to put it somewhere else.
- **Safe to run again.** It updates the chat folder without deleting anything you added, and keeps your own
  version of any file it would replace.
