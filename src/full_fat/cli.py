"""full-fat: chat with Claude or ChatGPT about your JASP analyses, using the subscription you already pay for."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.error
from pathlib import Path

from . import __version__, apps, connector, jasp, launcher, link, plots, prompts, remote, state, workspace
from .ui import UI, keep, waiting

GITHUB = "https://github.com/onetrickpony1/full-fat"


# ---------------------------------------------------------------------------- shared steps

def find_jasp(a, ui: UI) -> jasp.Jasp | None:
    while True:
        j = jasp.detect(a.settings_file, a.jasp_version)
        if j.found:
            return j
        ui.problem("Full Fat could not find JASP on this computer.")
        ui.say(f"  Download JASP from {jasp.DOWNLOAD_URL} , install it and open it once.")
        if not ui.enter("Press Enter when JASP is installed (or Ctrl+C to stop)."):
            return None


def check_version(j: jasp.Jasp, ui: UI) -> bool:
    ok = j.version_ok()
    need = prompts.version_string(jasp.MIN_VERSION)
    if ok is False:
        ui.problem(f"This JASP reports version {j.version}. Full Fat needs JASP {need} or newer, "
                   "which has the connection for AI apps.")
        ui.say(f"  Download the newest JASP from {jasp.DOWNLOAD_URL} , install it, then run this again.")
        return False
    if ok is None:
        ui.say(f"  Full Fat could not tell which JASP version this is. It needs JASP {need} or newer "
               "and will use the newest JASP instructions.")
    else:
        ui.ok(f"JASP found (it reports version {j.version}; use --jasp-version if that is wrong).")
    for n in j.notes:
        ui.say("  " + n)
    return True


GRACE = 15  # seconds JASP may take to show up as running after Full Fat opens it


def quit_hint() -> str:
    return "press Cmd+Q in JASP" if sys.platform == "darwin" else "close its window"


def prepare_link(j: jasp.Jasp, ui: UI) -> bool:
    """Setup's part: back up JASP's settings, note the original value, and leave the setting off."""
    store = j.write_store()
    if store is None:
        ui.problem("Full Fat could not find JASP's settings.")
        ui.say("  Run Full Fat again after opening and closing JASP once.")
        return False
    try:
        rec = link.remember(store)
        if link.users_own(rec):
            ui.ok("JASP's connection for chats was already switched on in JASP before Full Fat, so it stays on.")
            return True
        was_on = store.enabled()
        link.switch_off(store)
    except OSError as e:
        ui.problem(f"Full Fat could not read or change JASP's settings ({e}).")
        return False
    if was_on:
        ui.ok("Switched JASP's connection for chats off again. From now on Full Fat switches it on only while "
              "it opens JASP for a chat.")
    else:
        ui.ok("JASP is ready. Full Fat switches on its connection for chats only while it opens JASP for you.")
    return True


def chosen_apps(a, st: dict, ui: UI) -> list[str]:
    if a.app:
        return ["claude", "codex"] if a.app == "both" else [a.app]
    installed = [k for k, v in apps.APPS.items() if apps.find(v)]
    default = st.get("apps") or installed or ["claude"]
    if ui.yes:
        return default
    current = 3 if len(default) == 2 else (2 if default == ["codex"] else 1)
    n = ui.choose("Which do you pay for?", ["Claude (Pro or Max)", "ChatGPT (Plus or Pro)", "Both"], current)
    return [["claude"], ["codex"], ["claude", "codex"]][n - 1]


def chatgpt_place(a, st: dict, ui: UI) -> str:
    """Where a ChatGPT chat opens: "app" (the Codex side of the ChatGPT desktop app) or "terminal" (Codex)."""
    if getattr(a, "open_in", None) in ("app", "terminal"):
        return a.open_in
    if not apps.desktop_app_found():
        return "terminal"
    default = st.get("chatgpt_in") or "app"
    if ui.yes:
        return default
    n = ui.choose("The ChatGPT app is installed on this computer. Where do you want to chat with ChatGPT?",
                  ["In the ChatGPT app", "In a Terminal window like this one"], 1 if default == "app" else 2)
    return "app" if n == 1 else "terminal"


def claude_place(a, st: dict) -> str:
    """Where a Claude chat opens: "browser" (the Terminal and claude.ai/code, the default) or "terminal"."""
    if getattr(a, "open_in", None) in ("browser", "terminal"):
        return a.open_in
    return "terminal" if st.get("claude_in") == "terminal" else "browser"


def ensure_app(app: apps.App, ui: UI, may_install: bool, may_sign_in: bool, agreed: bool = False) -> str | None:
    """agreed: install without asking (--install-apps). Otherwise only a person's yes installs anything."""
    exe = apps.find(app)
    if not exe:
        provider = "Anthropic" if app.key == "claude" else "OpenAI"
        if not may_install:
            ui.problem(f"{app.product} is not installed. Run Full Fat setup again to install it.")
            return None
        if ui.yes and not agreed:
            ui.problem(f"{app.product} is not installed. Full Fat installs it only when you say so: run Full Fat "
                       "setup in a Terminal window and answer yes.")
            return None
        ui.say(f"To chat with {app.name.split(' (')[0]}, you need {app.product}, the free app from {provider} "
               "that you chat in.")
        if not agreed and not ui.yes_no(f"Install {app.product} now? It takes a minute or two.", True,
                                        on_eof=False):
            return None
        ui.say(f"Installing {app.product} with {provider}'s own installer...")
        if not apps.install(app):
            ui.problem(f"{app.product} could not be installed.")
            ui.say(f"  Install it by hand: {keep(app.install_windows if os.name == 'nt' else app.install_posix)}")
            return None
        exe = apps.find(app)
    ui.ok(f"{app.product} is installed.")
    if not may_sign_in:
        return exe
    s = apps.signed_in(app, exe)
    if s:
        ui.ok(f"You are signed in to {app.product}.")
    elif ui.yes:
        ui.say(f"  You are not signed in to {app.product} yet. Full Fat asks you to when you start a chat.")
    else:
        sign_in(app, exe, ui)
    return exe


def sign_in(app: apps.App, exe: str, ui: UI) -> bool:
    account = "Claude" if app.key == "claude" else "ChatGPT"
    ui.say(f"Now sign in with your {account} account (the one with your paid plan).")
    ui.say("  A browser window opens. Sign in there, allow access, then come back to this window.")
    ui.enter("Press Enter to open the sign-in page.")
    done = apps.sign_in(app, exe)
    if done:
        ui.ok(f"Signed in to {app.product}.")
    else:
        ui.problem(f"Not signed in to {app.product} yet. You can do it later: Full Fat asks again when you start a chat.")
    return done


def warm_connector(folder: Path, ui: UI) -> bool:
    import json  # noqa: PLC0415
    try:
        server = json.loads((folder / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["jasp"]
    except (OSError, ValueError, KeyError):
        return False
    ui.say("  Getting the link between the chat and JASP ready (the first time this takes a minute)...")
    ok, detail = connector.warm(server, folder)
    if ok:
        ui.ok("The chat can reach JASP's tools.")
    else:
        ui.problem("The part that lets the chat use JASP could not be prepared.")
        ui.say("  " + connector.explain(detail))
    return ok


def remove_launcher(recorded: str, ui: UI) -> bool:
    """Remove an icon that Full Fat's state records. False means it is still there to remove another time."""
    try:
        if launcher.remove(Path(recorded)):
            ui.ok(f"Removed {keep(recorded)}")
    except OSError as e:
        ui.problem(f"Could not remove {keep(recorded)}: {e}")
        return False
    return True


def pick_persona(wanted: str | None, p: prompts.Prompts, ui: UI) -> str:
    wanted = wanted or "alfred"
    if wanted == "none" or wanted in p.personas:
        return wanted
    fallback = next(iter(p.personas), "none")
    ui.say(f"  JASP has no persona '{wanted}' (it has: {', '.join(p.personas) or 'none'}), "
           f"so Full Fat uses {fallback}.")
    return fallback


# ---------------------------------------------------------------------------- setup

def cmd_setup(a, ui: UI) -> int:
    st = state.load()
    folder = Path(a.dir or st.get("dir") or state.default_workspace()).expanduser().absolute()
    careful = st.get("careful", False) if a.careful is None else a.careful
    ui.say("Full Fat sets up a chat with Claude or ChatGPT that can see and work with JASP.")
    ui.say("It uses the subscription you already pay for. It asks a few simple questions on the way.")

    ui.heading("JASP")
    j = find_jasp(a, ui)
    if j is None or not check_version(j, ui):
        return 1
    if not prepare_link(j, ui):
        return 1

    ui.heading("Chat app")
    keys = chosen_apps(a, st, ui)
    place = chatgpt_place(a, st, ui) if "codex" in keys else st.get("chatgpt_in")
    claude_in = claude_place(a, st)
    exes = {}
    for k in keys:
        if k == "codex" and place == "app":  # the app brings its own Codex and its own sign-in
            ui.ok("ChatGPT chats open in the ChatGPT app.")
            exes[k] = "app"
            continue
        exe = ensure_app(apps.APPS[k], ui, may_install=not a.no_install_apps, may_sign_in=not a.no_sign_in,
                         agreed=a.install_apps)
        if exe:
            exes[k] = exe

    ui.heading("Chat folder")
    if workspace.find_uvx() == "uvx" and not shutil.which("uvx"):
        ui.problem("uv is missing (the chat app needs it to reach JASP).")
        ui.say(f"  Run the Full Fat install line again: {GITHUB}#install")
    try:
        p = prompts.load_prompts(j.version)
    except (urllib.error.URLError, OSError, RuntimeError) as e:
        ui.problem(f"Could not download JASP's instructions from GitHub ({e}).")
        ui.say("  Check the internet connection and run Full Fat again.")
        return 1
    persona = pick_persona(a.persona or st.get("persona"), p, ui)
    host, port = j.host_port()
    res = workspace.build(folder, p, persona, careful, host, port, j.plot_dirs)
    ui.ok(f"Chat folder ready: {keep(folder)} (JASP instructions from {p.ref}, persona {persona}"
          f"{', careful mode' if careful else ''}).")
    for n in p.notes:
        ui.say("  " + n)
    for old in res.kept_old:
        ui.say(f"  You had changed a file Full Fat updates, so your copy is kept as {keep(old)}")
    connector_ok = warm_connector(folder, ui)

    if "codex" in keys and not a.no_trust:
        r = apps.trust_codex_folder(folder)
        if r == "added":
            state.save({"codex_trust_added": str(folder)})
            ui.ok("Codex trusts the chat folder, so it uses the folder's settings.")
        elif r == "already":
            ui.ok("Codex already trusts the chat folder.")
        else:
            ui.say("  When Codex asks whether you trust this folder, choose yes.")

    launchers: list[str] = []
    icon_place = "on your Desktop"
    if not a.no_launcher:
        if sys.platform == "darwin":
            ui.say("  If your Mac asks whether Terminal may use your Desktop folder, click Allow.")
        try:
            launchers = [str(x) for x in launcher.create(folder)]
        except OSError:
            try:
                launchers = [str(x) for x in launcher.create(folder, desktop=Path.home())]
                icon_place = "in your home folder"
                ui.say(f"  Full Fat could not put the icon on the Desktop, so it is in your home folder: "
                       f"{keep(launchers[0] if launchers else Path.home())}")
            except OSError as e:
                ui.problem(f"Full Fat could not make the Full Fat icon ({e}).")
        for x in launchers:
            if not launcher.is_icon_file(x) and Path(x).parent != state.config_dir():
                ui.ok(f'"{launcher.NAME}" icon: {keep(x)}')

    old_launchers = [x for x in st.get("launchers", []) if x not in launchers]
    if launchers:  # new icons were written, so they replace the ones recorded earlier
        old_launchers = [x for x in old_launchers if not remove_launcher(x, ui)]
    state.save({"dir": str(folder), "apps": keys, "persona": persona, "careful": careful,
                "launchers": launchers + old_launchers, "settings_file": a.settings_file,
                "jasp_version": j.version, "chatgpt_in": place or "terminal", "claude_in": claude_in})

    if not exes:
        ui.heading("Not finished")
        ui.say("No chat app is ready yet, so there is nothing to chat in. Run Full Fat setup again in a Terminal "
               "window: it offers to install the app and helps you sign in.")
        return 1
    ui.heading("Done" if connector_ok else "Almost done")
    ui.say("To chat about your JASP work:")
    if launchers:
        ui.say(f'  Double-click "{launcher.NAME}" {icon_place}.')
    else:
        ui.say("  Open a new Terminal window and type: full-fat launch")
        ui.say(f"  (or, in this window: {keep(launcher.shell_command(launcher.full_fat_command() + ['launch']))})")
    ui.say("  Full Fat opens JASP for you. If JASP is already open, it may ask you to close it first, so save your "
           "work in JASP before you start.")
    first_run_notes(list(exes), ui, app_route=place == "app", browser=claude_in == "browser")
    if not connector_ok:
        return 1
    if not ui.yes and not a.no_start and ui.yes_no("Start a chat now?", True, on_eof=False):
        a.app = next(iter(exes)) if len(exes) == 1 else None
        return cmd_launch(a, ui)
    return 0


def first_run_notes(keys: list[str], ui: UI, app_route: bool = False, browser: bool = False) -> None:
    if "codex" in keys and app_route:
        ui.say("ChatGPT chats open in the ChatGPT app:")
        for line in APP_NOTES:
            ui.say("  - " + line)
    terminal = [k for k in keys if k == "claude" or not app_route]
    if not terminal:
        return
    ui.say("The first time you start a chat in the Terminal:")
    if "claude" in terminal:
        ui.say("  - Claude shows a few welcome screens (for example a choice of colours). Press Enter on each.")
        ui.say('  - Claude asks whether you trust the chat folder. Press the Down arrow once, so that "Yes, I trust '
               'this folder" is picked, then press Enter. (Enter alone picks "No, exit".)')
    if "codex" in terminal:
        ui.say("  - Codex may show a welcome screen or ask about the folder. Choose the first option and press Enter.")
    ui.say("  - Before the chat loads a data file, or writes a report or an annotation into JASP, it asks you. To "
           'let it, choose the first option ("Yes" in Claude, "Allow" in ChatGPT) and press Enter.')
    if sys.platform == "darwin":
        ui.say("  - If your Mac offers to install \"command line developer tools\", click Cancel. The chat "
               "doesn't need them.")
    if "claude" in terminal and browser:
        ui.say("Claude chats also open in your web browser:")
        for line in BROWSER_NOTES:
            ui.say("  - " + line)


# ---------------------------------------------------------------------------- launch

APP_NOTES = [
    "Full Fat opens JASP, then the ChatGPT app with a new chat on its Codex side, in the chat folder.",
    "The first time, the app may ask you to sign in. Sign in with your ChatGPT account.",
    "The first message is already typed in for you. Press Enter to send it, and the chat says hello.",
    "If the app asks before it loads a data file, or writes a report or an annotation into JASP, choose Allow.",
    "To change the model or the effort, use the picker under the message box.",
    "Once the app is open, you can close the Terminal window. JASP stays open and connected.",
]


BROWSER_NOTES = [
    f'Once Claude is ready, the chat also opens in your web browser, at {remote.CODE_URL} (it is called '
    f'"{remote.NAME}" there). You can type there or in the Terminal window.',
    "If the browser asks you to sign in, sign in to claude.ai with your Claude account (the one you pay "
    "for). The first time it may ask you to sign in again to check this computer, and may offer "
    "notifications: those are up to you.",
    "Keep the Terminal window open while you chat: closing it ends the chat.",
    "To finish, type /exit in the Terminal window and press Enter, then close it.",
]
BROWSER_UNAVAILABLE = {
    "account": "Your chat stays in this window: opening it in the browser needs Claude Code signed in with a "
               "Claude Pro or Max account.",
    "old": "Your chat stays in this window: this Claude Code is too old to open it in the browser. To get "
           "that, update Claude Code (type claude update in a Terminal window).",
}


def _workspace_from(a, st: dict) -> Path:
    return Path(a.dir or st.get("dir") or state.default_workspace()).expanduser().absolute()


def connect(j: jasp.Jasp, host: str, port: int, ui: UI, is_running=None, ping=None,
            start_wait: float = 120) -> bool:
    """Make sure JASP is open and answers. Its connection is switched on only while Full Fat opens JASP, and
    is off again on disk however this ends (see link.py)."""
    store = j.write_store()
    try:
        return _connect(j, store, host, port, ui, is_running or jasp.running, ping or jasp.ping, start_wait)
    finally:
        if store is not None:
            try:
                link.switch_off(store)
            except OSError as e:
                ui.problem(f"Full Fat could not switch JASP's connection off again ({e}). Run full-fat setup to "
                           "try again.")


def _connect(j, store, host, port, ui: UI, is_running, ping, start_wait) -> bool:
    if ping(host, port):
        return True
    if store is None:
        ui.problem("Full Fat could not find JASP's settings, so it cannot connect to JASP.")
        ui.say("  Open and close JASP once, then run Full Fat setup again.")
        return False
    if is_running():
        if store.enabled() and waiting(ui, "JASP is open. Waiting for it to answer... If JASP shows a question "
                                       "(for example about checking for updates), answer it first.",
                                       lambda: ping(host, port), timeout=30):
            return True
        ui.say("JASP is open, but it was started without its connection for chats, and JASP only switches that "
               "on when it starts.")
        ui.say(f"  Save your work, then close JASP ({quit_hint()}). Full Fat then opens JASP again for you.")
        if ui.yes:
            return False
        waiting(ui, "  Waiting for JASP to close...", lambda: not is_running())
        time.sleep(2)  # let JASP finish quitting
    if not link.switch_on(store):
        ui.problem("Full Fat changed the setting, but JASP's settings still say it is off.")
        for n in j.notes:
            ui.say("  " + n)
        return False
    opened = jasp.open_jasp(j)
    if opened:
        msg = ("Opening JASP for you. This can take a minute. If JASP asks a question (for example about "
               "checking for updates), answer it: JASP connects after that.")
    else:
        msg = "Open JASP now. Full Fat waits until it answers."
    while True:
        started = time.monotonic()
        gone = {"since": None}

        def answered_or_gone() -> bool:
            """Stop waiting when JASP answers, or when the JASP Full Fat opened is gone (it closed or crashed)."""
            if ping(host, port):
                return True
            if opened and time.monotonic() - started > GRACE and not is_running():
                gone["since"] = gone["since"] or time.monotonic()
                return time.monotonic() - gone["since"] > GRACE
            gone["since"] = None
            return False
        waiting(ui, msg, answered_or_gone, timeout=start_wait)
        if ping(host, port):
            return True
        if gone["since"]:
            ui.problem("JASP closed again, or it did not start.")
            prompt = "Open JASP yourself, then press Enter (or Ctrl+C to stop)."
        else:
            prompt = ("JASP has not answered yet. If JASP shows a question, answer it. Then press Enter to keep "
                      "waiting (or Ctrl+C to stop).")
        if ui.yes or not ui.enter(prompt):
            return False
        opened = False
        msg = "Waiting for JASP to answer..."


def cmd_launch(a, ui: UI) -> int:
    st = state.load()
    folder = _workspace_from(a, st)
    missing = workspace.missing_files(folder)
    if missing:
        ui.problem(f"The chat folder {keep(folder)} is missing or incomplete.")
        ui.say("  Run Full Fat setup again (run the install line again, or: full-fat setup).")
        return 1
    keys = [a.app] if getattr(a, "app", None) in apps.APPS else list(st.get("apps") or ["claude"])
    if len(keys) > 1:
        n = ui.choose("Chat with which?", ["Claude", "ChatGPT"], 1)
        keys = [keys[n - 1]]
    app = apps.APPS[keys[0]]
    chosen = getattr(a, "open_in", None)
    in_app = app.key == "codex" and (chosen if chosen in ("app", "terminal") else st.get("chatgpt_in")) == "app"
    if in_app and not apps.desktop_app_found():
        ui.problem("Full Fat could not find the ChatGPT app, so the chat starts here in the Terminal instead.")
        in_app = False
    exe = None
    if not in_app:
        exe = terminal_app(app, a, ui)
        if not exe:
            return 1
    j = jasp.detect(st.get("settings_file"), st.get("jasp_version"))
    m = workspace.read_manifest(folder)
    host = m.get("host") or j.host_port()[0]
    port = int(m.get("port") or j.host_port()[1])
    if not connect(j, host, port, ui, start_wait=getattr(a, "wait", None) or 120):
        return 1
    if in_app:
        ui.ok("JASP is open and connected. Opening the chat in the ChatGPT app...")
        if apps.open_desktop_app(apps.deep_link(folder, prompts.INTRO_MESSAGE)):
            return app_opened(ui)
        ui.problem("The ChatGPT app did not open, so the chat starts here in the Terminal instead.")
        exe = terminal_app(app, a, ui)
        if not exe:
            return 1
    else:
        ui.ok("JASP is open and connected. Starting the chat...")
    browser = app.key == "claude" and claude_place(a, st) == "browser" and in_browser(exe, ui)
    cmd = apps.launch_command(app, exe, prompts.INTRO_MESSAGE, folder, remote.NAME if browser else None)
    os.chdir(folder)
    if os.name == "nt":
        with subprocess.Popen(cmd) as p:
            if browser:
                remote.start_thread(p, folder, j.plot_dirs)
            return p.wait()
    real_terminal_input()
    if browser:
        remote.start_detached(os.getpid(), folder, j.plot_dirs)
    os.execv(exe, cmd)
    return 0  # not reached


def in_browser(exe: str, ui: UI) -> bool:
    """Can this chat also open in the browser? Says what happens either way."""
    why = remote.unavailable(exe)
    if why:
        ui.say("  " + BROWSER_UNAVAILABLE[why])
        ui.say("  Keep this window open while you chat. To finish, type /exit and press Enter, or close it.")
        return False
    ui.ok("Your chat also opens in your web browser once Claude is ready. If it doesn't, go to "
          f'{remote.CODE_URL} and click "{remote.NAME}". Claude also shows the chat\'s own link below.')
    for line in BROWSER_NOTES[1:]:
        ui.say("  " + line)
    return True


def terminal_app(app: apps.App, a, ui: UI) -> str | None:
    """The chat app for the Terminal, installed (with a yes) and signed in, or None."""
    exe = ensure_app(app, ui, may_install=True, may_sign_in=False, agreed=getattr(a, "install_apps", False))
    if not exe or (apps.signed_in(app, exe) is False and not sign_in(app, exe, ui)):
        return None
    return exe


def app_opened(ui: UI) -> int:
    ui.ok("The ChatGPT app is opening a new chat on its Codex side, in the chat folder.")
    for line in APP_NOTES[1:]:
        ui.say("  " + line)
    if not ui.yes:
        ui.enter("Press Enter to close this window.")
    return 0


def real_terminal_input() -> None:
    """Give the chat app the terminal itself as its input, not /dev/tty.

    The install line runs setup with input from /dev/tty, and "Start a chat now?" then starts the chat app with
    that input. On macOS, programs that watch their input with kqueue cannot use /dev/tty (it fails with
    EINVAL), so the input is reopened as the terminal's own device (for example /dev/ttys003), found from the
    output, which is the same terminal."""
    try:
        if os.ttyname(0) != "/dev/tty":
            return
    except OSError:
        return
    for fd in (1, 2):
        try:
            name = os.ttyname(fd)
        except OSError:
            continue
        if name and name != "/dev/tty":
            try:
                new = os.open(name, os.O_RDWR | getattr(os, "O_NOCTTY", 0))
            except OSError:
                continue
            os.dup2(new, 0)
            os.close(new)
            return


# ---------------------------------------------------------------------------- doctor

def cmd_doctor(a, ui: UI) -> int:
    st = state.load()
    folder = _workspace_from(a, st)
    problems = 0

    def bad(msg: str, fix: str) -> None:
        nonlocal problems
        problems += 1
        ui.problem(msg)
        ui.say(f"  Fix: {fix}")

    j = jasp.detect(a.settings_file or st.get("settings_file"), a.jasp_version or st.get("jasp_version"))
    if not j.found:
        bad("JASP was not found.", f"download and install JASP from {jasp.DOWNLOAD_URL}")
    else:
        ok = j.version_ok()
        if ok is False:
            bad(f"JASP {j.version} is too old.", f"install the newest JASP from {jasp.DOWNLOAD_URL}")
        else:
            ui.ok(f"JASP found (it reports version {j.version or 'unknown'}).")
        for n in j.notes:
            bad(n, "ask whoever manages this computer")
        store = j.write_store()
        if store is None:
            bad("Full Fat could not find JASP's settings.", "open and close JASP once, then run full-fat setup")
        elif link.left_on(store):
            bad("JASP's connection for chats was left switched on.",
                "run full-fat setup, which switches it off (a chat started with the Full Fat icon still works)")
        elif store.enabled():
            ui.ok("JASP's connection for chats is switched on in JASP (it was on before Full Fat, so it stays on).")
        else:
            ui.ok("JASP's connection for chats is off until Full Fat opens JASP for a chat.")
    m = workspace.read_manifest(folder)
    host = m.get("host") or j.host_port()[0]
    port = int(m.get("port") or j.host_port()[1])
    if jasp.ping(host, port):
        ui.ok("JASP is open and answers.")
    elif jasp.running():
        ui.say("  JASP is open without its connection for chats. The Full Fat icon asks you to close it and "
               "opens it again.")
    else:
        ui.say("  JASP is not open (that is fine: the Full Fat icon opens it).")
    for k in st.get("apps") or ["claude"]:
        app = apps.APPS[k]
        if k == "codex" and st.get("chatgpt_in") == "app":
            if apps.desktop_app_found():
                ui.ok("The ChatGPT app is installed (ChatGPT chats open there).")
            else:
                bad("The ChatGPT app was not found, so ChatGPT chats start in the Terminal.",
                    "install the ChatGPT app, or run full-fat setup and choose the Terminal")
            continue
        exe = apps.find(app)
        if not exe:
            bad(f"{app.product} is not installed.", "run full-fat setup again")
            continue
        ui.ok(f"{app.product} is installed.")
        if apps.signed_in(app, exe):
            ui.ok(f"Signed in to {app.product}.")
        else:
            bad(f"Not signed in to {app.product}.", "run full-fat setup again, or double-click Full Fat")
    missing = workspace.missing_files(folder)
    if missing:
        bad(f"The chat folder {keep(folder)} is missing {', '.join(missing)}.", "run full-fat setup again")
    else:
        ui.ok(f"Chat folder {keep(folder)} is complete.")
    if not shutil.which("uvx") and workspace.find_uvx() == "uvx":
        bad("uv is missing, so the chat app cannot reach JASP.", f"run the Full Fat install line again ({GITHUB})")
    elif not missing:
        import json  # noqa: PLC0415
        try:
            server = json.loads((folder / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["jasp"]
            ok, detail = connector.warm(server, folder)
        except (OSError, ValueError, KeyError) as e:
            ok, detail = False, str(e)
        if ok:
            ui.ok("The link between the chat and JASP starts.")
        else:
            bad("The link between the chat and JASP does not start.", connector.explain(detail))
    for x in st.get("launchers", []):
        if not Path(x).exists():
            bad(f"The Full Fat icon {keep(x)} is gone.", "run full-fat setup again")
    ui.say("")
    ui.say("Everything looks fine." if not problems else f"{problems} problem(s) found.")
    return 1 if problems else 0


# ---------------------------------------------------------------------------- uninstall

def remove_chat_folder(folder: Path, ui: UI) -> None:
    """Delete what Full Fat wrote into the chat folder (the files its manifest lists, unchanged), then the
    folder if nothing else is left. Never a folder without Full Fat's manifest."""
    if not folder.is_dir():
        return
    m = workspace.read_manifest(folder)
    if not m:
        ui.say(f"  {keep(folder)} was not made by Full Fat (it has no {workspace.MANIFEST}), so it was left alone.")
        return
    files = m.get("files") if isinstance(m.get("files"), dict) else {}
    ours, changed = [], []
    for rel, digest in files.items():
        p = folder / rel
        if p.is_file() and not p.is_symlink() and folder.resolve() in p.resolve().parents:
            text = p.read_text(encoding="utf-8", errors="replace")
            (ours if workspace.sha(text) == digest else changed).append(p)
    listed = {folder / rel for rel in files} | {folder / workspace.MANIFEST} | set(plots.copies(folder))
    other = 0
    for root, dirs, names in os.walk(folder):
        for n in names + [d for d in dirs if os.path.islink(os.path.join(root, d))]:
            if Path(root, n) not in listed:
                other += 1
    other += len(changed)
    if other:
        ui.say(f"  The chat folder also has {other} other file(s), folder link(s) or changed file(s). They are kept.")
    if not ui.yes_no(f"Delete the files Full Fat made in {keep(folder)}?", True, on_eof=False):
        ui.say(f"  Kept {keep(folder)}")
        return
    plots.clear(folder)  # the plot copies made for the browser
    for p in ours + [folder / workspace.MANIFEST]:
        try:
            p.unlink()
        except OSError:
            pass
    # then the folders Full Fat made for its files, deepest first, if they are empty now
    made = {q for p in ours for q in p.parents if q == folder or folder in q.parents}
    for d in sorted(made, key=lambda q: len(q.parts), reverse=True):
        try:
            if not d.is_symlink() and not any(d.iterdir()):
                d.rmdir()
        except OSError:
            pass
    if folder.exists():
        ui.ok(f"Removed Full Fat's files. {keep(folder)} still has your own files, so it was kept.")
    else:
        ui.ok(f"Removed {keep(folder)}")


def cmd_uninstall(a, ui: UI) -> int:
    st = state.load()
    folder = _workspace_from(a, st)
    ui.say("This removes the Full Fat icon and the files Full Fat made in the chat folder, and puts JASP's "
           "setting back as it was.")
    if not ui.yes_no("Go ahead?", True, on_eof=False):
        return 1
    for x in st.get("launchers", []):
        remove_launcher(x, ui)
    remove_chat_folder(folder, ui)
    changes = [c for c in st.get("jasp_changes", []) if isinstance(c, dict) and isinstance(c.get("store"), dict)]
    for c in changes:
        try:
            link.restore(c)
        except OSError as e:
            ui.problem(f"Could not put JASP's setting back ({e}).")
            return 1
    if changes:
        ui.ok("JASP's connection for chats is back to how it was before Full Fat.")
    trusted = st.get("codex_trust_added")
    if trusted:
        r = apps.untrust_codex_folder(trusted)
        if r == "removed":
            ui.ok("Removed the trust entry Full Fat had added for Codex.")
        elif r == "left":
            ui.say(f"  Codex's trust entry for {keep(trusted)} was left in {keep(apps.codex_home() / 'config.toml')}.")
        backup = apps.codex_home() / "config.toml.before-full-fat"
        if backup.exists():
            ui.say(f"  Codex's settings from before Full Fat are kept in {keep(backup)}")
    sf = state.state_file()
    if sf.exists():
        sf.unlink()
    ui.say(f"Backups of JASP's settings are kept in {keep(state.backup_dir())}")
    ui.say("To remove Full Fat itself: uv tool uninstall full-fat")
    return 0


# ---------------------------------------------------------------------------- arguments

def parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dir", help="chat folder (default: '~/Full Fat', or the one used last time)")
    common.add_argument("--yes", "-y", action="store_true",
                        help="don't ask anything: take the defaults, never wait, never install the chat apps "
                             "(for scripts and CI)")
    common.add_argument("--settings-file", help=argparse.SUPPRESS)  # a stand-in JASP settings file (tests, CI)
    common.add_argument("--jasp-version", help="use this JASP version instead of the one found")

    p = argparse.ArgumentParser(prog="full-fat", description=__doc__)
    p.add_argument("--version", action="version", version=f"full-fat {__version__}")
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("setup", parents=[common], help="set everything up (the default)")
    s.add_argument("--app", choices=["claude", "codex", "both"], help="which chat app to set up")
    s.add_argument("--persona", help="JASP persona: alfred, socrates, evelyn or none (default alfred)")
    s.add_argument("--careful", action=argparse.BooleanOptionalAction, default=None,
                   help="ask before every change to JASP; reading JASP still runs without asking")
    s.add_argument("--no-install-apps", action="store_true", help="don't install Claude Code or Codex")
    s.add_argument("--install-apps", action="store_true",
                   help="install Claude Code or Codex without asking, also with --yes (for CI)")
    s.add_argument("--no-sign-in", action="store_true", help="don't check or start the sign-in")
    s.add_argument("--no-launcher", action="store_true", help="don't make the Full Fat icon")
    s.add_argument("--no-trust", action="store_true", help="don't mark the folder as trusted in Codex")
    s.add_argument("--no-start", action="store_true", help="don't offer to start a chat at the end")
    s.add_argument("--open-in", choices=["app", "browser", "terminal"],
                   help="where chats open (remembered): Claude in the Terminal and the browser (browser, the "
                        "default) or only the Terminal; ChatGPT in the ChatGPT app's Codex side (app) or the "
                        "Terminal. terminal sets both")
    l = sub.add_parser("launch", parents=[common], help="check JASP, then start the chat (the Full Fat icon runs this)")
    l.add_argument("--app", choices=["claude", "codex"], help="which chat app to start")
    l.add_argument("--open-in", choices=["app", "browser", "terminal"],
                   help="where this chat opens: browser or terminal (Claude), app or terminal (ChatGPT)")
    l.add_argument("--install-apps", action="store_true", help=argparse.SUPPRESS)
    l.add_argument("--wait", type=float, help=argparse.SUPPRESS)  # seconds to wait for JASP to answer (CI)
    sub.add_parser("doctor", parents=[common], help="check everything and say how to fix problems")
    sub.add_parser("uninstall", parents=[common],
                   help="remove the icon and Full Fat's files in the chat folder, put JASP's setting back")
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or (argv[0].startswith("-") and argv[0] not in ("-h", "--help", "--version")):
        argv.insert(0, "setup")
    a = parser().parse_args(argv)
    ui = UI(yes=a.yes)
    try:
        return {"setup": cmd_setup, "launch": cmd_launch, "doctor": cmd_doctor,
                "uninstall": cmd_uninstall}[a.cmd](a, ui)
    except KeyboardInterrupt:
        print("\nStopped. Nothing is broken: run the same thing again to carry on.")
        return 130
