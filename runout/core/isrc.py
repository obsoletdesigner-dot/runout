"""Limpieza y validación de códigos ISRC (CC-XXX-YY-NNNNN)."""
from __future__ import annotations

import re

from ..i18n import tr


ISRC_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{3}[0-9]{7}$")
_STRIP_RE = re.compile(r"[\s\-\._/‐-― ]")


def clean_isrc(value: str | None) -> str:
    """Normaliza lo que se pega desde Excel o una distribuidora.

    'es-abc-26-00001' -> 'ESABC2600001'; 'ISRC: ES ABC 26 00001' -> 'ESABC2600001'.
    """
    if not value:
        return ""
    v = value.strip().upper()
    if v.startswith("ISRC"):
        v = v[4:].lstrip(":= ")
    return _STRIP_RE.sub("", v)


def is_valid_isrc(value: str) -> bool:
    return bool(ISRC_RE.match(value))


def isrc_problem(value: str) -> str | None:
    """Mensaje de error legible, o None si el ISRC (ya limpio) es válido o está vacío."""
    if not value:
        return None
    if len(value) != 12:
        return tr("An ISRC must have 12 characters (it has %d).") % len(value)
    if not value[:2].isalpha():
        return tr("The first 2 characters must be the country code (letters).")
    if not value[2:5].isalnum():
        return tr("Characters 3-5 (registrant) must be letters or digits.")
    if not value[5:].isdigit():
        return tr("The last 7 characters (year + designation) must be digits.")
    return None


def format_isrc(value: str) -> str:
    """Forma legible con guiones: ESABC2600001 -> ES-ABC-26-00001."""
    if not is_valid_isrc(value):
        return value
    return "%s-%s-%s-%s" % (value[:2], value[2:5], value[5:7], value[7:])
