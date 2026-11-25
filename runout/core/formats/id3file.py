"""MP3 y AIFF: las dos usan ID3v2. mutagen solo serializa la etiqueta en memoria.

MP3: la etiqueta ID3v2 va al principio y detrás está el audio (tramas MPEG y, si
existen, etiquetas ID3v1 o APE al final). El archivo nuevo es la etiqueta nueva más
todo lo que había detrás de la antigua, copiado byte a byte; la huella es el SHA-256
de esa parte.

AIFF: archivo IFF en big-endian (FORM/AIFF o AIFC). La etiqueta va en un chunk «ID3 ».
Los demás chunks se copian byte a byte; la huella es el SHA-256 de SSND (audio) y COMM
(formato).
"""
from __future__ import annotations

import os
import struct
from dataclasses import dataclass

from ...i18n import tr
from .. import id3chunk
from ..fields import FIELDS, PICTURE_TYPES
from ..model import FileStatus, TrackMetadata
from .base import FormatError, Handler, SaveOptions, copy_range, hash_range, read_safely

ID3_FIELDS = frozenset({f.key for f in FIELDS if f.id3}
                       | {"track", "track_total", "disc", "disc_total", "custom_txxx"})


def _syncsafe(b: bytes) -> int:
    size = 0
    for x in b:
        size = (size << 7) | (x & 0x7F)
    return size


def id3v2_end(f, start: int = 0) -> int:
    """Offset donde terminan las etiquetas ID3v2 que haya a partir de `start`."""
    pos = start
    while True:
        f.seek(pos)
        head = f.read(10)
        if len(head) < 10 or head[:3] != b"ID3":
            return pos
        pos += 10 + _syncsafe(head[6:10]) + (10 if head[5] & 0x10 else 0)


def _apply_id3(raw: bytes | None, meta: TrackMetadata, status: FileStatus) -> None:
    tag = id3chunk.load(raw)
    if tag is not None:
        status.has_tags = status.has_id3 = True
        status.has_cover = id3chunk.has_cover(tag)
        id3chunk.to_metadata(tag, meta)
    elif raw:
        status.warnings.append(tr("The existing ID3 tag cannot be read; it will be replaced."))


class Id3Handler(Handler):
    fields = ID3_FIELDS
    picture_types = tuple(PICTURE_TYPES)


# --- MP3 ----------------------------------------------------------------------------
class Mp3Handler(Id3Handler):
    name = "MP3"

    def _layout(self, path: str) -> tuple[int, int]:
        with open(path, "rb") as f:
            audio_start = id3v2_end(f)
            f.seek(0, 2)
            size = f.tell()
            f.seek(audio_start)
            sync = f.read(2)
        if size - audio_start < 4 or len(sync) < 2 or sync[0] != 0xFF or sync[1] & 0xE0 != 0xE0:
            raise FormatError(tr("No MPEG audio found after the ID3 tag."))
        return audio_start, size

    def read(self, path):
        return read_safely(lambda: self._read(path))

    def _read(self, path):
        meta, status = TrackMetadata(), FileStatus(format=self.name)
        audio_start, size = self._layout(path)
        with open(path, "rb") as f:
            raw = f.read(audio_start)
            f.seek(max(size - 128, 0))
            if f.read(3) == b"TAG":
                status.warnings.append(tr("There is an old ID3v1 tag at the end; it is kept unchanged."))
        _apply_id3(raw, meta, status)
        return meta, status

    def fingerprint(self, path):
        audio_start, size = self._layout(path)
        with open(path, "rb") as f:
            return {"audio": hash_range(f, audio_start, size).hexdigest()}

    def write(self, src, tmp, meta, options: SaveOptions, warnings):
        audio_start, _ = self._layout(src)
        with open(src, "rb") as f:
            existing = f.read(audio_start)
        tag = id3chunk.build(existing, meta, options.id3_version, _mp3_length_ms(src))
        with open(src, "rb") as f, open(tmp, "wb") as out:
            out.write(tag)
            copy_range(f, out, audio_start)


def _mp3_length_ms(path: str) -> int | None:
    try:
        from mutagen.mp3 import MP3     # solo lectura, para la duración (TLEN)
        return int(MP3(path).info.length * 1000) or None
    except Exception:
        return None


# --- AIFF ---------------------------------------------------------------------------
@dataclass
class IffChunk:
    cid: bytes
    offset: int          # cabecera
    size: int

    @property
    def data_offset(self) -> int:
        return self.offset + 8

    @property
    def end(self) -> int:
        return self.data_offset + self.size + (self.size & 1)

    def is_id3(self) -> bool:
        return self.cid in (b"ID3 ", b"id3 ")


def parse_aiff(path: str) -> tuple[bytes, list[IffChunk], list[str]]:
    warnings = []
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        head = f.read(12)
        if len(head) < 12 or head[:4] != b"FORM" or head[8:12] not in (b"AIFF", b"AIFC"):
            raise FormatError(tr("Not an AIFF file."))
        form_size = struct.unpack(">I", head[4:8])[0]
        if form_size + 8 != size:
            warnings.append(tr("The declared FORM size (%d) does not match the file (%d bytes); "
                               "it will be fixed on save.") % (form_size, size - 8))
        chunks, pos = [], 12
        while pos + 8 <= size:
            f.seek(pos)
            cid, csize = struct.unpack(">4sI", f.read(8))
            chunk = IffChunk(cid, pos, csize)
            if chunk.data_offset + csize > size:
                raise FormatError(tr("Chunk %r is truncated (offset %d).") % (cid, pos))
            chunks.append(chunk)
            pos = chunk.end
        if pos < size:
            warnings.append(tr("There are %d stray bytes at the end of the file; they will be dropped on save.")
                            % (size - pos))
    for cid in (b"COMM", b"SSND"):
        n = sum(1 for c in chunks if c.cid == cid)
        if n != 1:
            raise FormatError(tr("Expected exactly one %r chunk, found %d.") % (cid.decode(), n))
    return head[8:12], chunks, warnings


def _read_chunk(path: str, chunk: IffChunk) -> bytes:
    with open(path, "rb") as f:
        f.seek(chunk.data_offset)
        return f.read(chunk.size)


def _aiff_length_ms(comm: bytes) -> int | None:
    if len(comm) < 18:
        return None
    frames = struct.unpack(">I", comm[2:6])[0]
    exponent = struct.unpack(">H", comm[8:10])[0] & 0x7FFF
    mantissa = struct.unpack(">Q", comm[10:18])[0]
    if not mantissa:
        return None
    rate = mantissa * 2.0 ** (exponent - 16383 - 63)
    return int(frames * 1000 / rate) if rate else None


class AiffHandler(Id3Handler):
    name = "AIFF"

    def read(self, path):
        return read_safely(lambda: self._read(path))

    def _read(self, path):
        meta, status = TrackMetadata(), FileStatus(format=self.name)
        _, chunks, warnings = parse_aiff(path)
        status.warnings.extend(warnings)
        status.chunk_labels = [c.cid.decode("latin-1") for c in chunks]
        id3s = [c for c in chunks if c.is_id3()]
        if len(id3s) > 1:
            status.warnings.append(tr("There are %d ID3 chunks; only one will be kept on save.") % len(id3s))
        if id3s:
            _apply_id3(_read_chunk(path, id3s[0]), meta, status)
        return meta, status

    def fingerprint(self, path):
        _, chunks, _ = parse_aiff(path)
        out = {}
        with open(path, "rb") as f:
            for c in chunks:
                if c.cid in (b"SSND", b"COMM"):
                    digest = hash_range(f, c.data_offset, c.data_offset + c.size).hexdigest()
                    out["audio" if c.cid == b"SSND" else "COMM"] = digest
        return out

    def write(self, src, tmp, meta, options: SaveOptions, warnings):
        form, chunks, _ = parse_aiff(src)
        id3s = [c for c in chunks if c.is_id3()]
        existing = _read_chunk(src, id3s[0]) if id3s else None
        comm = _read_chunk(src, next(c for c in chunks if c.cid == b"COMM"))
        tag = id3chunk.build(existing, meta, options.id3_version, _aiff_length_ms(comm))
        placed = False
        with open(src, "rb") as f, open(tmp, "wb") as out:
            out.write(b"FORM\0\0\0\0" + form)
            for c in chunks:
                if c.is_id3():
                    if placed:
                        continue
                    _write_chunk(out, b"ID3 ", tag)
                    placed = True
                    continue
                copy_range(f, out, c.offset, c.data_offset + c.size)
                if c.size & 1:
                    out.write(b"\0")
            if not placed:
                _write_chunk(out, b"ID3 ", tag)
            total = out.tell()
            out.seek(4)
            out.write(struct.pack(">I", total - 8))


def _write_chunk(out, cid: bytes, data: bytes) -> None:
    out.write(cid + struct.pack(">I", len(data)) + data)
    if len(data) & 1:
        out.write(b"\0")
