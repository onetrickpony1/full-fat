# Changelog

## Unreleased

### Features
- **Works on Windows and macOS as well as Linux.** Setup is now a Python program (`full-fat`) installed with
  one line (`install.ps1`, `install.sh`) or a double-click (`install.cmd`, `install.command`). It finds JASP,
  its version and its settings on each system, including the Flatpak and Microsoft Store versions.
- **Guided setup in plain English.** It asks whether you pay for Claude or ChatGPT, installs Claude Code or
  Codex with the provider's own installer if needed, and starts the sign-in.
- **JASP's connection is switched on for you.** If JASP is open, setup asks you to close it and waits, then
  changes the one setting (with a backup).
- **"Talk to JASP" icon on the Desktop.** It checks that JASP is open and answering, opens JASP or fixes the
  setting if not, then starts the chat with a greeting that says what you can ask.
- **JASP tools run without asking**, as in JASP's own assistant. Shell commands and file edits are off in the
  chat folder. `--careful` asks before every change to JASP, in Claude Code and in Codex.
- **`full-fat doctor` and `full-fat uninstall`.** Doctor checks every part and says how to fix it. Uninstall
  removes the icon and the chat folder (asking first) and puts JASP's setting back.
- **Any JASP from 0.98.0.** Older versions are refused with a link to the download page. Nightlies use the
  newest instructions, and a missing prompt or persona file no longer stops setup.
- **Running setup again keeps your changes.** Settings files are merged, and a text file you edited is kept as
  `<name>.old-<date>` next to the new one.
