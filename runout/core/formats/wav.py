"""WAV: usa el lector y el escritor RIFF propios (reader.py y writer.py)."""
from __future__ import annotations

from .. import reader, writer
from ..fields import FIELDS, PICTURE_TYPES
from ..riff import parse, sha256_chunk
from .base import Handler, SaveOptions


class WavHandler(Handler):
    name = "WAV"
    fields = frozenset(f.key for f in FIELDS)
    picture_types = tuple(PICTURE_TYPES)

    def read(self, path):
        return reader.read_track(path)

    def fingerprint(self, path):
        info = parse(path)
        return {"audio": sha256_chunk(path, info.data), "fmt": sha256_chunk(path, info.fmt)}

    def save(self, src, meta, dest=None, options=None, write_log=True):
        options = options or SaveOptions()
        return writer.save_track(src, meta, dest=dest, id3_version=options.id3_version,
                                 write_log=write_log, info_encoding=options.info_encoding)
