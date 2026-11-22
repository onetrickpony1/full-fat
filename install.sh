#!/bin/sh
# Full Fat installer for macOS and Linux. No admin rights needed.
#
#   curl -LsSf https://raw.githubusercontent.com/onetrickpony1/full-fat/main/install.sh | sh
#
# What it does:
#   1. installs uv (https://docs.astral.sh/uv/) if missing: it manages Python for Full Fat, and
#      the chat apps use it to start JASP's connector (jasp-mcp)
#   2. installs Full Fat in its own isolated environment, with its own Python if needed
#   3. starts the guided setup (it asks a few plain questions)
# Run it again to update. Uninstall: full-fat uninstall, then uv tool uninstall full-fat
set -eu

SOURCE="${FULL_FAT_SOURCE:-full-fat @ https://github.com/onetrickpony1/full-fat/archive/refs/heads/main.zip}"
PYTHON="${FULL_FAT_PYTHON:-3.12}"

say() { printf '\n==> %s\n' "$*"; }
fail() { printf '\nFull Fat installer: %s\n' "$*" >&2; exit 1; }

say "Installing Full Fat"

# 1. uv
if command -v uv >/dev/null 2>&1; then
    UV="$(command -v uv)"
elif [ -x "$HOME/.local/bin/uv" ]; then
    UV="$HOME/.local/bin/uv"
else
    say "Installing uv (a Python manager, from astral.sh)"
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    else
        fail "needs curl or wget to download uv"
    fi
    for c in "$HOME/.local/bin/uv" "${XDG_BIN_HOME:-$HOME/.local/bin}/uv" "$HOME/.cargo/bin/uv"; do
        [ -x "$c" ] && UV="$c" && break
    done
    [ -n "${UV:-}" ] || fail "uv was installed but can't be found; open a new terminal and run this again"
fi

# 2. Full Fat (+ Python if needed)
say "Installing Full Fat (Python $PYTHON is downloaded if needed)"
"$UV" tool install --force --python "$PYTHON" "$SOURCE" || fail "installing Full Fat failed (see above)"
"$UV" tool update-shell >/dev/null 2>&1 || true
BIN="$("$UV" tool dir --bin)"
FF="$BIN/full-fat"
[ -x "$FF" ] || fail "Full Fat was installed but $FF is missing"
say "Installed: $("$FF" --version)"

# 3. guided setup
say "Setting up"
status=0
if [ -n "${FULL_FAT_SETUP_ARGS:-}" ]; then
    # shellcheck disable=SC2086  # word splitting wanted (CI passes several options)
    "$FF" setup $FULL_FAT_SETUP_ARGS || status=$?
elif ( : < /dev/tty ) 2>/dev/null; then
    "$FF" setup < /dev/tty || status=$?
else
    "$FF" setup --yes || status=$?
fi
if [ "$status" -ne 0 ]; then
    printf '\nSetup stopped before the end. Run the same install line again any time to carry on.\n'
    exit "$status"
fi
