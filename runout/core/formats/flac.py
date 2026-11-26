"""FLAC: escritor propio de bloques de metadatos.

mutagen solo serializa en memoria el bloque VORBIS_COMMENT y los PICTURE. El archivo
se reconstruye así: «fLaC» + STREAMINFO (byte a byte) + los demás bloques que la app
no gestiona (SEEKTABLE, CUESHEET, APPLICATION...) + comentarios + imágenes + relleno,
y después los frames de audio copiados tal cual. La huella incluye los frames de
audio y el bloque STREAMINFO entero, que contiene el MD5 del audio descodificado.
"""
from __future__ import annotations

import hashlib
import struct

from mutagen._vorbis import VComment
from mutagen.flac import Picture as FlacPicture

from ...i18n import tr
from ..fields import PICTURE_TYPES, pictures_to_keep
from ..model import FileStatus, TrackMetadata
from . import vorbis
from .base import FormatError, Handler, SaveOptions, copy_range, hash_range, read_safely

STREAMINFO, PADDING, VORBIS_COMMENT, PICTURE = 0, 1, 4, 6
NEW_PADDING = 4096
MAX_BLOCK = (1 << 24) - 1


class Block:
    def __init__(self, btype: int, data: bytes):
        self.type = btype
        self.data = data


def _skip_id3(f) -> int:
    """Algunos programas ponen un ID3v2 delante de «fLaC» (no es estándar)."""
    head = f.read(10)
    if head[:3] == b"ID3" and len(head) == 10:
        size = 0
        for b in head[6:10]:
            size = (size << 7) | (b & 0x7F)
        return 10 + size + (10 if head[5] & 0x10 else 0)
    return 0


def parse(path: str) -> tuple[list[Block], int, int]:
    """Bloques de metadatos, offset del audio y offset de «fLaC»."""
    with open(path, "rb") as f:
        start = _skip_id3(f)
        f.seek(start)
        if f.read(4) != b"fLaC":
            raise FormatError(tr("Not a FLAC file."))
        blocks = []
        while True:
            header = f.read(4)
            if len(header) < 4:
                raise FormatError(tr("The FLAC metadata is truncated."))
            last = header[0] & 0x80
            btype = header[0] & 0x7F
            size = int.from_bytes(header[1:4], "big")
            data = f.read(size)
            if len(data) < size:
                raise FormatError(tr("The FLAC metadata is truncated."))
            blocks.append(Block(btype, data))
            if last:
                break
        if not blocks or blocks[0].type != STREAMINFO:
            raise FormatError(tr("The FLAC file has no STREAMINFO block."))
        return blocks, f.tell(), start


def _comments(blocks: list[Block]) -> tuple[str, list[tuple[str, str]]]:
    for b in blocks:
        if b.type == VORBIS_COMMENT:
            vc = VComment(b.data, framing=False)
            return vc.vendor, [(k, v) for k, v in vc]
    return "", []


class FlacHandler(Handler):
    name = "FLAC"
    fields = vorbis.FIELDS
    picture_types = tuple(PICTURE_TYPES)

    def read(self, path):
        return read_safely(lambda: self._read(path))

    def _read(self, path):
        meta, status = TrackMetadata(), FileStatus(format=self.name)
        blocks, _, start = parse(path)
        if start:
            status.warnings.append(tr("There is an ID3 tag before the FLAC data; it will be removed on save."))
        _, comments = _comments(blocks)
        status.has_tags = bool(comments)
        vorbis.to_metadata(comments, meta)
        pics = [FlacPicture(b.data) for b in blocks if b.type == PICTURE]
        vorbis.apply_pictures(pics, meta)
        status.has_cover = bool(pics)
        status.chunk_labels = [_BLOCK_NAMES.get(b.type, str(b.type)) for b in blocks]
        return meta, status

    def fingerprint(self, path):
        blocks, audio_start, _ = parse(path)
        with open(path, "rb") as f:
            f.seek(0, 2)
            audio = hash_range(f, audio_start, f.tell()).hexdigest()
        return {"audio": audio, "STREAMINFO": hashlib.sha256(blocks[0].data).hexdigest()}

    def write(self, src, tmp, meta, options: SaveOptions, warnings):
        blocks, audio_start, _ = parse(src)
        vendor, existing = _comments(blocks)
        keep = [b for b in blocks[1:] if b.type not in (PADDING, VORBIS_COMMENT, PICTURE)]
        kept_pics = pictures_to_keep([b for b in blocks if b.type == PICTURE],
                                     lambda b: FlacPicture(b.data).type)

        vc = VComment()
        vc.vendor = vendor or "reference libFLAC"
        for key, value in vorbis.build(existing, meta):
            vc.append((key, value))
        new = [blocks[0]] + keep + [Block(VORBIS_COMMENT, vc.write(framing=False))]
        new += kept_pics
        for ptype, pic in sorted(meta.pictures.items()):
            if pic and pic.data:
                new.append(Block(PICTURE, vorbis.model_to_picture(ptype, pic).write()))
        new.append(Block(PADDING, bytes(NEW_PADDING)))

        with open(src, "rb") as f, open(tmp, "wb") as out:
            out.write(b"fLaC")
            for i, b in enumerate(new):
                if len(b.data) > MAX_BLOCK:
                    raise FormatError(tr("A FLAC metadata block would exceed 16 MB."))
                flag = 0x80 if i == len(new) - 1 else 0
                out.write(struct.pack(">B", flag | b.type) + len(b.data).to_bytes(3, "big"))
                out.write(b.data)
            copy_range(f, out, audio_start)


_BLOCK_NAMES = {0: "STREAMINFO", 1: "PADDING", 2: "APPLICATION", 3: "SEEKTABLE",
                4: "VORBIS_COMMENT", 5: "CUESHEET", 6: "PICTURE"}
