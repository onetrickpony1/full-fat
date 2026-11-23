"""Make stand-in Claude Code and Codex programs for CI, and print the environment lines that point Full Fat at
them. Each one answers the sign-in check with success and, when started as the chat, writes the folder it was
started in and its arguments to LOG, then exits.

Usage: python tests/make_stand_in_apps.py DIR LOG >> "$GITHUB_ENV"
"""

import os
import sys
from pathlib import Path


def main() -> int:
    folder, log = Path(sys.argv[1]), Path(sys.argv[2])
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("claude", "codex"):
        if os.name == "nt":
            p = folder / f"{name}.cmd"
            p.write_text('@echo off\r\nif "%~1"=="auth" exit /b 0\r\nif "%~1"=="login" exit /b 0\r\n'
                         f'>>"{log}" echo %CD%\r\n>>"{log}" echo %*\r\nexit /b 0\r\n')
        else:
            p = folder / name
            p.write_text('#!/bin/sh\ncase "$1" in auth|login) exit 0;; esac\n'
                         f'{{ pwd; echo "$@"; }} >> "{log}"\n')
            p.chmod(0o755)
        print(f"FULL_FAT_{name.upper()}={p}")
    print("FULL_FAT_CHATGPT_APP=none")  # the stand-in Codex starts in the Terminal, never a real ChatGPT app
    return 0


if __name__ == "__main__":
    sys.exit(main())
