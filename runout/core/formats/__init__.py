"""Formatos admitidos y punto de entrada común para leer y guardar.

    from runout.core import formats
    meta, status = formats.read_track(path)
    result = formats.save_track(path, meta, dest, formats.SaveOptions(id3_version=3))
"""
from __future__ import annotations

import os

from ...i18n import tr
from ..model import FileStatus, TrackMetadata
from ..writer import SaveResult
from .base import FormatError, Handler, SaveOptions
from .flac import FlacHandler
from .id3file import AiffHandler, Mp3Handler
from .mp4 import Mp4Handler
from .ogg import OggHandler
from .wav import WavHandler

_WAV, _AIFF, _FLAC, _MP3, _MP4, _OGG = (WavHandler(), AiffHandler(), FlacHandler(), Mp3Handler(),
                                       Mp4Handler(), OggHandler())
HANDLERS: dict[str, Handler] = {
    ".wav": _WAV, ".wave": _WAV,
    ".aif": _AIFF, ".aiff": _AIFF, ".aifc": _AIFF,
    ".flac": _FLAC,
    ".mp3": _MP3,
    ".m4a": _MP4,
    ".ogg": _OGG, ".oga": _OGG, ".opus": _OGG,
}
EXTENSIONS = tuple(sorted(HANDLERS))

__all__ = ["EXTENSIONS", "FormatError", "Handler", "SaveOptions", "handler_for", "is_supported",
           "read_track", "save_track", "supported_fields", "picture_types"]


def is_supported(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in HANDLERS


def handler_for(path: str) -> Handler | None:
    return HANDLERS.get(os.path.splitext(path)[1].lower())


def read_track(path: str) -> tuple[TrackMetadata, FileStatus]:
    handler = handler_for(path)
    if handler is None:
        status = FileStatus(format="?")
        status.error = tr("Unsupported format.")
        return TrackMetadata(), status
    meta, status = handler.read(path)
    if meta.track is None:
        from ..reader import track_from_filename
        meta.set("track", track_from_filename(path))
    return meta, status


def save_track(src: str, meta: TrackMetadata, dest: str | None = None,
               options: SaveOptions | None = None, write_log: bool = True) -> SaveResult:
    handler = handler_for(src)
    if handler is None:
        return SaveResult(ok=False, source=src, dest=dest or src, message=tr("Unsupported format."))
    return handler.save(src, meta, dest, options, write_log)


def supported_fields(path: str) -> frozenset[str]:
    handler = handler_for(path)
    return handler.fields if handler else frozenset()


def picture_types(path: str) -> tuple[int, ...]:
    handler = handler_for(path)
    return handler.picture_types if handler else ()
