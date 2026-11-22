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

from . import __version__, apps, jasp, launcher, prompts, state, workspace
from .ui import UI, waiting

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
        ui.problem(f"This JASP is version {j.version}. Full Fat needs JASP {need} or newer, "
                   "which has the connection for AI apps.")
        ui.say(f"  Download the newest JASP from {jasp.DOWNLOAD_URL} , install it, then run this again.")
        return False
    if ok is None:
        ui.say(f"  Full Fat could not tell which JASP version this is. It needs JASP {need} or newer "
               "and will use the newest JASP instructions.")
    else:
        ui.ok(f"JASP {j.version} found.")
    for n in j.notes:
        ui.say("  " + n)
    return True


def record_change(store: jasp.Store, previous: str | None) -> None:
    st = state.load()
    changes = [c for c in st.get("jasp_changes", []) if isinstance(c, dict)]
    if not any(c.get("store", {}).get("path") == store.to_json()["path"]
               and c.get("store", {}).get("domain") == store.domain for c in changes):
        changes.append({"store": store.to_json(), "previous": previous})
    state.save({"jasp_changes": changes})


def switch_on(j: jasp.Jasp, ui: UI, is_running=None) -> bool:
    """Turn on JASP's connection for AI apps. Only while JASP is closed, and with a backup first."""
    is_running = is_running or jasp.running
    store = j.write_store()
    if store is None:
        ui.problem("Full Fat could not find JASP's settings.")
        ui.say('  In JASP, open Preferences > AI > MCP, tick "Enable MCP server", then close and reopen JASP.')
        return False
    if store.enabled():
        ui.ok("JASP's connection for AI apps is already switched on.")
        return True
    if is_running():
        if ui.yes:
            ui.say("  JASP is open, so Full Fat did not change its settings. "
                   "Close JASP and run Full Fat again to switch on its connection for AI apps.")
            return False
        ui.say("JASP is open. Full Fat needs to switch on one JASP setting, and that only works while "
               "JASP is closed.")
        ui.say("  Save your work in JASP, then close JASP. Full Fat waits here until it has closed.")
        waiting(ui, "  Waiting for JASP to close...", lambda: not is_running())
        time.sleep(2)  # let JASP finish writing its own settings
    backup = store.backup(state.backup_dir())
    previous = store.get(jasp.KEY_ENABLED)
    store.set(jasp.KEY_ENABLED, True)
    record_change(store, previous)
    if not store.enabled():
        ui.problem("Full Fat changed the setting but JASP's settings still say it is off.")
        ui.say('  In JASP, open Preferences > AI > MCP and tick "Enable MCP server", then restart JASP.')
        return False
    where = f" A copy of the old settings is in {backup}." if backup else ""
    ui.ok("Switched on JASP's connection for AI apps." + where)
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


def ensure_app(app: apps.App, ui: UI, may_install: bool, may_sign_in: bool) -> str | None:
    exe = apps.find(app)
    if not exe:
        provider = "Anthropic" if app.key == "claude" else "OpenAI"
        if not may_install:
            ui.problem(f"{app.product} is not installed. Run Full Fat setup again to install it.")
            return None
        ui.say(f"To chat with {app.name.split(' (')[0]}, you need {app.product}, the free app from {provider} "
               "that you chat in.")
        if not ui.yes_no(f"Install {app.product} now? It takes a minute or two.", True):
            return None
        ui.say(f"Installing {app.product} with {provider}'s own installer...")
        if not apps.install(app):
            ui.problem(f"{app.product} could not be installed.")
            ui.say(f"  Install it by hand: {app.install_windows if os.name == 'nt' else app.install_posix}")
            return None
        exe = apps.find(app)
    ui.ok(f"{app.product} is installed.")
    if not may_sign_in:
        return exe
    s = apps.signed_in(app, exe)
    if s:
        ui.ok(f"You are signed in to {app.product}.")
    elif ui.yes:
        ui.say(f"  You are not signed in to {app.product} yet. Talk to JASP asks you to when you start it.")
    else:
        sign_in(app, exe, ui)
    return exe


def sign_in(app: apps.App, exe: str, ui: UI) -> bool:
    account = "Claude" if app.key == "claude" else "ChatGPT"
    ui.say(f"Now sign in with your {account} account (the one with your paid plan).")
    ui.say("  A browser window opens. Sign in there, allow access, then come back to this window.")
    if app.key == "claude":
        ui.say("  If it asks how to sign in, choose your Claude subscription (not the API / Console).")
    ui.enter("Press Enter to open the sign-in page.")
    done = apps.sign_in(app, exe)
    if done:
        ui.ok(f"Signed in to {app.product}.")
    else:
        ui.problem(f"Not signed in to {app.product} yet. You can do it later: Talk to JASP asks again.")
    return done


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
    switched = switch_on(j, ui)

    ui.heading("Chat app")
    keys = chosen_apps(a, st, ui)
    exes = {}
    for k in keys:
        exe = ensure_app(apps.APPS[k], ui, may_install=not a.no_install_apps, may_sign_in=not a.no_sign_in)
        if exe:
            exes[k] = exe

    ui.heading("Chat folder")
    if workspace.find_uvx() == "uvx" and not shutil.which("uvx"):
        ui.problem("uv is missing (the chat app needs it to talk to JASP).")
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
    ui.ok(f"Chat folder ready: {folder} (JASP instructions from {p.ref}, persona {persona}"
          f"{', careful mode' if careful else ''}).")
    for n in p.notes:
        ui.say("  " + n)
    for old in res.kept_old:
        ui.say(f"  You had changed a file Full Fat updates, so your copy is kept as {old}")

    if "codex" in keys and not a.no_trust:
        r = apps.trust_codex_folder(folder)
        if r == "added":
            ui.ok("Codex trusts the chat folder, so it uses the folder's settings.")
        elif r == "already":
            ui.ok("Codex already trusts the chat folder.")
        else:
            ui.say("  When Codex asks whether you trust this folder, choose yes.")

    launchers: list[str] = []
    if not a.no_launcher:
        if sys.platform == "darwin":
            ui.say("  If your Mac asks whether Terminal may use your Desktop folder, click Allow.")
        try:
            launchers = [str(x) for x in launcher.create(folder)]
        except OSError:
            launchers = [str(x) for x in launcher.create(folder, desktop=Path.home())]
            ui.say("  Full Fat could not put the icon on the Desktop, so it is in your home folder.")
        for x in launchers:
            ui.ok(f'"{launcher.NAME}" icon: {x}')

    old_launchers = [x for x in st.get("launchers", []) if x not in launchers]
    state.save({"dir": str(folder), "apps": keys, "persona": persona, "careful": careful,
                "launchers": launchers + old_launchers, "settings_file": a.settings_file,
                "jasp_version": j.version})

    ui.heading("Done")
    if "claude" in keys:
        ui.say("The first time, Claude asks whether you trust the chat folder. Press Enter to say yes.")
    ui.say("To chat about your JASP work:")
    ui.say("  1. Open JASP." + ("" if switched else " (Its connection for AI apps is still off: "
                                 "Talk to JASP offers to fix that.)"))
    ui.say(f'  2. Double-click "{launcher.NAME}" on your Desktop.' if launchers else
           f"  2. Run: full-fat launch")
    if not ui.yes and not a.no_start and exes and ui.yes_no("Start a chat now?", True):
        a.app = keys[0] if len(keys) == 1 else None
        return cmd_launch(a, ui)
    return 0


# ---------------------------------------------------------------------------- launch

def _workspace_from(a, st: dict) -> Path:
    return Path(a.dir or st.get("dir") or state.default_workspace()).expanduser().absolute()


def wait_for_jasp(j: jasp.Jasp, host: str, port: int, ui: UI, is_running=None, ping=None,
                  start_wait: float = 90) -> bool:
    """Make sure JASP is open and answers. Opens JASP, offers to fix the setting, retries."""
    is_running = is_running or jasp.running
    ping = ping or jasp.ping
    opened = False
    while True:
        if ping(host, port):
            return True
        if not is_running():
            if not opened and jasp.open_jasp(j):
                opened = True
                if waiting(ui, "Opening JASP for you. This can take a minute...", lambda: ping(host, port),
                           timeout=start_wait):
                    return True
                continue
            if not ui.enter("JASP is not open. Open JASP first, then press Enter."):
                return False
            continue
        if j.found and j.write_store() and not j.enabled():
            ui.say("JASP is open, but its connection for AI apps is switched off.")
            if not ui.yes_no("Switch it on now? JASP has to close for a moment.", True):
                return False
            if not switch_on(j, ui, is_running):
                return False
            opened = False
            continue
        if waiting(ui, "JASP is open. Waiting for it to answer...", lambda: ping(host, port), timeout=30):
            return True
        if not ui.enter("JASP does not answer. If you opened it before switching on its connection, close "
                        "JASP and open it again. Then press Enter."):
            return False


def cmd_launch(a, ui: UI) -> int:
    st = state.load()
    folder = _workspace_from(a, st)
    missing = workspace.missing_files(folder)
    if missing:
        ui.problem(f"The chat folder {folder} is missing or incomplete.")
        ui.say("  Run Full Fat setup again (run the install line again, or: full-fat setup).")
        return 1
    keys = [a.app] if getattr(a, "app", None) in apps.APPS else list(st.get("apps") or ["claude"])
    if len(keys) > 1:
        n = ui.choose("Chat with which?", ["Claude", "ChatGPT"], 1)
        keys = [keys[n - 1]]
    app = apps.APPS[keys[0]]
    exe = ensure_app(app, ui, may_install=True, may_sign_in=False)
    if not exe:
        return 1
    if apps.signed_in(app, exe) is False and not sign_in(app, exe, ui):
        return 1
    j = jasp.detect(st.get("settings_file"), st.get("jasp_version"))
    m = workspace.read_manifest(folder)
    host = m.get("host") or j.host_port()[0]
    port = int(m.get("port") or j.host_port()[1])
    if not wait_for_jasp(j, host, port, ui):
        return 1
    ui.ok("JASP is open and connected. Starting the chat...")
    cmd = apps.launch_command(app, exe, prompts.INTRO_MESSAGE)
    os.chdir(folder)
    if os.name == "nt":
        return subprocess.run(cmd).returncode
    os.execv(exe, cmd)
    return 0  # not reached


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
            ui.ok(f"JASP {j.version or '(version unknown)'} found.")
        for n in j.notes:
            bad(n, "ask whoever manages this computer")
        if j.enabled():
            ui.ok("JASP's connection for AI apps is switched on.")
        else:
            bad("JASP's connection for AI apps is switched off.",
                "close JASP and run full-fat setup, or double-click Talk to JASP and say yes when it offers")
    m = workspace.read_manifest(folder)
    host = m.get("host") or j.host_port()[0]
    port = int(m.get("port") or j.host_port()[1])
    if jasp.ping(host, port):
        ui.ok("JASP is open and answers.")
    elif jasp.running():
        bad("JASP is open but does not answer.", "close JASP and open it again")
    else:
        ui.say("  JASP is not open (that is fine until you want to chat).")
    for k in st.get("apps") or ["claude"]:
        app = apps.APPS[k]
        exe = apps.find(app)
        if not exe:
            bad(f"{app.product} is not installed.", "run full-fat setup again")
            continue
        ui.ok(f"{app.product} is installed.")
        if apps.signed_in(app, exe):
            ui.ok(f"Signed in to {app.product}.")
        else:
            bad(f"Not signed in to {app.product}.", "run full-fat setup again, or double-click Talk to JASP")
    missing = workspace.missing_files(folder)
    if missing:
        bad(f"The chat folder {folder} is missing {', '.join(missing)}.", "run full-fat setup again")
    else:
        ui.ok(f"Chat folder {folder} is complete.")
    if not shutil.which("uvx") and workspace.find_uvx() == "uvx":
        bad("uv is missing, so the chat app cannot reach JASP.", f"run the Full Fat install line again ({GITHUB})")
    for x in st.get("launchers", []):
        if not Path(x).exists():
            bad(f"The Talk to JASP icon {x} is gone.", "run full-fat setup again")
    ui.say("")
    ui.say("Everything looks fine." if not problems else f"{problems} problem(s) found.")
    return 1 if problems else 0


# ---------------------------------------------------------------------------- uninstall

def cmd_uninstall(a, ui: UI) -> int:
    st = state.load()
    folder = _workspace_from(a, st)
    ui.say("This removes the Talk to JASP icon and the chat folder, and puts JASP's setting back as it was.")
    if not ui.yes_no("Go ahead?", True):
        return 1
    for x in st.get("launchers", []):
        p = Path(x)
        try:
            if p.is_file() and launcher.NAME in p.read_text(encoding="utf-8", errors="replace"):
                p.unlink()
                ui.ok(f"Removed {p}")
        except OSError as e:
            ui.problem(f"Could not remove {p}: {e}")
    if folder.is_dir():
        m = workspace.read_manifest(folder)
        ours = set((m.get("files") or {}).keys()) | {".mcp.json", ".claude/settings.json", workspace.MANIFEST}
        extra = [q for q in folder.rglob("*") if q.is_file()
                 and q.relative_to(folder).as_posix() not in ours]
        note = f" It also has {len(extra)} file(s) you added." if extra else ""
        if ui.yes_no(f"Delete the chat folder {folder}?{note}", not extra):
            shutil.rmtree(folder)
            ui.ok(f"Removed {folder}")
        else:
            ui.say(f"  Kept {folder}")
    changes = st.get("jasp_changes", [])
    if changes:
        if jasp.running():
            if ui.yes:
                ui.say("  JASP is open, so its setting was left on. Close JASP and run this again to undo it.")
                return 1
            ui.say("JASP is open. To put its setting back, JASP has to be closed.")
            waiting(ui, "  Close JASP. Full Fat waits until it has closed...", lambda: not jasp.running())
            time.sleep(2)
        for c in changes:
            s = jasp.Store.from_json(c["store"])
            prev = c.get("previous")
            if prev is None:
                s.remove(jasp.KEY_ENABLED)
            else:
                s.set(jasp.KEY_ENABLED, str(prev).lower() in ("true", "1"))
        ui.ok("JASP's connection for AI apps is back to how it was before Full Fat.")
    sf = state.state_file()
    if sf.exists():
        sf.unlink()
    ui.say(f"Backups of JASP's settings are kept in {state.backup_dir()}")
    ui.say("To remove Full Fat itself: uv tool uninstall full-fat")
    return 0


# ---------------------------------------------------------------------------- arguments

def parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dir", help="chat folder (default: ~/JASP-AI, or the one used last time)")
    common.add_argument("--yes", "-y", action="store_true",
                        help="don't ask anything: take the defaults, never wait (for scripts and CI)")
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
    s.add_argument("--no-sign-in", action="store_true", help="don't check or start the sign-in")
    s.add_argument("--no-launcher", action="store_true", help="don't make the Talk to JASP icon")
    s.add_argument("--no-trust", action="store_true", help="don't mark the folder as trusted in Codex")
    s.add_argument("--no-start", action="store_true", help="don't offer to start a chat at the end")
    l = sub.add_parser("launch", parents=[common], help="check JASP, then start the chat (Talk to JASP runs this)")
    l.add_argument("--app", choices=["claude", "codex"], help="which chat app to start")
    sub.add_parser("doctor", parents=[common], help="check everything and say how to fix problems")
    sub.add_parser("uninstall", parents=[common], help="remove the icon and chat folder, put JASP's setting back")
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
