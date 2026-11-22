import json

import pytest

SETTINGS_CPP = r'''
#include "settings.h"
Settings::Setting Settings::Values[] = {
	{"aiEnabled",			false},
	{"aiCommonSystemPrompt",		"You are JASP AI.\n\nUse \"tools\" wisely.\tTabbed\\slash"},
	{"aiCommonSystemPromptUseCustom",	false},
	{"aiAnnotationPrompt",		"Annotate only the current analysis.\n"
	                                "Second line, été." // a comment
	                                /* another */ " End."},
	{"rpcServerEnabled",		false},
	{"rpcServerIp",			"127.0.0.1"},
	{"rpcServerPort",			48164},
};
'''

PERSONAS = json.dumps([
    {"id": "a1", "name": "Alfred the Assistant", "personaPrompt": "Your name is Alfred.\nLine two.\n",
     "enabledCapabilities": ["*"], "image": ""},
    {"id": "s1", "name": "Socrates the Tutor", "personaPrompt": "Ask questions.", "enabledCapabilities": ["*"]},
    {"id": "e1", "name": "Evelyn the Explainer", "personaPrompt": "Explain.", "enabledCapabilities": ["*"]},
])


def make_fetcher(files):
    """files: {(ref, path): text}. Anything else is a 404."""
    from full_fat.prompts import NotFound

    def fetch(ref, path, timeout=30):
        if (ref, path) in files:
            return files[(ref, path)]
        raise NotFound(f"{path} at {ref}")
    return fetch


@pytest.fixture
def fake_github():
    from full_fat.prompts import PERSONAS as P, SETTINGS as S
    files = {}
    for ref in ("v0.98.1", "development"):
        files[(ref, S)] = SETTINGS_CPP
        files[(ref, P)] = PERSONAS
    return files


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("FULL_FAT_CONFIG", str(tmp_path / "ff-config"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
