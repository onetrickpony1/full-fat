# Legal notice

This notice applies to Full Fat (the "Software"). By installing or running it, you accept it.

## 1. What Full Fat does

Full Fat is a setup tool that runs on your own computer. It:

- reads and changes one setting of JASP on your computer (`rpcServerEnabled`, the "Enable MCP server" option),
  after making a backup. Full Fat switches JASP's AI link on only while a Full Fat chat has JASP open, because
  while it is on, other programs on the computer can reach JASP: it switches the setting on, opens JASP, and
  switches it off again as soon as JASP answers. If you had switched it on yourself before, it stays on;
- downloads text from JASP's public source code on GitHub (the AI system prompt, the annotation prompt and the
  persona prompts in [jasp-stats/jasp-desktop](https://github.com/jasp-stats/jasp-desktop));
- writes configuration files for Claude Code and Codex CLI into a folder on your computer (`~/Full Fat` unless
  you choose another), and a "Full Fat" launcher icon. During a Claude chat in the browser it copies JASP's
  plot images into that folder. `full-fat uninstall` removes only the files it wrote;
- adds a trust entry for that folder to Codex's settings (`~/.codex/config.toml`) when you set up Codex;
- can run the official installers of Claude Code (Anthropic) and Codex CLI (OpenAI) when you answer yes (or
  when you run it with `--install-apps`), and their sign-in commands when you agree to it;
- starts Claude Code or Codex in that folder when you double-click the icon, and opens JASP for it. A Claude
  chat is started with Claude Code's Remote Control, so it is also shown on claude.ai/code in your browser,
  under your Claude account. Full Fat opens that page.

Everything that is downloaded, and from where:

- **uv**, from astral.sh (by the install line, if you don't have it), and **a Python build** that uv fetches
  for Full Fat if your computer has no suitable one;
- **Full Fat itself**, from this GitHub repository;
- **JASP's prompts**, from github.com/jasp-stats/jasp-desktop (raw.githubusercontent.com), at every setup;
- **jasp-mcp**, JASP's official connector, from github.com/jasp-stats/jasp-mcp at a fixed version, and the
  Python packages it needs, from the Python Package Index (pypi.org), when setup starts it for the first time;
- **Claude Code** from claude.ai and **Codex CLI** from chatgpt.com, through their official installers, only
  when you agree to install them. They then update themselves as their makers decide.

## 2. Not affiliated

Full Fat is an independent project. It is **not affiliated with, made by or endorsed by** the JASP team, the
University of Amsterdam, Anthropic or OpenAI. "JASP", "Claude", "ChatGPT" and "Codex" are
names of their owners, used here only to say what the Software works with.

## 3. JASP's text and software

JASP is licensed under the GNU Affero General Public License, version 3 (AGPL-3.0). The prompts Full Fat
downloads are part of JASP's source and stay under that licence. They are **not included in this repository**.
They are downloaded to your computer when you run setup, together with a note of where they came from.
jasp-mcp, the connector the chat apps start, is downloaded from
[jasp-stats/jasp-mcp](https://github.com/jasp-stats/jasp-mcp) under its own licence (MIT).

The "Full Fat" icon's "FF" letters are outlines from the Inter typeface by The Inter Project Authors, under the
SIL Open Font License 1.1 (`assets/icon/OFL-Inter.txt`, also installed with the icons).

## 4. Your subscriptions and accounts

You use your own Claude or ChatGPT subscription, under Anthropic's or OpenAI's terms. You are responsible for
following those terms. **Full Fat never handles your logins, passwords or tokens**: you sign in through the
providers' own apps, in their own browser pages, and Full Fat only asks those apps whether you are signed in
(and Claude Code whether that is a Claude account).

## 5. Your data

When you chat, Claude Code or Codex sends what you type, and what it reads from JASP (your data, analyses and
results), to Anthropic or OpenAI, as with any use of those apps. Check that you may share the data you open in
JASP with those services, for example under your institution's rules or a data protection agreement. Full Fat
itself sends nothing anywhere except the downloads in section 1.

## 6. No warranty, no liability

The Software is provided "as is", without warranty of any kind. The authors are not liable for any damage
arising from its use, including changes to JASP's settings, wrong or misleading output from AI models, or
analyses an AI app creates or changes in JASP. Check results yourself before you rely on them.

## 7. Licence

The Software is free software under the GNU General Public License, version 3 or (at your option) any later
version (see `LICENSE`). Section 6 restates sections 15 and 16 of the GPL. Nothing in this notice adds a
"further restriction" within the meaning of sections 7 and 10 of the GPL.
