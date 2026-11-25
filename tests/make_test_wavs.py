"""Genera WAV sintéticos para probar el núcleo (sin motor de audio: bytes a mano).

Uso: python tests/make_test_wavs.py carpeta_destino
"""
from __future__ import annotations

import io
import os
import random
import struct
import sys

from mutagen.id3 import COMM, ID3, TIT2, TSRC


def chunk(cid: bytes, payload: bytes) -> bytes:
    pad = b"\x00" if len(payload) & 1 else b""
    return struct.pack("<4sI", cid, len(payload)) + payload + pad


def fmt_chunk(channels=2, rate=44100, bits=16) -> bytes:
    block = channels * bits // 8
    return chunk(b"fmt ", struct.pack("<HHIIHH", 1, channels, rate, rate * block, block, bits))


def pcm(n_bytes: int, seed: int) -> bytes:
    rnd = random.Random(seed)
    return bytes(rnd.getrandbits(8) for _ in range(n_bytes))


def riff(chunks: list[bytes], riff_size: int | None = None) -> bytes:
    body = b"WAVE" + b"".join(chunks)
    return b"RIFF" + struct.pack("<I", len(body) if riff_size is None else riff_size) + body


def bext_payload() -> bytes:
    desc = b"Master final".ljust(256, b"\x00")
    originator = b"Ejemplo Mastering".ljust(32, b"\x00")
    ref = b"REF0001".ljust(32, b"\x00")
    date, time = b"2026-11-25", b"12:00:00"
    rest = struct.pack("<IIH", 0, 0, 1) + b"\x00" * 64 + b"\x00" * 10 + b"\x00" * 180
    return desc + originator + ref + date + time + rest + b"A=PCM,F=44100,W=16,M=stereo\r\n"


def cue_payload() -> bytes:
    pts = [(1, 0), (2, 22050)]
    out = struct.pack("<I", len(pts))
    for cid, pos in pts:
        out += struct.pack("<II4sIII", cid, pos, b"data", 0, 0, pos)
    return out


def adtl_payload() -> bytes:
    labl = chunk(b"labl", struct.pack("<I", 1) + b"Intro\x00")
    labl2 = chunk(b"labl", struct.pack("<I", 2) + b"Estribillo\x00")
    return b"adtl" + labl + labl2


def info_payload(items: dict[bytes, bytes]) -> bytes:
    out = b"INFO"
    for cid, val in items.items():
        out += chunk(cid, val + b"\x00")
    return out


def id3_bytes(**frames) -> bytes:
    t = ID3()
    t.add(TIT2(encoding=3, text=frames.get("title", "Viejo título")))
    t.add(TSRC(encoding=3, text=frames.get("isrc", "ESXXX2500001")))
    t.add(COMM(encoding=3, lang="spa", desc="", text="Comentario de otra herramienta"))
    b = io.BytesIO()
    t.save(b, v2_version=4, padding=lambda i: 0)
    return b.getvalue()


OTHER_AXML = (b'<?xml version="1.0" encoding="UTF-8"?>\n'
              b'<ebucore:ebuCoreMain xmlns:dc="http://purl.org/dc/elements/1.1/" '
              b'xmlns:ebucore="urn:ebu:metadata-schema:ebuCore_2012">'
              b'<ebucore:coreMetadata><ebucore:title><dc:title>Otro dato</dc:title>'
              b'</ebucore:title></ebucore:coreMetadata></ebucore:ebuCoreMain>')


def build_all(dest: str) -> dict[str, str]:
    os.makedirs(dest, exist_ok=True)
    files = {
        # WAV mínimo: fmt + data
        "01 - plain.wav": riff([fmt_chunk(), chunk(b"data", pcm(44100 * 4, 1))]),
        # data de tamaño impar (8 bit mono) + chunks BWF habituales
        "02 - odd_bwf.wav": riff([
            chunk(b"bext", bext_payload()),
            fmt_chunk(channels=1, bits=8),
            chunk(b"iXML", b"<BWFXML><PROJECT>Album</PROJECT></BWFXML>"),
            chunk(b"data", pcm(22051, 2)),
            chunk(b"cue ", cue_payload()),
            chunk(b"LIST", adtl_payload()),
        ]),
        # metadatos previos: INFO (con ISFT ajeno), ID3 en mayúsculas, axml EBUCore tras data
        "03 - existing_meta.wav": riff([
            fmt_chunk(),
            chunk(b"LIST", info_payload({b"INAM": "Título viejo".encode("cp1252"),
                                         b"ISFT": b"Pro Tools", b"ICMT": b"impar"})),
            chunk(b"data", pcm(10001 * 4, 3)),
            chunk(b"ID3 ", id3_bytes()),
            chunk(b"axml", OTHER_AXML + b"\x00"),
            chunk(b"JUNK", b"\x00" * 27),
        ]),
        # tamaño RIFF mal declarado + bytes basura al final
        "04 - bad_riffsize.wav": riff([fmt_chunk(), chunk(b"data", pcm(2000, 4))],
                                      riff_size=12345) + b"\x00\x01\x02",
    }
    # último chunk impar sin byte de relleno
    odd = riff([fmt_chunk(channels=1, bits=8), chunk(b"data", pcm(1001, 5))])
    files["05 - missing_pad.wav"] = odd[:-1]
    # axml que no es EBUCore (no debe tocarse)
    files["06 - foreign_axml.wav"] = riff([fmt_chunk(), chunk(b"axml", b"<foo>bar</foo>"),
                                           chunk(b"data", pcm(4000, 6))])
    paths = {}
    for name, data in files.items():
        p = os.path.join(dest, name)
        with open(p, "wb") as fh:
            fh.write(data)
        paths[name] = p
    return paths


if __name__ == "__main__":
    for p in build_all(sys.argv[1] if len(sys.argv) > 1 else "test_wavs").values():
        print(p)
