"""Registro de todos los campos editables y su destino en cada capa.

Fuente: docs/listado_completo_de_metadatos_de_audio_por_estandar.txt
(secciones 1 a 4 y tabla maestra). La sección 5 (Vorbis) no aplica a WAV.

Cada campo dice dónde se escribe:
  id3      frame ID3 ("TIT2", "TXXX:CATALOGNUMBER", "WPUB", ...)
  id3_v23  alternativa cuando el frame solo existe en ID3v2.4
  info     subchunk de LIST-INFO
  axml     elemento EBUCore gestionado
  bext     campo del chunk bext
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    tab: str
    kind: str = "text"
    id3: str | None = None
    id3_v23: str | None = None
    info: str | None = None
    axml: str | None = None
    bext: str | None = None
    choices: tuple[tuple[str, str], ...] = ()   # (valor, etiqueta)
    maxlen: int | None = None
    readonly: bool = False
    help: str = ""


TABS = ["Album", "Track", "Credits", "Identifiers", "Web links", "RIFF INFO", "BWF (bext)",
        "Images", "Custom"]

MEDIA_CHOICES = (
    ("", ""), ("DIG", "DIG · Digital"), ("CD", "CD"), ("CD/A", "Audio CD"),
    ("TT/33", "Vinyl 33 rpm"), ("TT/45", "Vinyl 45 rpm"), ("MC", "Cassette"),
    ("DAT", "DAT"), ("MD", "MiniDisc"), ("DVD", "DVD"), ("ANA", "Analogue"),
    ("RAD", "Radio"), ("TV", "Television"), ("VID", "Video"), ("REE", "Reel-to-reel tape"),
)
RELEASE_TYPES = (("", ""), ("album", "album"), ("single", "single"), ("ep", "ep"),
                 ("compilation", "compilation"), ("broadcast", "broadcast"), ("other", "other"))
RELEASE_STATUS = (("", ""), ("official", "official"), ("promotion", "promotion"),
                  ("bootleg", "bootleg"), ("pseudo-release", "pseudo-release"))

F = Field
FIELDS: list[Field] = [
    # ---------------- Álbum (valores comunes a todo el lanzamiento) -------------
    F("album", "Album", "Album", id3="TALB", info="IPRD"),
    F("album_artist", "Album artist", "Album", id3="TPE2"),
    F("artist", "Artist", "Album", id3="TPE1", info="IART", axml="creator"),
    F("label", "Label / Publisher", "Album", id3="TPUB", axml="publisher"),
    F("copyright", "Copyright ©", "Album", id3="TCOP", info="ICOP", axml="rights",
      help="e.g. © 2026 Example Records"),
    F("produced_notice", "Phonogram ℗", "Album", id3="TPRO", id3_v23="TXXX:PRODUCEDNOTICE",
      help="e.g. ℗ 2026 Example Records"),
    F("date", "Date / Year", "Album", "date", id3="TDRC", info="ICRD", axml="date",
      help="YYYY or YYYY-MM-DD"),
    F("original_date", "Original date", "Album", "date", id3="TDOR",
      help="ID3v2.3 only stores the year (TORY)."),
    F("release_time", "Official release date", "Album", "datetime", id3="TDRL",
      id3_v23="TXXX:RELEASETIME"),
    F("genre", "Genre", "Album", id3="TCON", info="IGNR"),
    F("track_total", "Total tracks", "Album", "count"),
    F("disc", "Disc number", "Album", "count"),
    F("disc_total", "Total discs", "Album", "count"),
    F("disc_subtitle", "Disc subtitle", "Album", id3="TSST", id3_v23="TXXX:SETSUBTITLE"),
    F("original_album", "Original album", "Album", id3="TOAL"),
    F("media", "Original media", "Album", "media", id3="TMED", info="IMED", choices=MEDIA_CHOICES),
    F("album_sort", "Album sort order", "Album", id3="TSOA",
      help="e.g. “Beatles, The”"),

    # ---------------- Pista -------------------------------------------------------
    F("track", "Track number", "Track", "count", info="ITRK"),
    F("title", "Title", "Track", id3="TIT2", info="INAM", axml="title"),
    F("subtitle", "Subtitle / version", "Track", id3="TIT3"),
    F("grouping", "Grouping / work", "Track", id3="TIT1"),
    F("isrc", "ISRC", "Track", "isrc", id3="TSRC", axml="isrc"),
    F("language", "Language (ISO 639-3)", "Track", "language", id3="TLAN", axml="language",
      help="3-letter code: eng, spa, fra, deu, cat…"),
    F("bpm", "BPM", "Track", "bpm", id3="TBPM"),
    F("key", "Key", "Track", "musickey", id3="TKEY", help="Am, F#m, C, Bb… (“o” = atonal)"),
    F("mood", "Mood", "Track", id3="TMOO", id3_v23="TXXX:MOOD"),
    F("title_sort", "Title sort order", "Track", id3="TSOT"),
    F("artist_sort", "Artist sort order", "Track", id3="TSOP"),
    F("comment", "Comment / sync contact", "Track", "multiline", id3="COMM", info="ICMT"),
    F("lyrics", "Lyrics", "Track", "multiline", id3="USLT"),

    # ---------------- Créditos ----------------------------------------------------
    F("composer", "Composer", "Credits", id3="TCOM"),
    F("lyricist", "Lyricist", "Credits", id3="TEXT"),
    F("original_lyricist", "Original lyricist", "Credits", id3="TOLY"),
    F("original_artist", "Original artist", "Credits", id3="TOPE"),
    F("conductor", "Conductor", "Credits", id3="TPE3"),
    F("remixer", "Remixer", "Credits", id3="TPE4"),
    F("involved_people", "Involved people", "Credits", "people", id3="TIPL",
      help="One per line: “role: name” (e.g. mastering: Jane Doe)"),
    F("musician_credits", "Musicians and instruments", "Credits", "people", id3="TMCL",
      help="One per line: “instrument: name”. In ID3v2.3 it is merged with Involved people."),
    F("encoded_by", "Encoded by", "Credits", id3="TENC"),
    F("encoder_settings", "Encoder settings", "Credits", id3="TSSE"),
    F("file_owner", "File owner / licensee", "Credits", id3="TOWN"),
    F("radio_name", "Internet radio station", "Credits", id3="TRSN"),
    F("radio_owner", "Radio station owner", "Credits", id3="TRSO"),
    F("encoding_time", "Encoding time", "Credits", "datetime", id3="TDEN",
      id3_v23="TXXX:ENCODINGTIME"),
    F("tagging_time", "Tagging time", "Credits", "datetime", id3="TDTG",
      id3_v23="TXXX:TAGGINGTIME"),

    # ---------------- Identificadores ---------------------------------------------
    F("catalog", "Catalogue number", "Identifiers", "oneline", id3="TXXX:CATALOGNUMBER",
      axml="catalog", help="e.g. EXR-001"),
    F("barcode", "UPC / EAN", "Identifiers", "gtin", id3="TXXX:BARCODE", axml="barcode"),
    F("iswc", "ISWC", "Identifiers", "iswc", id3="TXXX:ISWC", axml="iswc",
      help="T-123.456.789-C"),
    F("release_country", "Release country", "Identifiers", "country",
      id3="TXXX:RELEASECOUNTRY", help="ISO 3166-1 alpha-2: US, GB, ES…"),
    F("release_type", "Release type", "Identifiers", "choice",
      id3="TXXX:RELEASETYPE", choices=RELEASE_TYPES),
    F("release_status", "Release status", "Identifiers", "choice",
      id3="TXXX:RELEASESTATUS", choices=RELEASE_STATUS),
    F("script", "Script (ISO 15924)", "Identifiers", "script", id3="TXXX:SCRIPT",
      help="e.g. Latn"),
    F("rg_track_gain", "ReplayGain track gain", "Identifiers", "gain",
      id3="TXXX:REPLAYGAIN_TRACK_GAIN", help="e.g. -6.52 dB"),
    F("rg_track_peak", "ReplayGain track peak", "Identifiers", "peak",
      id3="TXXX:REPLAYGAIN_TRACK_PEAK", help="e.g. 0.988547"),
    F("rg_album_gain", "ReplayGain album gain", "Identifiers", "gain",
      id3="TXXX:REPLAYGAIN_ALBUM_GAIN"),
    F("rg_album_peak", "ReplayGain album peak", "Identifiers", "peak",
      id3="TXXX:REPLAYGAIN_ALBUM_PEAK"),
    F("mb_track_id", "MusicBrainz Track Id", "Identifiers", "uuid",
      id3="TXXX:MusicBrainz Release Track Id"),
    F("mb_album_id", "MusicBrainz Album Id", "Identifiers", "uuid",
      id3="TXXX:MusicBrainz Album Id"),
    F("mb_artist_id", "MusicBrainz Artist Id", "Identifiers", "uuid",
      id3="TXXX:MusicBrainz Artist Id"),

    # ---------------- Webs -----------------------------------------------------------
    F("url_commercial", "Store (WCOM)", "Web links", "url", id3="WCOM"),
    F("url_copyright", "Copyright info (WCOP)", "Web links", "url", id3="WCOP"),
    F("url_file", "File web page (WOAF)", "Web links", "url", id3="WOAF"),
    F("url_artist", "Artist web page (WOAR)", "Web links", "url", id3="WOAR"),
    F("url_source", "Source web page (WOAS)", "Web links", "url", id3="WOAS"),
    F("url_radio", "Radio station web page (WORS)", "Web links", "url", id3="WORS"),
    F("url_payment", "Payment / purchase (WPAY)", "Web links", "url", id3="WPAY"),
    F("url_publisher", "Label web page (WPUB)", "Web links", "url", id3="WPUB"),
    F("url_user", "Custom URL (WXXX)", "Web links", "url", id3="WXXX"),

    # ---------------- RIFF LIST-INFO (sin equivalente en otras capas) -----------------
    F("engineer", "Engineer / mastering (IENG)", "RIFF INFO", "oneline", info="IENG"),
    F("software", "Software (ISFT)", "RIFF INFO", "oneline", info="ISFT"),
    F("info_source", "Source (INFO/ISRC)", "RIFF INFO", "oneline", info="ISRC",
      help="In RIFF, “ISRC” means Source (supplier), NOT the ISRC code."),
    F("keywords", "Keywords (IKEY)", "RIFF INFO", "oneline", info="IKEY"),
    F("subject", "Subject (ISBJ)", "RIFF INFO", "oneline", info="ISBJ"),
    F("source_form", "Source form (ISRF)", "RIFF INFO", "oneline", info="ISRF"),
    F("technician", "Digitisation technician (ITCH)", "RIFF INFO", "oneline", info="ITCH"),
    F("archival_location", "Archival location (IARL)", "RIFF INFO", "oneline", info="IARL"),
    F("commissioned", "Commissioned by (ICMS)", "RIFF INFO", "oneline", info="ICMS"),

    # ---------------- BWF bext ----------------------------------------------------------
    F("bext_description", "Description", "BWF (bext)", "ascii", bext="description", maxlen=256),
    F("bext_originator", "Originator", "BWF (bext)", "ascii", bext="originator", maxlen=32),
    F("bext_originator_ref", "Originator reference", "BWF (bext)", "ascii",
      bext="originator_reference", maxlen=32),
    F("bext_date", "Origination date", "BWF (bext)", "isodate", bext="origination_date",
      help="YYYY-MM-DD"),
    F("bext_time", "Origination time", "BWF (bext)", "isotime", bext="origination_time",
      help="HH:MM:SS"),
    F("bext_loudness", "Integrated loudness (LUFS)", "BWF (bext)", "lufs", bext="loudness_value",
      help="e.g. -14.0"),
    F("bext_lra", "Loudness range (LU)", "BWF (bext)", "lra", bext="loudness_range"),
    F("bext_true_peak", "Max true peak (dBTP)", "BWF (bext)", "dbtp", bext="max_true_peak"),
    F("bext_max_momentary", "Max momentary loudness (LUFS)", "BWF (bext)", "lufs",
      bext="max_momentary"),
    F("bext_max_short_term", "Max short-term loudness (LUFS)", "BWF (bext)", "lufs",
      bext="max_short_term"),
    F("bext_coding_history", "Coding history", "BWF (bext)", "ascii_multiline",
      bext="coding_history"),
    F("bext_time_reference", "TimeReference (samples)", "BWF (bext)", readonly=True,
      bext="time_reference", help="Read-only: changing it would move the clip in a DAW."),
    F("bext_umid", "UMID", "BWF (bext)", readonly=True, bext="umid", help="Read-only."),

    # ---------------- Personalizados ------------------------------------------------------
    F("custom_txxx", "Free TXXX fields", "Custom", "keyvalue",
      help="One per line: KEY=value"),
]
del F

BY_KEY: dict[str, Field] = {f.key: f for f in FIELDS}

# Imágenes APIC gestionadas: tipo -> etiqueta
PICTURE_TYPES: dict[int, str] = {
    3: "Front cover",
    4: "Back cover",
    8: "Artist photo",
    20: "Label logo",
}

# Frames ID3 que la app gestiona por otras vías
SPECIAL_ID3 = {"TRCK", "TPOS", "APIC", "TLEN", "COMM", "USLT", "TXXX"}


def fields_in_tab(tab: str) -> list[Field]:
    return [f for f in FIELDS if f.tab == tab]


def managed_txxx() -> set[str]:
    """Descripciones TXXX que tienen campo propio (no van a «Personalizados»)."""
    out = set()
    for f in FIELDS:
        for spec in (f.id3, f.id3_v23):
            if spec and spec.startswith("TXXX:"):
                out.add(spec[5:].upper())
    return out
