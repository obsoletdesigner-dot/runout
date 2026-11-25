"""Todos los campos del listado: ida y vuelta en ID3v2.3/v2.4 y validadores."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from make_test_wavs import build_all  # noqa: E402
from test_core import PNG, structural_check  # noqa: E402
from runout.core import bext, id3chunk, listinfo, writer  # noqa: E402
from runout.core.fields import FIELDS  # noqa: E402
from runout.core.model import Picture  # noqa: E402
from runout.core.reader import read_track  # noqa: E402
from runout.core.riff import parse, read_chunk_bytes, sha256_chunk  # noqa: E402
from runout.core.validators import normalize, problem, validate_values  # noqa: E402

ALL = {
    "album": "La buena gente", "album_artist": "Varios", "artist": "Artista Ñ",
    "label": "Discos Ejemplo", "copyright": "© 2026 Discos Ejemplo",
    "produced_notice": "℗ 2026 Discos Ejemplo", "date": "2026-11-25",
    "original_date": "2019-05-01", "release_time": "2026-12-01T00:00", "genre": "Flamenco",
    "track_total": "10", "disc": "1", "disc_total": "2", "disc_subtitle": "Directo",
    "original_album": "Álbum original", "media": "DIG", "album_sort": "Buena gente, La",
    "track": "2", "title": "La buena gente siempre gana", "subtitle": "Remaster 2026",
    "grouping": "Obra I", "isrc": "ESABC2600001", "language": "spa", "bpm": "128",
    "key": "F#m", "mood": "Energetic", "title_sort": "Buena gente siempre gana, La",
    "artist_sort": "Artista, Ñ", "comment": "Sync: sync@sello.example\nTel. 600",
    "lyrics": "Primera línea\nSegunda línea", "composer": "Compositora", "lyricist": "Letrista",
    "original_lyricist": "Letrista original", "original_artist": "Artista original",
    "conductor": "Director", "remixer": "Remixer", "involved_people": "mastering: Ana Ruiz",
    "musician_credits": "guitarra: Pepe", "encoded_by": "Estudio", "encoder_settings": "Runout",
    "file_owner": "Discos Ejemplo", "radio_name": "Radio X", "radio_owner": "Grupo X",
    "encoding_time": "2026-11-20", "tagging_time": "2026-11-25T12:00:00",
    "catalog": "DEJ-001", "barcode": "8435123456786", "iswc": "T-034.524.680-1",
    "release_country": "ES", "release_type": "album", "release_status": "official",
    "script": "Latn", "rg_track_gain": "-6.52 dB", "rg_track_peak": "0.988547",
    "rg_album_gain": "-7.10 dB", "rg_album_peak": "0.999",
    "mb_track_id": "0d2a7ba8-3e1a-4d6c-9a7c-1c3f0f6a5b11",
    "mb_album_id": "1d2a7ba8-3e1a-4d6c-9a7c-1c3f0f6a5b11",
    "mb_artist_id": "2d2a7ba8-3e1a-4d6c-9a7c-1c3f0f6a5b11",
    "url_commercial": "https://tienda.example/x", "url_copyright": "https://ex.example/legal",
    "url_file": "https://ex.example/f", "url_artist": "https://artista.example",
    "url_source": "https://ex.example/s", "url_radio": "https://radio.example",
    "url_payment": "https://pay.example", "url_publisher": "https://sello.example",
    "url_user": "https://ex.example/u",
    "engineer": "Ingeniero", "software": "Pro Tools", "info_source": "Ejemplo",
    "keywords": "flamenco; fusión", "subject": "Single", "source_form": "Master",
    "technician": "Técnico", "archival_location": "Estantería 3", "commissioned": "Sello",
    "bext_description": "Master final", "bext_originator": "Ejemplo Mastering",
    "bext_originator_ref": "DEJ0001", "bext_date": "2026-11-25", "bext_time": "12:30:00",
    "bext_loudness": "-14.00", "bext_lra": "6.50", "bext_true_peak": "-1.00",
    "bext_max_momentary": "-9.20", "bext_max_short_term": "-11.30",
    "bext_coding_history": "A=PCM,F=44100,W=24,M=stereo,T=Master",
    "custom_txxx": "PROYECTO=Disco 2026\nSYNC_CONTACT=sync@sello.example",
}

V23_DIFFERENT = {
    "original_date": "2019",                         # TORY solo guarda el año
    "involved_people": "mastering: Ana Ruiz\nguitarra: Pepe",   # TIPL+TMCL -> IPLS
    "musician_credits": "",
    "date": "2026-11-25",
}


def test_every_valid_value_passes_validation():
    assert validate_values(ALL) == {}
    assert {f.key for f in FIELDS if not f.readonly} <= set(ALL) | {"bext_time_reference", "bext_umid"}


@pytest.mark.parametrize("version", [3, 4])
def test_all_fields_roundtrip(tmp_path, version):
    src = build_all(str(tmp_path))["02 - odd_bwf.wav"]
    before = parse(src)
    data_hash = sha256_chunk(src, before.data)
    time_ref_before = read_track(src)[0].get("bext_time_reference")

    meta = read_track(src)[0]
    meta.values.update(ALL)
    meta.pictures = {3: Picture(PNG, "image/png"), 4: Picture(PNG, "image/png"),
                     8: Picture(PNG, "image/png"), 20: Picture(PNG, "image/png")}
    res = writer.save_track(src, meta, id3_version=version)
    assert res.ok, res.message
    structural_check(src)
    assert sha256_chunk(src, parse(src).data) == data_hash

    back = read_track(src)[0]
    expected = dict(ALL)
    if version == 3:
        expected.update(V23_DIFFERENT)
    for key, value in expected.items():
        assert back.get(key) == value, (key, back.get(key), value)
    assert set(back.pictures) == {3, 4, 8, 20}
    assert back.get("bext_time_reference") == time_ref_before   # nunca se toca

    info = parse(src)
    labels = [c.label for c in info.chunks]
    assert labels.index("axml") == labels.index("data") - 1
    items = dict(listinfo.parse(read_chunk_bytes(src, info.info_lists()[0])))
    assert items[b"ISRC"] == b"Ejemplo\x00"                     # Fuente, nunca el código
    assert items[b"IENG"] == b"Ingeniero\x00"
    tag = id3chunk.load(read_chunk_bytes(src, info.id3_chunks()[0]))
    assert int(tag["TLEN"].text[0]) == 22051 * 1000 // 44100   # duración calculada
    if version == 3:
        assert "TSOA" in tag and "TXXX:MOOD" in tag and "TMOO" not in tag
    else:
        assert "TMOO" in tag and "TSST" in tag and "TDRL" in tag
    b = bext.parse(read_chunk_bytes(src, info.first(b"bext")))
    assert b["version"] == "2" and b["loudness_value"] == "-14.00"


def test_clearing_fields_removes_them(tmp_path):
    src = build_all(str(tmp_path))["01 - plain.wav"]
    meta = read_track(src)[0]
    meta.values.update(ALL)
    assert writer.save_track(src, meta).ok
    meta = read_track(src)[0]
    for key in ("mood", "catalog", "url_artist", "lyrics", "engineer"):
        meta.set(key, "")
    assert writer.save_track(src, meta).ok
    back = read_track(src)[0]
    for key in ("mood", "catalog", "url_artist", "lyrics", "engineer"):
        assert back.get(key) == "", key
    assert back.get("title") == ALL["title"]


def test_new_bext_goes_first_and_unchanged_bext_is_byte_exact(tmp_path):
    paths = build_all(str(tmp_path))
    src = paths["01 - plain.wav"]
    meta = read_track(src)[0]
    meta.set("bext_description", "Nuevo")
    assert writer.save_track(src, meta).ok
    assert parse(src).chunks[0].label == "bext"
    src2 = paths["02 - odd_bwf.wav"]
    old = read_chunk_bytes(src2, parse(src2).first(b"bext"))
    meta2 = read_track(src2)[0]
    meta2.set("title", "Solo cambia el título")
    assert writer.save_track(src2, meta2).ok
    assert read_chunk_bytes(src2, parse(src2).first(b"bext")) == old


def test_invalid_values_block_saving(tmp_path):
    src = build_all(str(tmp_path))["01 - plain.wav"]
    original = open(src, "rb").read()
    meta = read_track(src)[0]
    meta.set("language", "español")
    res = writer.save_track(src, meta)
    assert not res.ok and "Language" in res.message
    assert open(src, "rb").read() == original


@pytest.mark.parametrize("key,value,ok", [
    ("language", "spa", True), ("language", "cat", True), ("language", "eus", True),
    ("language", "fre", True), ("language", "es", False), ("language", "xyz", False),
    ("release_country", "ES", True), ("release_country", "XX", False),
    ("script", "Latn", True), ("script", "Abcd", False),
    ("barcode", "8435123456786", True), ("barcode", "8435123456787", False),
    ("barcode", "036000291452", True), ("barcode", "12345", False),
    ("iswc", "T-034.524.680-1", True), ("iswc", "T-034.524.680-2", False),
    ("date", "2026", True), ("date", "2026-02-30", False), ("date", "25/11/2026", False),
    ("release_time", "2026-11-25T23:59", True), ("release_time", "2026-11-25T25:00", False),
    ("bpm", "128", True), ("bpm", "0", False), ("bpm", "12.5", False),
    ("key", "F#m", True), ("key", "Bb", True), ("key", "H", False),
    ("url_artist", "https://a.example", True), ("url_artist", "www.a.com", False),
    ("rg_track_gain", "-6.52 dB", True), ("rg_track_gain", "-6,52", False),
    ("bext_description", "Sin tildes", True), ("bext_description", "Canción", False),
    ("bext_originator", "x" * 33, False), ("bext_loudness", "-14", True),
    ("bext_loudness", "3", False), ("media", "TT/33", True), ("media", "VINYL", False),
    ("mb_album_id", "nope", False), ("involved_people", "mastering Ana", False),
    ("custom_txxx", "CLAVE=valor", True), ("custom_txxx", "sin igual", False),
    ("track", "0", False), ("title", "dos\nlíneas", False),
])
def test_validators(key, value, ok):
    assert (problem(key, value) is None) == ok, problem(key, value)


def test_normalizers():
    assert normalize("isrc", "es-abc-26-00001") == "ESABC2600001"
    assert normalize("iswc", "t0345246801") == "T-034.524.680-1"
    assert normalize("language", "SPA") == "spa"
    assert normalize("release_country", "es") == "ES"
    assert normalize("rg_track_gain", "-6.5") == "-6.50 dB"
    assert normalize("barcode", "8 435123 456786") == "8435123456786"
    assert validate_values({"track": "5", "track_total": "3"}) == {"track": "Greater than the total (3)."}


# --- revisión con BWF MetaEdit (2026-11-25) --------------------------------------------

def test_info_is_utf8_by_default_and_cp1252_optional(tmp_path):
    src = build_all(str(tmp_path))["01 - plain.wav"]
    meta = read_track(src)[0]
    meta.set("engineer", "Víctor Llinares")
    meta.set("album", "Canciones para un día de lluvia")
    assert writer.save_track(src, meta).ok
    items = dict(listinfo.parse(read_chunk_bytes(src, parse(src).info_lists()[0])))
    assert items[b"IENG"] == "Víctor Llinares".encode("utf-8") + b"\x00"
    assert items[b"IPRD"].rstrip(b"\x00").decode("utf-8") == "Canciones para un día de lluvia"
    assert writer.save_track(src, read_track(src)[0], info_encoding="cp1252").ok
    items = dict(listinfo.parse(read_chunk_bytes(src, parse(src).info_lists()[0])))
    assert items[b"IENG"] == "Víctor Llinares".encode("cp1252") + b"\x00"
    assert read_track(src)[0].get("engineer") == "Víctor Llinares"      # se lee igual en ambos


def test_info_isrc_with_code_follows_track_isrc(tmp_path):
    """REAPER guarda el ISRC en INFO/ISRC: si cambia el ISRC no puede quedar el viejo."""
    from make_test_wavs import chunk, fmt_chunk, info_payload, pcm, riff
    p = tmp_path / "reaper.wav"
    p.write_bytes(riff([fmt_chunk(), chunk(b"LIST", info_payload({b"ISRC": b"ES83F2519397"})),
                        chunk(b"data", pcm(4000, 3))]))
    meta = read_track(str(p))[0]
    assert meta.get("info_source") == "ES83F2519397"
    meta.set("isrc", "ESABC2600001")
    res = writer.save_track(str(p), meta)
    assert res.ok and any("INFO/ISRC" in w for w in res.warnings)
    assert read_track(str(p))[0].get("info_source") == "ESABC2600001"
    # un texto que no es un ISRC (p. ej. el nombre de un proveedor) no se toca
    meta = read_track(str(p))[0]
    meta.set("info_source", "Ejemplo")
    meta.set("isrc", "ESABC2600002")
    assert writer.save_track(str(p), meta).ok
    assert read_track(str(p))[0].get("info_source") == "Ejemplo"


def test_folder_art(tmp_path):
    from runout.core.model import Picture
    path = writer.write_folder_art(str(tmp_path), Picture(PNG, "image/png"))
    assert path and open(path, "rb").read()[:3] == b"\xff\xd8\xff"
    assert writer.write_folder_art(str(tmp_path), Picture(PNG, "image/png")) is None  # sin cambios


def test_folder_art_failure_leaves_no_temp_file(tmp_path, monkeypatch):
    def broken_replace(src, dst):
        raise OSError("disk full")
    monkeypatch.setattr(writer.os, "replace", broken_replace)
    with pytest.raises(OSError):
        writer.write_folder_art(str(tmp_path), Picture(PNG, "image/png"))
    assert os.listdir(tmp_path) == []
