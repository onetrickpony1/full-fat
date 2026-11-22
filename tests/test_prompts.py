import pytest

from conftest import PERSONAS, SETTINGS_CPP, make_fetcher
from full_fat import prompts
from full_fat.prompts import cpp_setting_string, load_prompts, parse_personas, persona_slug


def test_escapes():
    assert cpp_setting_string(SETTINGS_CPP, "aiCommonSystemPrompt") == \
        'You are JASP AI.\n\nUse "tools" wisely.\tTabbed\\slash'


def test_concatenated_literals_with_comments_and_unicode():
    assert cpp_setting_string(SETTINGS_CPP, "aiAnnotationPrompt") == \
        "Annotate only the current analysis.\nSecond line, été. End."


def test_missing_key_and_non_string():
    assert cpp_setting_string(SETTINGS_CPP, "nope") is None
    assert cpp_setting_string(SETTINGS_CPP, "rpcServerPort") is None


def test_raw_string_and_wrapper():
    src = '{"k1", R"x(raw "text" \\n kept)x"},\n{"k2", QStringLiteral("a\\n" "b")},'
    assert cpp_setting_string(src, "k1") == 'raw "text" \\n kept'
    assert cpp_setting_string(src, "k2") == "a\nb"


def test_hex_octal_and_unknown_escapes():
    src = r'{"k", "\x41\101\q\'"}'
    assert cpp_setting_string(src, "k") == "AA\\q'"


def test_utf8_bytes_escape():
    src = r'{"k", "caf\xc3\xa9"}'
    assert cpp_setting_string(src, "k") == "café"


def test_same_as_old_regex_on_simple_literals():
    # the old setup used one regex; the new parser must give the same text for JASP's current shape
    import re
    old_escapes = {"n": "\n", "t": "\t", '"': '"', "\\": "\\", "'": "'", "r": "\r"}
    src = r'{"aiX",	"a\nb \"c\" \\d \'e\' \tf"},'
    m = re.search(r'\{"aiX",\s*"((?:[^"\\]|\\.)*)"', src)
    old = re.sub(r"\\(.)", lambda e: old_escapes.get(e.group(1), e.group(0)), m.group(1))
    assert cpp_setting_string(src, "aiX") == old


@pytest.mark.parametrize("name,slug", [
    ("Alfred the Assistant", "alfred"), ("Socrates the Tutor", "socrates"),
    ("Evelyn the Explainer", "evelyn"), ("Dr. Jane O'Neil", "dr-jane-o-neil"), ("", "persona"),
])
def test_persona_slug(name, slug):
    assert persona_slug(name) == slug


def test_parse_personas_list_and_dict_and_duplicates():
    assert list(parse_personas(PERSONAS)) == ["alfred", "socrates", "evelyn"]
    d = '{"personas": [{"name": "Al the A", "personaPrompt": "x"}, {"name": "Al the B", "personaPrompt": "y"},' \
        ' {"name": "Empty", "personaPrompt": ""}]}'
    assert list(parse_personas(d)) == ["al", "al-2"]


def test_candidate_refs():
    assert prompts.candidate_refs("0.98.1.0") == ["v0.98.1", "development"]
    assert prompts.candidate_refs("0.98.100") == ["v0.98.100", "v0.98.10", "v0.98.1", "development"]
    assert prompts.candidate_refs(None) == ["development"]
    assert prompts.candidate_refs("1.0") == ["v1.0.0", "development"]


def test_load_prompts_tag(fake_github):
    p = load_prompts("0.98.1.0", make_fetcher(fake_github))
    assert p.ref == "v0.98.1" and p.notes == []
    assert p.system.startswith("You are JASP AI.")
    assert set(p.personas) == {"alfred", "socrates", "evelyn"}


def test_load_prompts_nightly_falls_back(fake_github):
    p = load_prompts("1.0.0", make_fetcher(fake_github))
    assert p.ref == "development"
    assert any("no release tag" in n for n in p.notes)


def test_load_prompts_missing_pieces(fake_github):
    files = dict(fake_github)
    files[("v0.98.1", prompts.SETTINGS)] = SETTINGS_CPP.replace('{"aiAnnotationPrompt"', '{"aiOther"')
    del files[("v0.98.1", prompts.PERSONAS)]
    p = load_prompts("0.98.1", make_fetcher(files))
    assert p.ref == "v0.98.1"
    assert p.annotate.startswith("Annotate only")  # from development
    assert p.sources["aiAnnotationPrompt"] == "development"
    assert p.sources["personas"] == "development"
    files[("development", prompts.SETTINGS)] = files[("v0.98.1", prompts.SETTINGS)]
    del files[("development", prompts.PERSONAS)]
    p = load_prompts("0.98.1", make_fetcher(files))
    assert p.annotate is None and p.personas == {}


def test_load_prompts_too_old():
    from full_fat.prompts import PERSONAS as P, SETTINGS as S
    files = {("v0.97.1", S): "{\"aiEnabled\", false},", ("development", S): "nothing"}
    with pytest.raises(RuntimeError):
        load_prompts("0.97.1", make_fetcher(files))
