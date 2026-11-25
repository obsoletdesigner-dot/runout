"""Interface translations: English by default, complete catalogs, switching language."""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from runout import i18n  # noqa: E402
from runout.core.validators import country_name, language_name, problem  # noqa: E402


@pytest.fixture(autouse=True)
def english_after_each_test():
    yield
    i18n.set_language("en")


def test_english_is_the_default():
    assert i18n.language() == "en"
    assert problem("bpm", "abc") == "Must be a whole number."
    assert country_name("ES") == "Spain"


def test_spanish_translates_messages_and_iso_names():
    assert i18n.set_language("es") == "es"
    assert problem("bpm", "abc") == "Debe ser un número entero."
    assert country_name("ES") == "España"
    assert language_name("spa") == "Español"
    assert i18n.tr_n("%d track", "%d tracks", 1) % 1 == "1 pista"
    assert i18n.tr_n("%d track", "%d tracks", 3) % 3 == "3 pistas"


def test_unknown_language_falls_back_to_english():
    assert i18n.set_language("xx") == "en"
    assert i18n.set_language("es_ES") == "es"


def test_available_languages():
    langs = i18n.available_languages()
    assert list(langs)[0] == "en" and langs["es"] == "Español"


def test_catalogs_are_complete():
    result = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "i18n_check.py")],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout


def test_placeholders_match():
    import json
    import re
    spec = re.compile(r"%[-+ 0#]*\d*(?:\.\d+)?[sdrfx%]")
    for name in os.listdir(i18n.LOCALES_DIR):
        with open(os.path.join(i18n.LOCALES_DIR, name), encoding="utf-8") as fh:
            catalog = json.load(fh)
        for en, other in catalog.items():
            if en.startswith("_") or not other:
                continue
            assert spec.findall(en) == spec.findall(other), (name, en, other)
