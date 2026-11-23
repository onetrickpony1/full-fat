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
- **Clear first-chat steps**: the trust question in Claude Code needs the Down arrow, then Enter, and the
  approval question before loading data or writing a report is answered with the first option.
- **Notices when JASP does not start.** If the JASP that Full Fat opened closes or crashes, it says so and asks
  you to open JASP yourself, instead of waiting.
- **`full-fat doctor` and `full-fat uninstall`.** Doctor checks every part and says how to fix it. Uninstall
  asks first, removes the icon and only the files Full Fat made in the chat folder (the folder too if nothing
  else is in it), puts JASP's setting back and removes Codex's trust entry for the folder. It never deletes a
  folder Full Fat did not make.
- **Leaves your settings files as they are.** Codex's and JASP's settings keep their line endings, their
  permissions and any link to where they really live.
- **The chat lives in a "Full Fat" folder in your home folder.** Use `--dir` to put it somewhere else.
- **Safe to run again.** It updates the chat folder without deleting anything you added, and keeps your own
  version of any file it would replace.
- **ChatGPT chats can open in the ChatGPT app.** Before, a ChatGPT chat always started in a Terminal window.
  Now, if the ChatGPT app is installed, setup suggests it, and the icon opens JASP and then a new chat on the
  app's Codex side in the chat folder, with the first message typed in. If the app is missing or doesn't open,
  the chat starts in the Terminal as before. `--open-in terminal` keeps the Terminal.
- **The "Full Fat" icon is a milk carton.** Before, it showed Terminal's or Command Prompt's icon. Now Linux
  shows the carton on the Desktop and in the applications menu, Windows gets a "Full Fat" shortcut with the
  carton, and on a Mac Full Fat sets it as the Finder icon. Uninstall removes the icon files too.
- **Claude chats also open in your web browser.** Before, a Claude chat was only in the Terminal window. Now
  it also opens at claude.ai/code, called "Full Fat", where you can read and type, with tables as tables
  and approval questions as buttons. The Terminal window keeps it running. If your Claude Code is too old or
  isn't signed in with a Claude account, or your plan's admin has switched this off, the chat stays in
  the Terminal as before (after a refusal Full Fat says so and starts the chat again there). This is the new
  default for everyone, also if you set up Full Fat before and don't run setup again. To keep Claude chats in
  the Terminal, run `full-fat setup --open-in terminal`, or `full-fat launch --open-in terminal` for one chat.
- **Plots show in the browser.** Before, a plot link in a Claude chat on claude.ai/code said "Couldn't load
  this file", because JASP keeps plots outside the chat folder. Now Full Fat copies JASP's plots into the
  chat folder's `plots` folder while the chat runs, and the chat links to the copy, which opens when you
  click it.

### Fixes
- **Codex chats in the ChatGPT app start at high effort and without the app's extra tools.** Before, a chat
  in the app ran at the effort saved in your own Codex settings (often medium) and could use the app's tools
  for running code, reading any file, the computer, the browser and connected apps. Now the chat folder's
  settings start every Codex chat at high effort and switch those tools off.
- **Ctrl+C in a chat on Windows stops only what the chat is doing.** Before, Ctrl+C also stopped Full Fat
  while the chat kept running in the same window, and Full Fat's "Press any key" message appeared over the
  chat. Now Full Fat leaves Ctrl+C to the chat app and waits until the chat ends.
