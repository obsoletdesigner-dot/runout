"""M4A / AAC / ALAC (contenedor MP4).

mutagen escribe sobre una copia temporal, nunca sobre el original. Al cambiar el
tamaño de «moov» puede moverse «mdat», y mutagen corrige las tablas de offsets
(stco/co64). La huella es el SHA-256 del contenido de todos los «mdat», el de las
tablas de muestras (códec, tamaños, tiempos) y el de la lista de offsets relativos al
principio del primer «mdat»: si mutagen moviera el audio sin corregir bien las tablas,
la huella cambiaría y el guardado se aborta.
"""
from __future__ import annotations

import hashlib
import shutil
import struct

from mutagen.mp4 import MP4, MP4Cover, MP4FreeForm

from ...i18n import tr
from ..model import FileStatus, Picture, TrackMetadata
from .base import FormatError, Handler, SaveOptions, hash_range, read_safely

TEXT_ATOMS = {
    "title": "\xa9nam", "artist": "\xa9ART", "album": "\xa9alb", "album_artist": "aART",
    "date": "\xa9day", "genre": "\xa9gen", "composer": "\xa9wrt", "copyright": "cprt",
    "comment": "\xa9cmt", "lyrics": "\xa9lyr", "encoder_settings": "\xa9too",
    "grouping": "\xa9grp", "album_sort": "soal", "artist_sort": "soar", "title_sort": "sonm",
}
FREEFORM = {   # ----:com.apple.iTunes:<nombre>, como Picard
    "isrc": "ISRC", "label": "LABEL", "catalog": "CATALOGNUMBER", "barcode": "BARCODE",
    "iswc": "ISWC", "language": "LANGUAGE", "mood": "MOOD", "key": "initialkey",
    "subtitle": "SUBTITLE", "disc_subtitle": "DISCSUBTITLE", "original_date": "ORIGINALDATE",
    "media": "MEDIA", "lyricist": "LYRICIST", "conductor": "CONDUCTOR", "remixer": "REMIXER",
    "encoded_by": "ENCODEDBY", "release_country": "MusicBrainz Album Release Country",
    "release_type": "MusicBrainz Album Type", "release_status": "MusicBrainz Album Status",
    "script": "SCRIPT", "rg_track_gain": "replaygain_track_gain",
    "rg_track_peak": "replaygain_track_peak", "rg_album_gain": "replaygain_album_gain",
    "rg_album_peak": "replaygain_album_peak", "mb_track_id": "MusicBrainz Release Track Id",
    "mb_album_id": "MusicBrainz Album Id", "mb_artist_id": "MusicBrainz Artist Id",
}
PREFIX = "----:com.apple.iTunes:"
FIELDS = frozenset(TEXT_ATOMS) | frozenset(FREEFORM) | {
    "bpm", "track", "track_total", "disc", "disc_total", "custom_txxx"}
_MANAGED_FREEFORM = {name.upper() for name in FREEFORM.values()}


# --- estructura ---------------------------------------------------------------------
def _atoms(f, start: int, end: int):
    pos = start
    while pos + 8 <= end:
        f.seek(pos)
        size, kind = struct.unpack(">I4s", f.read(8))
        header = 8
        if size == 1:
            size = struct.unpack(">Q", f.read(8))[0]
            header = 16
        elif size == 0:
            size = end - pos
        if size < header or pos + size > end:
            raise FormatError(tr("The MP4 structure is damaged."))
        yield kind, pos, header, size
        pos += size


def _sample_tables(f, start: int, end: int, out: list[int], tables, in_stbl=False) -> None:
    """Recorre moov: guarda los offsets de stco/co64 y hashea el resto de tablas de stbl
    (descripción del códec, tamaños y tiempos de las muestras), que nunca deben cambiar."""
    for kind, pos, header, size in _atoms(f, start, end):
        if kind in (b"moov", b"trak", b"mdia", b"minf", b"stbl"):
            _sample_tables(f, pos + header, pos + size, out, tables, kind == b"stbl")
        elif kind in (b"stco", b"co64"):
            f.seek(pos + header + 4)
            count = struct.unpack(">I", f.read(4))[0]
            fmt, width = (">I", 4) if kind == b"stco" else (">Q", 8)
            data = f.read(count * width)
            out.extend(struct.unpack_from(fmt, data, i * width)[0] for i in range(count))
        elif in_stbl:
            tables.update(kind)
            hash_range(f, pos, pos + size, tables)


def fingerprint(path: str) -> dict[str, str]:
    h = hashlib.sha256()
    tables = hashlib.sha256()
    offsets: list[int] = []
    first_mdat = None
    with open(path, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        for kind, pos, header, asize in _atoms(f, 0, size):
            if kind == b"mdat":
                if first_mdat is None:
                    first_mdat = pos + header
                hash_range(f, pos + header, pos + asize, h)
            elif kind == b"moov":
                _sample_tables(f, pos + header, pos + asize, offsets, tables)
    if first_mdat is None:
        raise FormatError(tr("No audio (mdat) found in the MP4 file."))
    rel = hashlib.sha256(b"".join(struct.pack(">q", o - first_mdat) for o in offsets))
    return {"audio": h.hexdigest(), "sample offsets": rel.hexdigest(),
            "sample tables": tables.hexdigest()}


# --- etiquetas ----------------------------------------------------------------------
def _text(value) -> str:
    if isinstance(value, MP4FreeForm) or isinstance(value, bytes):
        return bytes(value).decode("utf-8", "replace")
    return str(value)


class Mp4Handler(Handler):
    name = "M4A"
    fields = FIELDS
    picture_types = (3,)         # MP4 solo tiene «covr» (portada)

    def read(self, path):
        return read_safely(lambda: self._read(path))

    def _read(self, path):
        audio = MP4(path)
        tags = audio.tags or {}
        meta = TrackMetadata()
        status = FileStatus(format="M4A (%s)" % getattr(audio.info, "codec", "mp4"))
        status.has_tags = bool(tags)
        for key, atom in TEXT_ATOMS.items():
            if tags.get(atom):
                meta.set(key, "; ".join(str(v) for v in tags[atom]) if key != "lyrics" else str(tags[atom][0]))
        for key, name in FREEFORM.items():
            values = tags.get(PREFIX + name)
            if values:
                meta.set(key, "; ".join(_text(v) for v in values))
        if tags.get("tmpo"):
            meta.set("bpm", str(tags["tmpo"][0]))
        for atom, num_key, total_key in (("trkn", "track", "track_total"), ("disk", "disc", "disc_total")):
            if tags.get(atom):
                num, total = tags[atom][0]
                meta.set(num_key, num or None)
                meta.set(total_key, total or None)
        custom = []
        for k, values in tags.items():
            if k.startswith(PREFIX) and k[len(PREFIX):].upper() not in _MANAGED_FREEFORM:
                custom.append("%s=%s" % (k[len(PREFIX):], "; ".join(_text(v) for v in values)))
        if custom:
            meta.set("custom_txxx", "\n".join(custom))
        covers = tags.get("covr") or []
        if covers:
            c = covers[0]
            mime = "image/png" if c.imageformat == MP4Cover.FORMAT_PNG else "image/jpeg"
            meta.pictures[3] = Picture(bytes(c), mime)
            status.has_cover = True
        return meta, status

    def fingerprint(self, path):
        return fingerprint(path)

    def write(self, src, tmp, meta, options: SaveOptions, warnings):
        shutil.copyfile(src, tmp)
        audio = MP4(tmp)
        if audio.tags is None:
            audio.add_tags()
        tags = audio.tags
        for atom in list(TEXT_ATOMS.values()) + ["tmpo", "trkn", "disk", "covr"]:
            tags.pop(atom, None)
        for k in [k for k in tags if k.startswith(PREFIX)]:
            del tags[k]
        for key, atom in TEXT_ATOMS.items():
            if meta.get(key):
                tags[atom] = [meta.get(key)]
        for key, name in FREEFORM.items():
            if meta.get(key):
                tags[PREFIX + name] = [MP4FreeForm(meta.get(key).encode("utf-8"))]
        if meta.get("bpm").isdigit():
            tags["tmpo"] = [min(int(meta.get("bpm")), 65535)]
        for atom, num_key, total_key in (("trkn", "track", "track_total"), ("disk", "disc", "disc_total")):
            num, total = meta.int(num_key), meta.int(total_key)
            if num or total:
                tags[atom] = [(num or 0, total or 0)]
        for line in meta.get("custom_txxx").splitlines():
            if "=" in line:
                name, value = line.split("=", 1)
                name = name.strip()
                if name and name.upper() not in _MANAGED_FREEFORM:
                    tags[PREFIX + name] = [MP4FreeForm(value.strip().encode("utf-8"))]
        cover = meta.pictures.get(3)
        if cover and cover.data:
            fmt = MP4Cover.FORMAT_PNG if cover.mime == "image/png" else MP4Cover.FORMAT_JPEG
            tags["covr"] = [MP4Cover(cover.data, imageformat=fmt)]
        audio.save()
