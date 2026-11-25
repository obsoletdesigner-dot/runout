"""Importación de CSV con columnas pista,titulo,isrc."""
from __future__ import annotations

import csv
import io
import unicodedata
from dataclasses import dataclass

from ..i18n import tr
from .isrc import clean_isrc

_ALIASES = {
    "pista": "pista", "track": "pista", "n": "pista", "no": "pista", "num": "pista",
    "numero": "pista", "tracknumber": "pista",
    "titulo": "titulo", "title": "titulo", "nombre": "titulo",
    "isrc": "isrc",
}


@dataclass
class CsvRow:
    pista: int
    titulo: str
    isrc: str
    line: int


def _norm(name: str) -> str:
    name = unicodedata.normalize("NFKD", name.strip().lower())
    name = "".join(c for c in name if not unicodedata.combining(c))
    return "".join(c for c in name if c.isalnum())


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def parse_csv(path: str) -> tuple[list[CsvRow], list[str]]:
    """Devuelve (filas, avisos). Acepta ',' o ';' y UTF-8 (con o sin BOM) o Windows-1252."""
    with open(path, "rb") as fh:
        text = _decode(fh.read())
    first = text.splitlines()[0] if text.strip() else ""
    delimiter = ";" if first.count(";") > first.count(",") else ","
    if "\t" in first and first.count("\t") > max(first.count(";"), first.count(",")):
        delimiter = "\t"
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows: list[CsvRow] = []
    warnings: list[str] = []
    header = next(reader, None)
    if not header:
        return rows, [tr("The CSV is empty.")]
    cols = {}
    for idx, name in enumerate(header):
        key = _ALIASES.get(_norm(name))
        if key and key not in cols:
            cols[key] = idx
    if "pista" not in cols:
        return rows, [tr("Column 'track' (or 'pista') not found in the header: %s") % ", ".join(header)]
    for line_no, rec in enumerate(reader, start=2):
        if not any(cell.strip() for cell in rec):
            continue

        def cell(key: str) -> str:
            i = cols.get(key)
            return rec[i].strip() if i is not None and i < len(rec) else ""

        raw_num = cell("pista").split("/")[0].strip()
        try:
            num = int(float(raw_num))
        except ValueError:
            warnings.append(tr("Line %d: invalid track number (%r).") % (line_no, raw_num))
            continue
        rows.append(CsvRow(pista=num, titulo=cell("titulo"), isrc=clean_isrc(cell("isrc")),
                           line=line_no))
    return rows, warnings
