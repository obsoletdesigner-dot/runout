"""Ogg Vorbis y Opus.

Aquí sí escribe mutagen, pero nunca sobre el original: se copia el archivo a un
temporal y mutagen reescribe en él los paquetes de cabecera (los comentarios). Las
páginas pueden cambiar de número de secuencia y de CRC, así que la huella no se hace
sobre las páginas sino sobre los paquetes: todos menos el de comentarios (la cabecera
de identificación, la de configuración de Vorbis y el audio), con su longitud, más la
posición (granule) de cada página de audio, en orden.
"""
from __future__ import annotations

import hashlib
import shutil
import struct

from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis

from ...i18n import tr
from ..fields import PICTURE_TYPES
from ..model import FileStatus, TrackMetadata
from . import vorbis
from .base import FormatError, Handler, SaveOptions, read_safely

HEADER_PACKETS = {b"\x01vorbis": 3, b"OpusHead": 2}   # paquetes de cabecera de cada códec
COMMENT_PACKET = 1                                      # el único que cambia al etiquetar


def _pages(f):
    """(serial, granule, segment table, cuerpo, flags) de cada página."""
    while True:
        head = f.read(27)
        if not head:
            return
        if len(head) < 27 or head[:4] != b"OggS":
            raise FormatError(tr("The Ogg stream is damaged."))
        flags = head[5]
        granule, serial = struct.unpack("<qI", head[6:18])
        lacing = f.read(head[26])
        body = f.read(sum(lacing))
        if len(lacing) < head[26] or len(body) < sum(lacing):
            raise FormatError(tr("The Ogg stream is damaged."))
        yield serial, granule, lacing, body, flags


def audio_hash(path: str) -> str:
    h = hashlib.sha256()
    serial0 = None
    packet = b""
    index = 0
    skip = None
    with open(path, "rb") as f:
        for serial, granule, lacing, body, _ in _pages(f):
            if serial0 is None:
                serial0 = serial
            elif serial != serial0:
                raise FormatError(tr("Ogg files with more than one stream are not supported."))
            pos = 0
            for seg in lacing:
                packet += body[pos:pos + seg]
                pos += seg
                if seg < 255:            # fin de paquete
                    if skip is None:
                        skip = next((n for magic, n in HEADER_PACKETS.items()
                                     if packet.startswith(magic)), None)
                        if skip is None:
                            raise FormatError(tr("Unknown Ogg codec (only Vorbis and Opus)."))
                    if index != COMMENT_PACKET:
                        h.update(struct.pack("<I", len(packet)))
                        h.update(packet)
                    index += 1
                    packet = b""
            if index > (skip or 0):
                h.update(struct.pack("<q", granule))
    return h.hexdigest()


class OggHandler(Handler):
    name = "Ogg"
    fields = vorbis.FIELDS
    picture_types = tuple(PICTURE_TYPES)

    def _open(self, path):
        with open(path, "rb") as f:
            f.seek(28)
            magic = f.read(8)
        if magic.startswith(b"\x01vorbis"):
            return OggVorbis(path), "Ogg Vorbis"
        if magic == b"OpusHead":
            return OggOpus(path), "Opus"
        raise FormatError(tr("Unknown Ogg codec (only Vorbis and Opus)."))

    def read(self, path):
        return read_safely(lambda: self._read(path))

    def _read(self, path):
        audio, fmt = self._open(path)
        meta, status = TrackMetadata(), FileStatus(format=fmt)
        comments = list(audio.tags or [])
        status.has_tags = any(k.upper() != "ENCODER" for k, _ in comments)
        vorbis.to_metadata(comments, meta)
        pics = vorbis.pictures_from_comments(comments)
        vorbis.apply_pictures(pics, meta)
        status.has_cover = bool(pics)
        return meta, status

    def fingerprint(self, path):
        return {"audio": audio_hash(path)}

    def write(self, src, tmp, meta, options: SaveOptions, warnings):
        shutil.copyfile(src, tmp)
        audio, _ = self._open(tmp)
        existing = list(audio.tags or [])
        kept_pics = [p for p in vorbis.pictures_from_comments(existing)
                     if p.type not in self.picture_types]
        new = vorbis.build(existing, meta)
        new += [vorbis.picture_comment(p) for p in kept_pics]
        for ptype, pic in sorted(meta.pictures.items()):
            if pic and pic.data:
                new.append(vorbis.picture_comment(vorbis.model_to_picture(ptype, pic)))
        audio.tags.clear()
        audio.tags.extend(new)
        audio.save()
