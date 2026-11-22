#!/usr/bin/env python3
"""Download JASP's own AI prompts for a given JASP version.

Reads the system prompt and annotation prompt from Desktop/utilities/settings.cpp
and the shipped personas from Resources/defaultPersonas.json in the
jasp-stats/jasp-desktop repository, at the tag that matches the installed JASP.

Usage: fetch_prompts.py VERSION OUT_DIR
Writes OUT_DIR/system-prompt.md, OUT_DIR/annotate-prompt.md,
OUT_DIR/personas/<slug>.md and OUT_DIR/source.txt.
"""

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAW = "https://raw.githubusercontent.com/jasp-stats/jasp-desktop/{ref}/{path}"
SETTINGS = "Desktop/utilities/settings.cpp"
PERSONAS = "Resources/defaultPersonas.json"
ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\", "'": "'", "r": "\r"}


def fetch(ref, path):
    url = RAW.format(ref=ref, path=path)
    req = urllib.request.Request(url, headers={"User-Agent": "full-fat"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def cpp_string(source, key):
    """Return the decoded C++ string literal that follows {"key", in settings.cpp."""
    m = re.search(r'\{"%s",\s*"((?:[^"\\]|\\.)*)"' % re.escape(key), source)
    if not m:
        raise SystemExit(f"Could not find {key} in {SETTINGS}")
    return re.sub(r"\\(.)", lambda e: ESCAPES.get(e.group(1), e.group(0)), m.group(1))


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.split(" the ")[0].lower()).strip("-")


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    version, out = sys.argv[1], Path(sys.argv[2])
    refs = [f"v{version}", "development"] if version else ["development"]
    for ref in refs:
        try:
            settings = fetch(ref, SETTINGS)
            personas = json.loads(fetch(ref, PERSONAS))
            break
        except urllib.error.HTTPError as e:
            print(f"  {ref}: {e.code}, trying the next source", file=sys.stderr)
    else:
        raise SystemExit("Could not download JASP's prompts.")

    out.mkdir(parents=True, exist_ok=True)
    (out / "personas").mkdir(exist_ok=True)
    (out / "system-prompt.md").write_text(cpp_string(settings, "aiCommonSystemPrompt") + "\n")
    (out / "annotate-prompt.md").write_text(cpp_string(settings, "aiAnnotationPrompt") + "\n")
    plist = personas if isinstance(personas, list) else personas.get("personas", [])
    names = []
    for p in plist:
        s = slug(p["name"])
        names.append(s)
        (out / "personas" / f"{s}.md").write_text(
            f"Persona: {p['name']}\n\n{p['personaPrompt'].strip()}\n")
    (out / "source.txt").write_text(
        f"Downloaded from jasp-stats/jasp-desktop at {ref} (AGPL-3.0).\n"
        f"Files: {SETTINGS}, {PERSONAS}\n")
    print(f"  Prompts from jasp-desktop {ref}; personas: {', '.join(names)}")


if __name__ == "__main__":
    main()
