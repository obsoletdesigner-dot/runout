"""Chunk ``bext`` (EBU Tech 3285, Broadcast Wave Format).

Estructura fija de 602 bytes seguida del CodingHistory (texto libre).
TimeReference, UMID y los bytes reservados se conservan siempre tal cual.
"""
from __future__ import annotations

import struct

FIXED = 602
_LAYOUT = (("description", 0, 256), ("originator", 256, 32),
           ("originator_reference", 288, 32), ("origination_date", 320, 10),
           ("origination_time", 330, 8))
_LOUDNESS = (("loudness_value", 412), ("loudness_range", 414), ("max_true_peak", 416),
             ("max_momentary", 418), ("max_short_term", 420))
UNSET = 0x7FFF

# clave del campo de la app -> clave interna
FIELD_MAP = {
    "bext_description": "description", "bext_originator": "originator",
    "bext_originator_ref": "originator_reference", "bext_date": "origination_date",
    "bext_time": "origination_time", "bext_loudness": "loudness_value",
    "bext_lra": "loudness_range", "bext_true_peak": "max_true_peak",
    "bext_max_momentary": "max_momentary", "bext_max_short_term": "max_short_term",
    "bext_coding_history": "coding_history",
}
READONLY = {"bext_time_reference": "time_reference", "bext_umid": "umid"}


def _ascii(raw: bytes) -> str:
    return raw.split(b"\x00", 1)[0].decode("ascii", "replace").rstrip()


def parse(raw: bytes) -> dict[str, str]:
    raw = raw.ljust(FIXED, b"\x00")
    out = {name: _ascii(raw[o:o + n]) for name, o, n in _LAYOUT}
    low, high, version = struct.unpack_from("<IIH", raw, 338)
    out["time_reference"] = str((high << 32) | low)
    out["version"] = str(version)
    umid = raw[348:412]
    out["umid"] = umid.hex().upper() if any(umid) else ""
    for name, off in _LOUDNESS:
        (val,) = struct.unpack_from("<h", raw, off)
        out[name] = "" if version < 2 or val == UNSET else "%.2f" % (val / 100)
    hist = raw[FIXED:].split(b"\x00", 1)[0].decode("ascii", "replace")
    out["coding_history"] = hist.replace("\r\n", "\n").strip("\n")
    return out


def to_metadata(raw: bytes, meta) -> None:
    values = parse(raw)
    for key, inner in list(FIELD_MAP.items()) + list(READONLY.items()):
        if values.get(inner) and not meta.get(key):
            meta.set(key, values[inner])


def _fixed_text(value: str, size: int) -> bytes:
    return value.encode("ascii", "replace")[:size].ljust(size, b"\x00")


def build(existing: bytes | None, meta) -> bytes | None:
    """Devuelve el bext nuevo, o None si no hay que tocar nada."""
    wanted = {inner: meta.get(key) for key, inner in FIELD_MAP.items()}
    if existing is None:
        if not any(wanted.values()):
            return None
        base = bytearray(FIXED)
        current = parse(bytes(base))
        current["coding_history"] = ""
        raw_history = b""
    else:
        base = bytearray(existing[:FIXED].ljust(FIXED, b"\x00"))
        current = parse(existing)
        raw_history = existing[FIXED:]
        if all((current.get(k) or "") == (v or "") for k, v in wanted.items()):
            return None   # sin cambios: el chunk se copia byte a byte

    for name, off, size in _LAYOUT:
        base[off:off + size] = _fixed_text(wanted[name], size)

    version = struct.unpack_from("<H", base, 346)[0]
    any_loudness = any(wanted[name] for name, _ in _LOUDNESS)
    if any_loudness and version < 2:
        version = 2
    if version >= 2:
        for name, off in _LOUDNESS:
            v = wanted[name]
            struct.pack_into("<h", base, off, int(round(float(v) * 100)) if v else UNSET)
    struct.pack_into("<H", base, 346, version)

    if (wanted["coding_history"] or "") == (current.get("coding_history") or ""):
        history = raw_history
    elif wanted["coding_history"]:
        history = ("\r\n".join(wanted["coding_history"].split("\n")) + "\r\n").encode("ascii", "replace")
    else:
        history = b""
    return bytes(base) + history
