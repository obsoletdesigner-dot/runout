"""Parser RIFF/WAVE propio, en Python puro (struct).

Solo indexa el archivo: guarda id, offset y tamaño de cada chunk. El chunk
``data`` nunca se carga en memoria; se lee en streaming cuando hace falta
(hash o copia).
"""
from __future__ import annotations

import hashlib
import os
import struct
from dataclasses import dataclass, field
from typing import BinaryIO, Iterator

from ..i18n import tr


COPY_BLOCK = 1024 * 1024          # 1 MB por bloque al copiar o hashear
MAX_RIFF_SIZE = 0xFFFFFFFF         # límite de un uint32
MAX_META_CHUNK = 64 * 1024 * 1024  # tope para cargar en memoria un chunk de metadatos


class RiffError(Exception):
    """El archivo no es un WAV que podamos manejar con seguridad."""


@dataclass
class Chunk:
    cid: bytes            # id de 4 bytes, p. ej. b"fmt "
    offset: int           # offset de la cabecera del chunk (id + tamaño)
    size: int             # tamaño declarado (sin byte de relleno)
    list_type: bytes | None = None  # para LIST: b"INFO", b"adtl", ...

    @property
    def data_offset(self) -> int:
        return self.offset + 8

    @property
    def padded_size(self) -> int:
        return self.size + (self.size & 1)

    @property
    def end(self) -> int:
        """Offset del byte siguiente al chunk, incluido el relleno."""
        return self.data_offset + self.padded_size

    @property
    def label(self) -> str:
        name = self.cid.decode("latin-1")
        if self.list_type:
            name += "-" + self.list_type.decode("latin-1")
        return name

    def is_info_list(self) -> bool:
        return self.cid == b"LIST" and self.list_type == b"INFO"

    def is_id3(self) -> bool:
        return self.cid in (b"id3 ", b"ID3 ")


@dataclass
class RiffFile:
    path: str
    file_size: int
    riff_size: int
    chunks: list[Chunk] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def find(self, cid: bytes) -> list[Chunk]:
        return [c for c in self.chunks if c.cid == cid]

    def first(self, cid: bytes) -> Chunk | None:
        found = self.find(cid)
        return found[0] if found else None

    @property
    def data(self) -> Chunk:
        c = self.first(b"data")
        assert c is not None
        return c

    @property
    def fmt(self) -> Chunk:
        c = self.first(b"fmt ")
        assert c is not None
        return c

    def info_lists(self) -> list[Chunk]:
        return [c for c in self.chunks if c.is_info_list()]

    def id3_chunks(self) -> list[Chunk]:
        return [c for c in self.chunks if c.is_id3()]


def _valid_id(cid: bytes) -> bool:
    return len(cid) == 4 and all(32 <= b <= 126 for b in cid)


def parse(path: str | os.PathLike) -> RiffFile:
    """Indexa un WAV. Lanza RiffError si no es seguro trabajar con él."""
    path = os.fspath(path)
    file_size = os.path.getsize(path)
    if file_size < 12:
        raise RiffError(tr("The file is too small to be a WAV."))

    with open(path, "rb") as f:
        head = f.read(12)
        magic, riff_size, form = struct.unpack("<4sI4s", head)
        if magic in (b"RF64", b"BW64"):
            raise RiffError(tr("RF64/BW64 file (> 4 GB): not supported in this version."))
        if magic != b"RIFF":
            raise RiffError(tr("Not a RIFF file (header %r).") % magic)
        if form != b"WAVE":
            raise RiffError(tr("RIFF but not WAVE (type %r).") % form)

        info = RiffFile(path=path, file_size=file_size, riff_size=riff_size)
        if riff_size + 8 != file_size:
            info.warnings.append(
                tr("The declared RIFF size (%d) does not match the file (%d bytes); "
                   "it will be fixed on save.") % (riff_size, file_size - 8))

        pos = 12
        while pos < file_size:
            if file_size - pos < 8:
                info.warnings.append(
                    tr("There are %d stray bytes at the end of the file; they will be dropped on save.")
                    % (file_size - pos))
                break
            f.seek(pos)
            cid, size = struct.unpack("<4sI", f.read(8))
            if not _valid_id(cid):
                if info.first(b"data") is not None and info.first(b"fmt ") is not None:
                    info.warnings.append(
                        tr("Non-RIFF data after the last chunk (%d bytes); it will be dropped "
                           "on save.") % (file_size - pos))
                    break
                raise RiffError(tr("Chunk with an invalid id at offset %d.") % pos)
            chunk = Chunk(cid=cid, offset=pos, size=size)
            data_end = chunk.data_offset + size
            if data_end > file_size:
                if cid == b"data":
                    raise RiffError(tr("The data chunk is truncated: the file is incomplete."))
                raise RiffError(tr("Chunk %r is truncated (offset %d).") % (cid, pos))
            if cid == b"LIST" and size >= 4:
                chunk.list_type = f.read(4)
            info.chunks.append(chunk)
            if chunk.end > file_size:
                # chunk impar al final sin su byte de relleno: tolerado
                info.warnings.append(
                    tr("The last chunk %s is missing its padding byte; it will be added on save.")
                    % chunk.label)
                break
            pos = chunk.end

    fmts = info.find(b"fmt ")
    datas = info.find(b"data")
    if len(fmts) != 1:
        raise RiffError(tr("Expected exactly one 'fmt ' chunk, found %d.") % len(fmts))
    if len(datas) != 1:
        raise RiffError(tr("Expected exactly one 'data' chunk, found %d.") % len(datas))
    return info


def read_chunk_bytes(path: str, chunk: Chunk) -> bytes:
    """Lee el contenido (sin relleno) de un chunk pequeño de metadatos."""
    if chunk.size > MAX_META_CHUNK:
        raise RiffError(tr("Chunk %s is too large (%d bytes).") % (chunk.label, chunk.size))
    with open(path, "rb") as f:
        f.seek(chunk.data_offset)
        data = f.read(chunk.size)
    if len(data) != chunk.size:
        raise RiffError(tr("Incomplete read of chunk %s.") % chunk.label)
    return data


def iter_chunk_payload(f: BinaryIO, chunk: Chunk) -> Iterator[bytes]:
    """Devuelve el contenido del chunk en bloques, sin cargarlo entero."""
    f.seek(chunk.data_offset)
    remaining = chunk.size
    while remaining:
        block = f.read(min(COPY_BLOCK, remaining))
        if not block:
            raise RiffError(tr("Unexpected end of file while reading %s.") % chunk.label)
        remaining -= len(block)
        yield block


def sha256_chunk(path: str, chunk: Chunk) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter_chunk_payload(f, chunk):
            h.update(block)
    return h.hexdigest()
