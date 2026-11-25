"""Normalización y validación de cada tipo de campo.

normalize(field, valor) limpia lo que se pega (espacios, guiones, mayúsculas).
problem(field, valor) devuelve un mensaje (traducido con tr) o None si es válido.
Un valor vacío siempre es válido (significa «sin este dato»).
"""
from __future__ import annotations

import datetime as _dt
import re
import uuid
from functools import lru_cache
from urllib.parse import urlparse

from ..i18n import N_, tr, tr_iso
from .fields import BY_KEY, Field
from .isrc import clean_isrc, isrc_problem

# códigos especiales admitidos además de ISO 639-3 / 639-2B
_SPECIAL_LANG = {"und", "mul", "zxx", "mis", "xxx"}
_MUSIC_KEY = re.compile(r"^(?:[A-G](?:b|#)?m?|o)$")
_GAIN = re.compile(r"^[+-]?\d{1,2}(?:\.\d{1,2})? dB$")
_ISWC = re.compile(r"^T\d{10}$")
_ID3_MEDIA = {"DIG", "ANA", "CD", "LD", "TT", "MD", "DAT", "DCC", "DVD", "TV", "VID", "RAD",
              "TEL", "MC", "REE"}


@lru_cache(maxsize=1)
def _pyc():
    import pycountry  # import diferido: solo cuando hace falta
    return pycountry


def language_name(code: str) -> str | None:
    code = code.lower()
    if code in _SPECIAL_LANG:
        return tr({"und": N_("undetermined"), "mul": N_("multiple languages"),
                   "zxx": N_("no linguistic content"), "mis": N_("uncoded language"),
                   "xxx": N_("unknown")}[code])
    p = _pyc()
    lang = p.languages.get(alpha_3=code)
    if lang is None:
        try:
            lang = p.languages.get(bibliographic=code)
        except (KeyError, LookupError):
            lang = None
    return tr_iso("iso639-3", lang.name) if lang else None


def country_name(code: str) -> str | None:
    c = _pyc().countries.get(alpha_2=code.upper())
    return tr_iso("iso3166-1", c.name) if c else None


def script_name(code: str) -> str | None:
    s = _pyc().scripts.get(alpha_4=code.title())
    return tr_iso("iso15924", s.name) if s else None


def gtin_ok(digits: str) -> bool:
    """Dígito de control GTIN (UPC-A 12, EAN-13)."""
    if not digits.isdigit() or len(digits) not in (12, 13):
        return False
    body, check = digits[:-1], int(digits[-1])
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return (10 - total % 10) % 10 == check


def iswc_check_digit(nine: str) -> int:
    total = 1 + sum(i * int(d) for i, d in enumerate(nine, start=1))
    return (10 - total % 10) % 10


def format_iswc(compact: str) -> str:
    """T1234567890 -> T-123.456.789-0"""
    return "T-%s.%s.%s-%s" % (compact[1:4], compact[4:7], compact[7:10], compact[10])


def _parse_date(value: str) -> bool:
    try:
        if re.fullmatch(r"\d{4}", value):
            return 1000 <= int(value) <= 9999
        if re.fullmatch(r"\d{4}-\d{2}", value):
            _dt.date(int(value[:4]), int(value[5:7]), 1)
            return True
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            _dt.date.fromisoformat(value)
            return True
    except ValueError:
        return False
    return False


def _parse_datetime(value: str) -> bool:
    if _parse_date(value):
        return True
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?", value)
    if not m or not _parse_date(m.group(1)):
        return False
    h, mi, s = int(m.group(2)), int(m.group(3)), int(m.group(4) or 0)
    return h < 24 and mi < 60 and s < 60


def _number(value: str) -> float | None:
    try:
        return float(value.replace(",", "."))
    except ValueError:
        return None


# ----------------------------------------------------------------------------------
def normalize(field: Field | str, value: str) -> str:
    f = BY_KEY[field] if isinstance(field, str) else field
    if value is None:
        return ""
    if f.kind in ("multiline", "people", "keyvalue", "ascii_multiline"):
        return value.replace("\r\n", "\n").strip("\n").rstrip()
    v = value.strip()
    if not v:
        return ""
    k = f.kind
    if k == "isrc":
        return clean_isrc(v)
    if k == "iswc":
        c = re.sub(r"[\s.\-]", "", v.upper())
        return format_iswc(c) if _ISWC.match(c) else v.upper()
    if k == "gtin":
        return re.sub(r"[\s\-]", "", v)
    if k == "language":
        return v.lower()
    if k == "country":
        return v.upper()
    if k == "script":
        return v.title()
    if k == "musickey":
        return v[0].upper() + v[1:] if v != "o" else v
    if k == "media":
        return v.upper()
    if k in ("count", "bpm"):
        return v.lstrip("0") or "0"
    if k == "gain":
        n = _number(v.replace("dB", "").strip())
        return "%+.2f dB" % n if n is not None else v
    if k in ("lufs", "lra", "dbtp"):
        return v.replace(",", ".")
    if k == "uuid":
        return v.lower()
    if k in ("oneline", "text", "ascii"):
        return " ".join(v.split()) if k != "ascii" else v
    return v


def problem(field: Field | str, value: str) -> str | None:
    f = BY_KEY[field] if isinstance(field, str) else field
    if f.readonly or value is None or value == "":
        return None
    k, v = f.kind, value
    if f.maxlen and len(v.encode("ascii", "replace")) > f.maxlen:
        return tr("At most %d characters (it has %d).") % (f.maxlen, len(v))
    if k in ("text", "oneline") and ("\n" in v or "\x00" in v):
        return tr("Must be a single line.")
    if k == "isrc":
        return isrc_problem(v)
    if k in ("count", "bpm"):
        if not v.isdigit():
            return tr("Must be a whole number.")
        n = int(v)
        if k == "bpm" and not 1 <= n <= 999:
            return tr("BPM must be between 1 and 999.")
        if k == "count" and not 1 <= n <= 999:
            return tr("Must be between 1 and 999.")
        return None
    if k == "date":
        return None if _parse_date(v) else tr("Invalid date: use YYYY, YYYY-MM or YYYY-MM-DD.")
    if k == "datetime":
        return None if _parse_datetime(v) else tr("Use YYYY-MM-DD or YYYY-MM-DDTHH:MM(:SS).")
    if k == "isodate":
        return None if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) and _parse_date(v) \
            else tr("Invalid date: YYYY-MM-DD.")
    if k == "isotime":
        m = re.fullmatch(r"(\d{2}):(\d{2}):(\d{2})", v)
        return None if m and int(m[1]) < 24 and int(m[2]) < 60 and int(m[3]) < 60 \
            else tr("Invalid time: HH:MM:SS.")
    if k == "language":
        if not re.fullmatch(r"[a-z]{3}", v):
            return tr("Must be a 3-letter ISO 639-3 code (eng, spa, fra…).")
        return None if language_name(v) else tr("“%s” is not an existing ISO 639-3 code.") % v
    if k == "country":
        if not re.fullmatch(r"[A-Z]{2}", v):
            return tr("Must be a 2-letter ISO 3166-1 code (US, GB, ES…).")
        return None if country_name(v) else tr("“%s” is not an ISO 3166-1 country.") % v
    if k == "script":
        return None if re.fullmatch(r"[A-Z][a-z]{3}", v) and script_name(v) \
            else tr("Must be a 4-letter ISO 15924 code (Latn, Cyrl…).")
    if k == "musickey":
        return None if _MUSIC_KEY.match(v) else tr("Invalid key (e.g. Am, F#m, C, Bb, o).")
    if k == "media":
        return None if v.split("/")[0] in _ID3_MEDIA else tr("Invalid ID3 media type.")
    if k == "gtin":
        if not v.isdigit() or len(v) not in (12, 13):
            return tr("UPC (12 digits) or EAN (13 digits).")
        return None if gtin_ok(v) else tr("The barcode check digit is wrong.")
    if k == "iswc":
        c = re.sub(r"[\s.\-]", "", v)
        if not _ISWC.match(c):
            return tr("ISWC format: T-123.456.789-C.")
        return None if iswc_check_digit(c[1:10]) == int(c[10]) \
            else tr("The ISWC check digit is wrong.")
    if k == "url":
        u = urlparse(v)
        return None if u.scheme in ("http", "https") and u.netloc and " " not in v \
            else tr("Invalid URL: it must start with http:// or https://.")
    if k == "uuid":
        try:
            uuid.UUID(v)
            return None
        except ValueError:
            return tr("Invalid MusicBrainz identifier (UUID).")
    if k == "gain":
        return None if _GAIN.match(v) else tr("Format: -6.52 dB.")
    if k == "peak":
        n = _number(v)
        return None if n is not None and 0 <= n <= 10 else tr("Linear peak between 0 and 10 (e.g. 0.988547).")
    if k == "lufs":
        n = _number(v)
        return None if n is not None and -99.99 <= n <= 0 else tr("Between -99.99 and 0 LUFS.")
    if k == "lra":
        n = _number(v)
        return None if n is not None and 0 <= n <= 99.99 else tr("Between 0 and 99.99 LU.")
    if k == "dbtp":
        n = _number(v)
        return None if n is not None and -99.99 <= n <= 20 else tr("Between -99.99 and +20 dBTP.")
    if k in ("ascii", "ascii_multiline"):
        try:
            v.encode("ascii")
        except UnicodeEncodeError:
            return tr("bext only allows ASCII (no accents or special letters).")
        return None
    if k == "people":
        for line in v.splitlines():
            if line.strip() and ":" not in line:
                return tr("Each line must be “role: name”.")
        return None
    if k == "keyvalue":
        for line in v.splitlines():
            if line.strip() and ("=" not in line or not line.split("=", 1)[0].strip()):
                return tr("Each line must be KEY=value.")
        return None
    return None


def validate_values(values: dict[str, str]) -> dict[str, str]:
    """Errores de todos los campos, más las reglas que cruzan campos."""
    errors = {}
    for key, value in values.items():
        if key in BY_KEY:
            msg = problem(BY_KEY[key], value)
            if msg:
                errors[key] = msg
    for n, total in (("track", "track_total"), ("disc", "disc_total")):
        a, b = values.get(n, ""), values.get(total, "")
        if a.isdigit() and b.isdigit() and int(a) > int(b):
            errors[n] = tr("Greater than the total (%s).") % b
    return errors
