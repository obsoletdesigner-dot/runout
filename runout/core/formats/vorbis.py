"""Vorbis Comments (FLAC, Ogg Vorbis, Opus) <-> campos de la app.

La primera clave de cada lista es la que se escribe; todas se leen. Las claves que la
app no gestiona se muestran y conservan en «Campos libres» como CLAVE=valor.
"""
from __future__ import annotations

import base64

from mutagen.flac import Picture as FlacPicture

from ..fields import PICTURE_TYPES
from ..model import Picture, TrackMetadata

VORBIS_KEYS: dict[str, tuple[str, ...]] = {
    "title": ("TITLE",),
    "subtitle": ("VERSION", "SUBTITLE"),
    "grouping": ("GROUPING",),
    "album": ("ALBUM",),
    "album_artist": ("ALBUMARTIST", "ALBUM ARTIST"),
    "artist": ("ARTIST",),
    "label": ("LABEL", "ORGANIZATION", "PUBLISHER"),
    "copyright": ("COPYRIGHT",),
    "date": ("DATE",),
    "original_date": ("ORIGINALDATE",),
    "genre": ("GENRE",),
    "track": ("TRACKNUMBER",),
    "track_total": ("TRACKTOTAL", "TOTALTRACKS"),
    "disc": ("DISCNUMBER",),
    "disc_total": ("DISCTOTAL", "TOTALDISCS"),
    "disc_subtitle": ("DISCSUBTITLE",),
    "media": ("MEDIA",),
    "album_sort": ("ALBUMSORT",),
    "isrc": ("ISRC",),
    "language": ("LANGUAGE",),
    "bpm": ("BPM",),
    "key": ("INITIALKEY", "KEY"),
    "mood": ("MOOD",),
    "title_sort": ("TITLESORT",),
    "artist_sort": ("ARTISTSORT",),
    "comment": ("COMMENT", "DESCRIPTION"),
    "lyrics": ("LYRICS", "UNSYNCEDLYRICS"),
    "composer": ("COMPOSER",),
    "lyricist": ("LYRICIST",),
    "original_artist": ("ORIGINALARTIST",),
    "conductor": ("CONDUCTOR",),
    "remixer": ("REMIXER",),
    "encoded_by": ("ENCODEDBY",),
    "encoder_settings": ("ENCODERSETTINGS",),
    "catalog": ("CATALOGNUMBER",),
    "barcode": ("BARCODE", "UPC", "EAN"),
    "iswc": ("ISWC",),
    "release_country": ("RELEASECOUNTRY",),
    "release_type": ("RELEASETYPE",),
    "release_status": ("RELEASESTATUS",),
    "script": ("SCRIPT",),
    "rg_track_gain": ("REPLAYGAIN_TRACK_GAIN",),
    "rg_track_peak": ("REPLAYGAIN_TRACK_PEAK",),
    "rg_album_gain": ("REPLAYGAIN_ALBUM_GAIN",),
    "rg_album_peak": ("REPLAYGAIN_ALBUM_PEAK",),
    "mb_track_id": ("MUSICBRAINZ_RELEASETRACKID",),
    "mb_album_id": ("MUSICBRAINZ_ALBUMID",),
    "mb_artist_id": ("MUSICBRAINZ_ARTISTID",),
    "url_artist": ("WEBSITE", "URL"),
}
FIELDS = frozenset(VORBIS_KEYS) | {"custom_txxx"}
PICTURE_KEY = "METADATA_BLOCK_PICTURE"
# claves que no se muestran en «Campos libres»; ENCODER (lo pone el codificador) se conserva
_PRESERVED = {"ENCODER"}
_HIDDEN = {PICTURE_KEY, "COVERART", "COVERARTMIME"} | _PRESERVED
_MANAGED = {k for keys in VORBIS_KEYS.values() for k in keys} | _HIDDEN


def to_metadata(comments: list[tuple[str, str]], meta: TrackMetadata) -> None:
    """comments: pares (clave, valor) en el orden del archivo."""
    by_key: dict[str, list[str]] = {}
    for key, value in comments:
        by_key.setdefault(key.upper(), []).append(value)
    for field_key, keys in VORBIS_KEYS.items():
        for k in keys:
            if by_key.get(k):
                values = by_key[k]
                meta.set(field_key, values[0] if field_key in ("lyrics", "comment") else "; ".join(values))
                break
    for num_key, total_key in (("track", "track_total"), ("disc", "disc_total")):
        num, _, total = meta.get(num_key).partition("/")      # «3/12» también existe
        if total.strip().isdigit():
            meta.set(num_key, num.strip())
            if not meta.get(total_key):
                meta.set(total_key, total.strip())
        if meta.get(num_key).isdigit():
            meta.set(num_key, str(int(meta.get(num_key))))
    custom = ["%s=%s" % (k, v) for k, v in comments if k.upper() not in _MANAGED]
    if custom:
        meta.set("custom_txxx", "\n".join(custom))


def build(existing: list[tuple[str, str]], meta: TrackMetadata) -> list[tuple[str, str]]:
    """Nueva lista de comentarios, sin imágenes. Las claves gestionadas salen de `meta`,
    las libres del campo «Campos libres» y ENCODER se copia de `existing`."""
    out = [(k, v) for k, v in existing if k.upper() in _PRESERVED]
    for field_key, keys in VORBIS_KEYS.items():
        value = meta.get(field_key)
        if value:
            out.append((keys[0], value))
    for line in meta.get("custom_txxx").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            key = key.strip()
            if key and key.upper() not in _MANAGED and _valid_key(key):
                out.append((key, value.strip()))
    return out


def _valid_key(key: str) -> bool:
    # especificación Vorbis: ASCII 0x20-0x7D sin «=»
    return all(0x20 <= ord(c) <= 0x7D and c != "=" for c in key)


# --- imágenes (bloque PICTURE de FLAC, o METADATA_BLOCK_PICTURE en base64 en Ogg) ---------
def picture_to_model(pic: FlacPicture) -> tuple[int, Picture]:
    return pic.type, Picture(bytes(pic.data), pic.mime or "image/jpeg", pic.desc)


def model_to_picture(ptype: int, pic: Picture) -> FlacPicture:
    from ..cover import image_size
    out = FlacPicture()
    out.type = ptype
    out.mime = pic.mime or "image/jpeg"
    out.desc = pic.desc or PICTURE_TYPES.get(ptype, "")
    out.width, out.height, out.depth = image_size(pic.data)
    out.data = pic.data
    return out


def pictures_from_comments(comments: list[tuple[str, str]]) -> list[FlacPicture]:
    pics = []
    for key, value in comments:
        if key.upper() == PICTURE_KEY:
            try:
                pics.append(FlacPicture(base64.b64decode(value)))
            except Exception:
                continue
    return pics


def picture_comment(pic: FlacPicture) -> tuple[str, str]:
    return PICTURE_KEY, base64.b64encode(pic.write()).decode("ascii")


def apply_pictures(found: list[FlacPicture], meta: TrackMetadata) -> None:
    for pic in found:
        if pic.type in PICTURE_TYPES and pic.type not in meta.pictures:
            ptype, model = picture_to_model(pic)
            meta.pictures[ptype] = model
    if 3 not in meta.pictures and found and not any(p.type in PICTURE_TYPES for p in found):
        meta.pictures[3] = picture_to_model(found[0])[1]
