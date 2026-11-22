"""Download JASP's own AI prompts for the installed JASP version.

The prompts are JASP's text (AGPL-3.0). They are downloaded from jasp-stats/jasp-desktop when you run
setup and are never stored in this repository.

Where they live in JASP's source (same paths in v0.98.0 to v0.99.0 and development):
- Desktop/utilities/settings.cpp: the settings table, entries {"aiCommonSystemPrompt", "..."} and
  {"aiAnnotationPrompt", "..."} (v0.98.1 lines 150 and 153, development lines 167 and 170).
- Resources/defaultPersonas.json: a list of {id, name, personaPrompt, enabledCapabilities, image}.
- Desktop/ai/aiBridge.cpp (v0.98.1 line 312): the hidden first message "Give a short introduction."
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field

RAW = "https://raw.githubusercontent.com/jasp-stats/jasp-desktop/{ref}/{path}"
SETTINGS = "Desktop/utilities/settings.cpp"
PERSONAS = "Resources/defaultPersonas.json"
FALLBACK_REF = "development"
INTRO_MESSAGE = "Give a short introduction."

SIMPLE_ESCAPES = {
    "n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v",
    "\\": "\\", "'": "'", '"': '"', "?": "?",
}
# Wrappers JASP could put around a literal, e.g. {"key", QStringLiteral("...")}.
WRAPPERS = ("QStringLiteral", "QString", "QLatin1String", "QT_TR_NOOP", "QT_TRANSLATE_NOOP", "tr", "qsTr")


class NotFound(Exception):
    """The file is not in jasp-desktop at that ref (HTTP 404)."""


def fetch(ref: str, path: str, timeout: float = 30) -> str:
    url = RAW.format(ref=ref, path=path)
    req = urllib.request.Request(url, headers={"User-Agent": "full-fat"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise NotFound(f"{path} at {ref}") from e
        raise


# ---------------------------------------------------------------------------- C++ string literals

def _skip_space(src: str, i: int) -> int:
    """Skip whitespace and C++ comments."""
    n = len(src)
    while i < n:
        if src[i].isspace():
            i += 1
        elif src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j + 1
        elif src.startswith("/*", i):
            j = src.find("*/", i + 2)
            i = n if j < 0 else j + 2
        else:
            break
    return i


_LITERAL_START = re.compile(r'(u8|u|U|L)?(R)?"')


def _decode_escapes(body: str) -> str:
    """Decode the escapes of an ordinary C++ string literal. \\x and octal escapes are bytes (UTF-8)."""
    out = bytearray()
    i, n = 0, len(body)
    while i < n:
        c = body[i]
        if c != "\\":
            out += c.encode("utf-8")
            i += 1
            continue
        i += 1
        if i >= n:
            out += b"\\"
            break
        e = body[i]
        if e in SIMPLE_ESCAPES:
            out += SIMPLE_ESCAPES[e].encode("utf-8")
            i += 1
        elif e == "x":
            m = re.match(r"[0-9A-Fa-f]+", body[i + 1:])
            if not m:
                out += b"\\x"
                i += 1
                continue
            out.append(int(m.group(0), 16) & 0xFF)
            i += 1 + len(m.group(0))
        elif e in "uU":
            size = 4 if e == "u" else 8
            digits = body[i + 1:i + 1 + size]
            if len(digits) == size and re.fullmatch(r"[0-9A-Fa-f]+", digits):
                out += chr(int(digits, 16)).encode("utf-8")
                i += 1 + size
            else:
                out += ("\\" + e).encode("utf-8")
                i += 1
        elif e in "01234567":
            m = re.match(r"[0-7]{1,3}", body[i:])
            out.append(int(m.group(0), 8) & 0xFF)
            i += len(m.group(0))
        else:  # unknown escape: keep it as written
            out += ("\\" + e).encode("utf-8")
            i += 1
    return out.decode("utf-8", errors="replace")


def _read_literal(src: str, i: int) -> tuple[str, int] | None:
    """Read one string literal at src[i]. Returns (decoded text, index after it), or None."""
    m = _LITERAL_START.match(src, i)
    if not m:
        return None
    j = m.end()
    if m.group(2):  # raw string R"delim( ... )delim"
        paren = src.find("(", j)
        if paren < 0:
            return None
        delim = src[j:paren]
        end_marker = ")" + delim + '"'
        end = src.find(end_marker, paren + 1)
        if end < 0:
            return None
        return src[paren + 1:end], end + len(end_marker)
    k = j
    n = len(src)
    while k < n:
        if src[k] == "\\":
            k += 2
            continue
        if src[k] == '"':
            return _decode_escapes(src[j:k]), k + 1
        if src[k] == "\n":
            return None  # unterminated
        k += 1
    return None


def cpp_setting_string(source: str, key: str) -> str | None:
    """Return the text of the settings entry {"key", "..."} in settings.cpp, or None if missing.

    Handles adjacent literals ("a" "b" on several lines, with comments between them), raw strings,
    the usual escapes, and a wrapper such as QStringLiteral("...").
    """
    for m in re.finditer(r'\{\s*"%s"\s*,' % re.escape(key), source):
        i = _skip_space(source, m.end())
        opened = 0
        while True:
            w = re.match(r"(%s)\s*\(" % "|".join(WRAPPERS), source[i:])
            if not w:
                break
            i = _skip_space(source, i + w.end())
            opened += 1
        parts = []
        while True:
            lit = _read_literal(source, i)
            if lit is None:
                break
            parts.append(lit[0])
            i = _skip_space(source, lit[1])
        if parts:
            return "".join(parts)
    return None


# ---------------------------------------------------------------------------- personas

def persona_slug(name: str, fallback: str = "persona") -> str:
    """'Alfred the Assistant' -> 'alfred'."""
    s = re.sub(r"[^a-z0-9]+", "-", name.split(" the ")[0].lower()).strip("-")
    return s or re.sub(r"[^a-z0-9]+", "-", fallback.lower()).strip("-") or "persona"


def parse_personas(text: str) -> dict[str, tuple[str, str]]:
    """Return {slug: (display name, prompt)} from defaultPersonas.json, in file order."""
    data = json.loads(text)
    items = data if isinstance(data, list) else data.get("personas", []) if isinstance(data, dict) else []
    out: dict[str, tuple[str, str]] = {}
    for p in items:
        if not isinstance(p, dict):
            continue
        prompt = str(p.get("personaPrompt") or "").strip()
        name = str(p.get("name") or p.get("id") or "").strip()
        if not prompt or not name:
            continue
        slug = persona_slug(name, str(p.get("id") or ""))
        base, n = slug, 2
        while slug in out:
            slug = f"{base}-{n}"
            n += 1
        out[slug] = (name, prompt)
    return out


# ---------------------------------------------------------------------------- versions and refs

def parse_version(text: str | None) -> tuple[int, ...] | None:
    """'0.98.1.0' -> (0, 98, 1); '0.99' -> (0, 99, 0). None if there is no number."""
    if not text:
        return None
    m = re.match(r"\s*v?(\d+)(?:\.(\d+))?(?:\.(\d+))?", str(text))
    if not m:
        return None
    return tuple(int(g or 0) for g in m.groups())


def version_string(v: tuple[int, ...]) -> str:
    return ".".join(str(x) for x in v[:3])


def candidate_refs(version: str | None) -> list[str]:
    """Tags to try for a version, then development.

    Microsoft Store packages can add digits to the patch number (Tools/CMake/JASP.cmake,
    JASP_VERSION_MSIX_PATCH_POSTFIX), so 0.98.100 also tries v0.98.10 and v0.98.1.
    """
    refs: list[str] = []
    v = parse_version(version)
    if v:
        major, minor, patch = v[:3]
        p = str(patch)
        while True:
            refs.append(f"v{major}.{minor}.{p}")
            if len(p) <= 1 or not p.endswith("0"):
                break
            p = p[:-1]
    refs.append(FALLBACK_REF)
    out = []
    for r in refs:
        if r not in out:
            out.append(r)
    return out


@dataclass
class Prompts:
    system: str
    annotate: str | None
    personas: dict[str, tuple[str, str]]
    ref: str
    notes: list[str] = field(default_factory=list)
    sources: dict[str, str] = field(default_factory=dict)  # piece -> ref it came from


def load_prompts(version: str | None, fetcher=None) -> Prompts:
    """Download the prompts for a JASP version.

    Uses the tag for that version. When the tag does not exist (a nightly or a newer build), or a piece
    is missing there, that piece comes from the development branch instead.
    """
    fetcher = fetcher or fetch
    refs = candidate_refs(version)
    settings_src = None
    ref = None
    notes: list[str] = []
    for r in refs:
        try:
            settings_src = fetcher(r, SETTINGS)
            ref = r
            break
        except NotFound:
            continue
    if settings_src is None:
        raise RuntimeError("Could not download JASP's prompts from GitHub.")
    if version and ref == FALLBACK_REF:
        notes.append(f"JASP {version} has no release tag on GitHub, so the newest prompts were used.")

    cache: dict[tuple[str, str], str | None] = {(ref, SETTINGS): settings_src}

    def get(r: str, path: str) -> str | None:
        if (r, path) not in cache:
            try:
                cache[(r, path)] = fetcher(r, path)
            except NotFound:
                cache[(r, path)] = None
        return cache[(r, path)]

    sources: dict[str, str] = {}

    def piece(key: str) -> str | None:
        for r in [ref] + ([FALLBACK_REF] if ref != FALLBACK_REF else []):
            src = get(r, SETTINGS)
            text = cpp_setting_string(src, key) if src else None
            if text is not None:
                sources[key] = r
                if r != ref:
                    notes.append(f"{key} is not in JASP {ref}, so it came from {r}.")
                return text
        return None

    system = piece("aiCommonSystemPrompt")
    if system is None:
        raise RuntimeError("JASP's source has no AI system prompt (aiCommonSystemPrompt). "
                           "This JASP version is probably too old.")
    annotate = piece("aiAnnotationPrompt")
    if annotate is None:
        notes.append("No annotation prompt found, so /annotate is not set up.")

    personas: dict[str, tuple[str, str]] = {}
    for r in [ref] + ([FALLBACK_REF] if ref != FALLBACK_REF else []):
        text = get(r, PERSONAS)
        if text is None:
            continue
        try:
            personas = parse_personas(text)
        except (ValueError, AttributeError):
            personas = {}
        if personas:
            sources["personas"] = r
            if r != ref:
                notes.append(f"JASP {ref} has no personas file, so the personas came from {r}.")
            break
    if not personas:
        notes.append("No personas found, so none is used.")
    return Prompts(system=system, annotate=annotate, personas=personas, ref=ref, notes=notes, sources=sources)
