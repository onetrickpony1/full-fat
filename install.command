#!/bin/sh
# Double-click to install or update Full Fat (macOS), then set it up.
# If your Mac says it can't open this file, use the Terminal line from the README instead.
curl -LsSf https://raw.githubusercontent.com/onetrickpony1/full-fat/main/install.sh | sh
echo
printf "Press Return to close."
read -r _ || true
