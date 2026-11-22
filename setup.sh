#!/usr/bin/env bash
# Set up a folder where an AI app (Claude Code, Codex CLI) can work with a running JASP
# through JASP's MCP server, using JASP's own prompts.
#
# Usage: ./setup.sh [--dir DIR] [--persona alfred|socrates|evelyn|none] [--jasp-version X.Y.Z]
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIR="$HOME/JASP-AI"
PERSONA="alfred"
VERSION=""
# Pinned jasp-mcp commit (2026-05-13). Update after checking a newer one.
# jasp-mcp breaks with the MCP Python SDK 2.x, so templates/mcp.json adds --with "mcp<2".
JASP_MCP_REF="72d9d7be9c003b9681b40871ee5850795108e5ab"

while [[ $# -gt 0 ]]; do
	case "$1" in
		--dir) DIR="$2"; shift 2 ;;
		--persona) PERSONA="$2"; shift 2 ;;
		--jasp-version) VERSION="$2"; shift 2 ;;
		-h|--help) sed -n 2,6p "$0"; exit 0 ;;
		*) echo "Unknown option: $1" >&2; exit 1 ;;
	esac
done

for cmd in python3 uvx; do
	command -v "$cmd" >/dev/null || { echo "Needs $cmd. Install it first (uvx comes with uv: https://docs.astral.sh/uv/)." >&2; exit 1; }
done

# 1. Find JASP and its settings file.
CONF=""
if flatpak info org.jaspstats.JASP >/dev/null 2>&1; then
	[[ -z "$VERSION" ]] && VERSION="$(flatpak info org.jaspstats.JASP | awk '/Version:/ {print $2}')"
	CONF="$HOME/.var/app/org.jaspstats.JASP/config/JASP/JASP.conf"
elif [[ -f "$HOME/.config/JASP/JASP.conf" ]]; then
	CONF="$HOME/.config/JASP/JASP.conf"
fi
echo "JASP version: ${VERSION:-unknown (using the latest prompts)}"

conf_get() { [[ -f "$CONF" ]] && sed -n "s/^$1=//p" "$CONF" | head -1 || true; }
HOST="$(conf_get rpcServerIp)"; HOST="${HOST:-127.0.0.1}"
PORT="$(conf_get rpcServerPort)"; PORT="${PORT:-48164}"

# 2. Turn on JASP's MCP server.
if [[ "$(conf_get rpcServerEnabled)" == "true" ]]; then
	echo "JASP MCP server: already on ($HOST:$PORT)"
elif [[ -n "$CONF" ]] && ! pgrep -x JASP >/dev/null; then
	cp "$CONF" "$CONF.before-jasp-ai"
	if grep -q '^rpcServerEnabled=' "$CONF"; then
		sed -i 's/^rpcServerEnabled=.*/rpcServerEnabled=true/' "$CONF"
	else
		sed -i '0,/^\[General\]$/s//[General]\nrpcServerEnabled=true/' "$CONF"
	fi
	echo "JASP MCP server: turned on (backup: $CONF.before-jasp-ai)"
else
	echo "JASP MCP server: OFF. In JASP, tick Preferences > AI > MCP > \"Enable MCP server\", then restart JASP."
	echo "  (JASP is running, so this script does not edit its settings.)"
fi

# 3. Build the workspace folder.
mkdir -p "$DIR/.claude/commands" "$DIR/jasp"
python3 -I "$HERE/fetch_prompts.py" "$VERSION" "$DIR/jasp"

{
	cat "$HERE/templates/environment.md"
	cat "$DIR/jasp/system-prompt.md"
	if [[ "$PERSONA" != "none" ]]; then
		pfile="$DIR/jasp/personas/$PERSONA.md"
		[[ -f "$pfile" ]] || { echo "No persona '$PERSONA'. Choose: $(ls "$DIR/jasp/personas" | sed 's/\.md$//' | tr '\n' ' ')none" >&2; exit 1; }
		printf '\nPersona Prompt:\n'
		tail -n +3 "$pfile" | sed 's/^/  /'
	fi
} > "$DIR/AGENTS.md"
cp "$HERE/templates/CLAUDE.md" "$DIR/CLAUDE.md"
sed -e "s/__JASP_MCP_REF__/$JASP_MCP_REF/" -e "s/__RPC_HOST__/$HOST/" -e "s/__RPC_PORT__/$PORT/" \
	"$HERE/templates/mcp.json" > "$DIR/.mcp.json"
cp "$HERE/templates/claude-settings.json" "$DIR/.claude/settings.json"
cat "$HERE/templates/annotate-head.md" "$DIR/jasp/annotate-prompt.md" > "$DIR/.claude/commands/annotate.md"

echo "Persona: $PERSONA"
echo "Done. Open JASP, then run:  cd \"$DIR\" && claude"
