"""Lectura de las tres capas de metadatos de un WAV."""
from __future__ import annotations

import os
import re

from ..i18n import tr
from . import axml, bext, id3chunk, listinfo
from .model import FileStatus, TrackMetadata
from .riff import RiffError, parse, read_chunk_bytes

_LEADING_NUMBER = re.compile(r"^\s*(\d{1,3})(?!\d)")


def track_from_filename(path: str) -> int | None:
    m = _LEADING_NUMBER.match(os.path.basename(path))
    return int(m.group(1)) if m else None


def read_track(path: str) -> tuple[TrackMetadata, FileStatus]:
    """Lee ID3 > axml > LIST-INFO. Nunca escribe nada."""
    meta = TrackMetadata()
    status = FileStatus()
    try:
        info = parse(path)
    except (RiffError, OSError) as exc:
        status.error = str(exc)
        return meta, status
    status.warnings.extend(info.warnings)
    status.chunk_labels = [c.label for c in info.chunks]

    id3_chunks = info.id3_chunks()
    if len(id3_chunks) > 1:
        status.warnings.append(tr("There are %d ID3 chunks; only one will be kept on save.") % len(id3_chunks))
    if id3_chunks:
        tag = id3chunk.load(read_chunk_bytes(path, id3_chunks[0]))
        if tag is not None:
            status.has_id3 = status.has_tags = True
            status.has_cover = id3chunk.has_cover(tag)
            id3chunk.to_metadata(tag, meta)
        else:
            status.warnings.append(tr("The existing ID3 chunk cannot be read; it will be replaced."))

    axml_chunk = info.first(b"axml")
    if axml_chunk is not None:
        fields = axml.read_fields(read_chunk_bytes(path, axml_chunk))
        isrc = fields.get("isrc", "")
        if isrc:
            status.has_axml_isrc = True
            if meta.isrc and meta.isrc != isrc:
                status.warnings.append(
                    tr("The axml ISRC (%s) does not match the ID3 one (%s); the ID3 one will be used.")
                    % (isrc, meta.isrc))
        for key, value in fields.items():
            if not meta.get(key):
                meta.set(key, value)

    bext_chunk = info.first(b"bext")
    if bext_chunk is not None:
        status.has_bext = True
        bext.to_metadata(read_chunk_bytes(path, bext_chunk), meta)

    lists = info.info_lists()
    if lists:
        status.has_info = True
        listinfo.to_metadata(listinfo.parse(read_chunk_bytes(path, lists[0])), meta)

    if meta.track is None:
        meta.set("track", track_from_filename(path))
    return meta, status
