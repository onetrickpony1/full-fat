# Changelog

## Unreleased

### Features
- **Set up a chat with Claude or ChatGPT that works with JASP, on Windows, macOS and Linux.** One install line
  installs Full Fat and starts a guided setup. It asks whether you pay for Claude or ChatGPT, installs Claude
  Code or Codex with the provider's own installer if needed, and starts the sign-in.
- **JASP's connection for AI apps is switched on for you.** Setup finds JASP and its settings (also the
  Flatpak and Microsoft Store versions), asks you to close JASP if it is open and waits, then changes that one
  setting after making a backup.
- **JASP's own instructions and personas**, downloaded for the JASP version you have (0.98.0 or newer;
  nightlies use the newest ones). `/annotate` in Claude Code writes an annotation into the JASP output.
- **"Talk to JASP" icon on the Desktop.** It checks that JASP is open and answering, opens JASP or fixes the
  setting if not, then starts the chat with a greeting that says what you can ask.
- **The same tools as JASP's own assistant, without asking.** Loading a data file asks first, and
  `--careful` asks before every change to JASP. Shell commands are off in the chat folder.
- **Starts on the top model at high effort**: Opus in Claude Code, GPT-6.2 Astra in Codex.
- **`full-fat doctor` and `full-fat uninstall`.** Doctor checks every part and says how to fix it. Uninstall
  removes the icon and the chat folder (asking first), puts JASP's setting back and removes Codex's trust
  entry for the folder.
- **Safe to run again.** It updates the chat folder without deleting anything you added, and keeps your own
  version of any file it would replace.
