"""AIFF, FLAC, MP3, M4A, Ogg Vorbis y Opus: ida y vuelta de etiquetas con el audio intacto.

Los archivos de tests/fixtures/ son medio segundo de un tono de 440 Hz generado con
ffmpeg (sin etiquetas), así que las pruebas no necesitan codificadores instalados.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sys

import mutagen
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_core import PNG  # noqa: E402
from runout.core import formats  # noqa: E402
from runout.core.formats.base import FormatError  # noqa: E402
from runout.core.model import Picture  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
SAMPLES = ["sample.aiff", "sample.flac", "sample.mp3", "sample.m4a", "sample.ogg", "sample.opus"]

COMMON = {
    "title": "Canción del Ñandú", "artist": "Artista", "album": "Álbum de prueba",
    "album_artist": "Artista", "label": "Discos Ejemplo", "date": "2026-11-25",
    "genre": "Flamenco", "isrc": "ESABC2600001", "track": "3", "track_total": "12",
    "disc": "1", "disc_total": "2", "composer": "Compositora", "copyright": "© 2026 Discos Ejemplo",
    "catalog": "DEJ-001", "barcode": "8435123456786", "language": "spa", "bpm": "120",
    "comment": "Sync: sync@sello.example", "lyrics": "Primera línea\nSegunda línea",
    "custom_txxx": "PROYECTO=Disco 2026",
}


def sha(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


@pytest.fixture(params=SAMPLES)
def sample(request, tmp_path):
    dst = tmp_path / request.param
    shutil.copy(os.path.join(FIXTURES, request.param), dst)
    return str(dst)


def _meta_with_common(path):
    meta, status = formats.read_track(path)
    assert not status.error, status.error
    for key, value in COMMON.items():
        meta.set(key, value)
    meta.pictures[3] = Picture(PNG, "image/png")
    return meta


def test_read_untagged(sample):
    meta, status = formats.read_track(sample)
    assert not status.error
    assert not status.has_cover
    assert meta.get("title") == ""


def test_round_trip_keeps_audio(sample):
    handler = formats.handler_for(sample)
    before = handler.fingerprint(sample)
    length = mutagen.File(sample).info.length

    res = formats.save_track(sample, _meta_with_common(sample))
    assert res.ok, res.message

    assert handler.fingerprint(sample) == before
    assert mutagen.File(sample).info.length == pytest.approx(length, abs=1e-6)
    meta, status = formats.read_track(sample)
    assert status.has_tags and status.has_cover
    for key, value in COMMON.items():
        assert meta.get(key) == value, (key, meta.get(key))
    assert meta.cover.data[:3] == b"\xff\xd8\xff" or meta.cover.data[:4] == b"\x89PNG"
    assert not [n for n in os.listdir(os.path.dirname(sample)) if n.endswith(".tmp")]


def test_second_save_is_stable(sample):
    assert formats.save_track(sample, _meta_with_common(sample)).ok
    first = sha(sample)
    meta, _ = formats.read_track(sample)
    assert formats.save_track(sample, meta).ok
    assert sha(sample) == first


def test_export_leaves_original_untouched(sample, tmp_path):
    original = sha(sample)
    dest = str(tmp_path / "tagged" / os.path.basename(sample))
    res = formats.save_track(sample, _meta_with_common(sample), dest)
    assert res.ok, res.message
    assert sha(sample) == original
    assert formats.read_track(dest)[0].get("isrc") == "ESABC2600001"


def test_corrupted_audio_is_detected(sample, monkeypatch):
    handler = formats.handler_for(sample)
    original = sha(sample)
    real_write = type(handler).write

    with open(sample, "rb") as fh:
        data = fh.read()
    window = data[len(data) // 2:len(data) // 2 + 16]     # en mitad del original: audio

    def write_and_corrupt(self, src, tmp, meta, options, warnings):
        real_write(self, src, tmp, meta, options, warnings)
        with open(tmp, "r+b") as fh:
            out = fh.read()
            pos = out.index(window)
            fh.seek(pos)
            fh.write(bytes([out[pos] ^ 0xFF]))

    monkeypatch.setattr(type(handler), "write", write_and_corrupt)
    res = formats.save_track(sample, _meta_with_common(sample))
    assert not res.ok
    assert sha(sample) == original
    assert not [n for n in os.listdir(os.path.dirname(sample)) if n.endswith(".tmp")]


def test_unknown_custom_tags_are_kept(sample):
    meta = _meta_with_common(sample)
    meta.set("custom_txxx", "PROYECTO=Disco 2026\nSYNC_CONTACT=sync@sello.example")
    assert formats.save_track(sample, meta).ok
    custom = formats.read_track(sample)[0].get("custom_txxx").splitlines()
    assert "PROYECTO=Disco 2026" in custom and "SYNC_CONTACT=sync@sello.example" in custom


def test_fields_that_do_not_apply_are_ignored(sample):
    meta = _meta_with_common(sample)
    meta.set("bext_description", "Solo WAV")
    meta.set("engineer", "Solo RIFF INFO")
    assert formats.save_track(sample, meta).ok
    reread = formats.read_track(sample)[0]
    assert reread.get("bext_description") == "" and reread.get("engineer") == ""
    assert "bext_description" not in formats.supported_fields(sample)


def test_flac_keeps_streaminfo_and_other_blocks(tmp_path):
    from runout.core.formats import flac
    path = str(tmp_path / "a.flac")
    shutil.copy(os.path.join(FIXTURES, "sample.flac"), path)
    blocks_before, _, _ = flac.parse(path)
    assert formats.save_track(path, _meta_with_common(path)).ok
    blocks_after, _, _ = flac.parse(path)
    assert blocks_after[0].data == blocks_before[0].data          # STREAMINFO (con el MD5)
    kinds = [b.type for b in blocks_before if b.type not in (flac.PADDING, flac.VORBIS_COMMENT)]
    assert all(k in [b.type for b in blocks_after] for k in kinds)


def test_flac_all_picture_types(tmp_path):
    path = str(tmp_path / "a.flac")
    shutil.copy(os.path.join(FIXTURES, "sample.flac"), path)
    meta = _meta_with_common(path)
    for ptype in (4, 8, 20):
        meta.pictures[ptype] = Picture(PNG, "image/png")
    assert formats.save_track(path, meta).ok
    assert sorted(formats.read_track(path)[0].pictures) == [3, 4, 8, 20]


def test_m4a_only_front_cover():
    assert formats.picture_types("x.m4a") == (3,)


def test_mp3_keeps_id3v1_tail(tmp_path):
    path = str(tmp_path / "a.mp3")
    with open(os.path.join(FIXTURES, "sample.mp3"), "rb") as fh:
        data = fh.read()
    tail = b"TAG" + b"Old title".ljust(30, b"\0") + bytes(95)
    with open(path, "wb") as fh:
        fh.write(data + tail)
    _, status = formats.read_track(path)
    assert any("ID3v1" in w for w in status.warnings)
    assert formats.save_track(path, _meta_with_common(path)).ok
    with open(path, "rb") as fh:
        assert fh.read().endswith(tail)


def test_wrong_content_is_not_usable(tmp_path):
    for name in ("fake.flac", "fake.mp3", "fake.m4a", "fake.ogg", "fake.aiff"):
        path = tmp_path / name
        path.write_bytes(b"not audio at all" * 10)
        assert formats.read_track(str(path))[1].error, name


def test_unsupported_extension(tmp_path):
    path = tmp_path / "a.wma"
    path.write_bytes(b"x")
    assert formats.read_track(str(path))[1].error
    assert not formats.save_track(str(path), formats.read_track(str(path))[0]).ok
    assert not formats.is_supported("a.wma") and formats.is_supported("A.FLAC")


def test_ogg_audio_hash_ignores_page_renumbering(tmp_path):
    from runout.core.formats.ogg import audio_hash
    path = str(tmp_path / "a.ogg")
    shutil.copy(os.path.join(FIXTURES, "sample.ogg"), path)
    before = audio_hash(path)
    meta = _meta_with_common(path)
    meta.set("lyrics", "x" * 70000)      # obliga a repartir los comentarios en más páginas
    assert formats.save_track(path, meta).ok
    assert audio_hash(path) == before


def test_flac_rejects_missing_streaminfo(tmp_path):
    from runout.core.formats import flac
    path = tmp_path / "bad.flac"
    path.write_bytes(b"fLaC" + bytes([0x81, 0, 0, 0]))
    with pytest.raises(FormatError):
        flac.parse(str(path))


def test_dates_with_time_from_other_tools_do_not_block_saving(tmp_path):
    """MP3 con TDRC '2024-01-01 10:00:00' e iTunes con ©day '2014-05-19T07:00:00Z':
    al leerlos, la fecha se queda en la forma que acepta el validador."""
    from mutagen.id3 import ID3, TDRC
    from mutagen.mp4 import MP4
    from runout.core.validators import validate_values

    mp3 = tmp_path / "a.mp3"
    shutil.copy(os.path.join(FIXTURES, "sample.mp3"), mp3)
    tag = ID3()
    tag.add(TDRC(encoding=3, text=["2024-01-01 10:00:00"]))
    tag.save(str(mp3))
    m4a = tmp_path / "b.m4a"
    shutil.copy(os.path.join(FIXTURES, "sample.m4a"), m4a)
    mp4 = MP4(str(m4a))
    mp4["\xa9day"] = ["2014-05-19T07:00:00Z"]
    mp4.save()

    for path, date in ((mp3, "2024-01-01"), (m4a, "2014-05-19")):
        meta, status = formats.read_track(str(path))
        assert not status.error
        assert meta.get("date") == date
        assert "date" not in validate_values(meta.values)
        res = formats.save_track(str(path), meta)
        assert res.ok, res.message


def _add_other_picture(path):
    """Imagen de tipo 0 («otra») escrita con mutagen, como hacen algunos programas."""
    import base64
    from mutagen.flac import FLAC, Picture as MPicture
    from mutagen.id3 import APIC, ID3
    pic = MPicture()
    pic.type, pic.mime, pic.desc, pic.data = 0, "image/png", "", PNG
    if path.endswith(".mp3"):
        tag = ID3()
        tag.add(APIC(encoding=3, mime="image/png", type=0, desc="", data=PNG))
        tag.save(path)
    elif path.endswith(".flac"):
        f = FLAC(path)
        f.add_picture(pic)
        f.save()
    else:
        f = mutagen.File(path)
        f["METADATA_BLOCK_PICTURE"] = [base64.b64encode(pic.write()).decode("ascii")]
        f.save()


def _pictures_in_file(path):
    f = mutagen.File(path)
    if path.endswith(".mp3"):
        return len(f.tags.getall("APIC")) if f.tags else 0
    if path.endswith(".flac"):
        return len(f.pictures)
    return len((f.tags or {}).get("METADATA_BLOCK_PICTURE", []))


@pytest.mark.parametrize("name", ["sample.mp3", "sample.flac", "sample.ogg", "sample.opus"])
def test_other_type_picture_shown_as_cover_is_not_duplicated(tmp_path, name):
    path = str(tmp_path / name)
    shutil.copy(os.path.join(FIXTURES, name), path)
    _add_other_picture(path)

    meta, _ = formats.read_track(path)
    assert meta.pictures[3].data == PNG
    assert formats.save_track(path, meta).ok
    assert _pictures_in_file(path) == 1          # la portada, sin copia de tipo 0

    meta, _ = formats.read_track(path)
    meta.pictures.clear()                        # el usuario quita la portada
    assert formats.save_track(path, meta).ok
    assert _pictures_in_file(path) == 0
    assert 3 not in formats.read_track(path)[0].pictures
