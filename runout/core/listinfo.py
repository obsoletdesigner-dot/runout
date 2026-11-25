"""Chunk ``LIST`` de tipo ``INFO`` (metadatos RIFF nativos)."""
from __future__ import annotations

import struct

from .fields import FIELDS
from .model import TrackMetadata

# Campos que gestiona la app (sale de core/fields.py). OJO: INFO/ISRC significa
# "Source", así que el código ISRC nunca se escribe ahí: ese subchunk solo se
# rellena desde el campo «Fuente (INFO/ISRC)».
MANAGED: dict[bytes, str] = {f.info.encode("ascii"): f.key for f in FIELDS if f.info}

def decode_text(raw: bytes) -> str:
    raw = raw.split(b"\x00", 1)[0]
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", "replace")


def encode_text(text: str, encoding: str = "utf-8") -> bytes:
    """UTF-8 por defecto (lo que esperan BWF MetaEdit y MediaInfo). Con
    «cp1252» se usa Windows-1252 y, si un texto no cabe, UTF-8."""
    if encoding == "cp1252":
        try:
            return text.encode("cp1252")
        except UnicodeEncodeError:
            pass
    return text.encode("utf-8")


def parse(payload: bytes) -> list[tuple[bytes, bytes]]:
    """payload = contenido del chunk LIST (empieza por b'INFO')."""
    items: list[tuple[bytes, bytes]] = []
    if payload[:4] != b"INFO":
        return items
    pos = 4
    while pos + 8 <= len(payload):
        cid, size = struct.unpack_from("<4sI", payload, pos)
        start = pos + 8
        value = payload[start:start + size]
        items.append((cid, value))
        pos = start + size + (size & 1)
    return items


def to_metadata(items: list[tuple[bytes, bytes]], meta: TrackMetadata) -> None:
    """Rellena en `meta` solo los campos vacíos (ID3 tiene prioridad)."""
    for cid, value in items:
        key = MANAGED.get(cid)
        if not key or meta.get(key):
            continue
        text = decode_text(value).strip()
        if not text:
            continue
        if key == "track":
            digits = text.split("/")[0].strip()
            if digits.isdigit():
                meta.set("track", str(int(digits)))
        else:
            meta.set(key, text)


def build(existing_payload: bytes | None, meta: TrackMetadata,
          encoding: str = "utf-8") -> bytes | None:
    """Devuelve el nuevo contenido del LIST-INFO (b'INFO' + subchunks).

    Conserva los subchunks que la app no gestiona (IPRT, ISMP, ...).
    Devuelve None si no queda ningún campo.
    """
    items = parse(existing_payload) if existing_payload else []
    values = {cid: meta.get(key) for cid, key in MANAGED.items()}
    out: list[tuple[bytes, bytes]] = []
    seen = set()
    for cid, value in items:
        if cid in values:
            if cid in seen:
                continue
            seen.add(cid)
            if values[cid]:
                out.append((cid, encode_text(values[cid], encoding) + b"\x00"))
        else:
            # subchunk ajeno: se copia tal cual
            out.append((cid, value))
    for cid, text in values.items():
        if cid not in seen and text:
            out.append((cid, encode_text(text, encoding) + b"\x00"))
    if not out:
        return None

    parts = [b"INFO"]
    for cid, data in out:
        parts.append(struct.pack("<4sI", cid, len(data)))
        parts.append(data)
        if len(data) & 1:
            parts.append(b"\x00")
    return b"".join(parts)
