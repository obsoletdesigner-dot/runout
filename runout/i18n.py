"""Interface translations.

The source strings are written in English directly in the code and wrapped in tr().
Each extra language is one JSON file in runout/locales/ that maps the English text to
the translation, plus a "_language_name" entry with the language's own name, which is
shown in Preferences. To add a language, copy es.json to <code>.json, translate the
values and run `python tools/i18n_check.py` to list missing or obsolete entries.
Untranslated strings fall back to English.
"""
from __future__ import annotations

import gettext
import json
import os

LOCALES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")
DEFAULT = "en"

_language = DEFAULT
_catalog: dict[str, str] = {}


def available_languages() -> dict[str, str]:
    """Language code -> name in that language, English first."""
    langs = {DEFAULT: "English"}
    try:
        names = sorted(n for n in os.listdir(LOCALES_DIR) if n.endswith(".json"))
    except OSError:
        names = []
    for name in names:
        code = name[:-5]
        try:
            with open(os.path.join(LOCALES_DIR, name), encoding="utf-8") as fh:
                langs[code] = json.load(fh).get("_language_name", code)
        except (OSError, ValueError):
            continue
    return langs


def set_language(code: str | None) -> str:
    """Activate a language. Unknown codes fall back to English. Returns the active code."""
    global _language, _catalog
    code = (code or DEFAULT).split("_")[0].split("-")[0].lower()
    catalog: dict[str, str] = {}
    if code != DEFAULT:
        try:
            with open(os.path.join(LOCALES_DIR, code + ".json"), encoding="utf-8") as fh:
                catalog = {k: v for k, v in json.load(fh).items() if not k.startswith("_") and v}
        except (OSError, ValueError):
            code = DEFAULT
    _language, _catalog = code, catalog
    _iso_cache.clear()
    return code


def language() -> str:
    return _language


def tr(text: str) -> str:
    return _catalog.get(text, text)


def N_(text: str) -> str:
    """Marks a string for translation without translating it yet (it is passed to tr() later)."""
    return text


def tr_n(singular: str, plural: str, n: int) -> str:
    """Singular or plural form; both are translated as separate entries."""
    return tr(singular if n == 1 else plural)


# --- ISO names (languages, countries, scripts) from pycountry's own translations ---------
_iso_cache: dict[str, gettext.NullTranslations | None] = {}


def tr_iso(domain: str, name: str) -> str:
    """Translate an ISO name (domain: iso639-3, iso3166-1, iso15924)."""
    if _language == DEFAULT:
        return name
    if domain not in _iso_cache:
        try:
            import pycountry
            _iso_cache[domain] = gettext.translation(domain, pycountry.LOCALES_DIR,
                                                     languages=[_language])
        except (ImportError, OSError):
            _iso_cache[domain] = None
    t = _iso_cache[domain]
    return t.gettext(name) if t else name
