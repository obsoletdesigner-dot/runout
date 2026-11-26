"""Pruebas del núcleo con WAV sintéticos. Ejecutar: python -m pytest -q"""
from __future__ import annotations

import hashlib
import os
import struct
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from make_test_wavs import build_all  # noqa: E402
from runout.core import axml, id3chunk, listinfo  # noqa: E402
from runout.core.csv_import import parse_csv  # noqa: E402
from runout.core.isrc import clean_isrc, is_valid_isrc  # noqa: E402
from runout.core.model import Picture, TrackMetadata  # noqa: E402
from runout.core.reader import read_track  # noqa: E402
from runout.core.riff import RiffError, parse, read_chunk_bytes, sha256_chunk  # noqa: E402
from runout.core import writer  # noqa: E402

def _png() -> bytes:
    import io as _io
    from PIL import Image
    buf = _io.BytesIO()
    Image.new("RGB", (64, 64), (200, 30, 30)).save(buf, "PNG")
    return buf.getvalue()


PNG = _png()


@pytest.fixture()
def wavs(tmp_path):
    return build_all(str(tmp_path))


def full_meta(**kw) -> TrackMetadata:
    values = dict(title="Canción del Ñandú", artist="Artista", album_artist="Artista",
                  album="Álbum", track="2", track_total="12", date="2026", genre="Flamenco",
                  label="Discos Ejemplo", composer="Compositora",
                  copyright="© 2026 Discos Ejemplo", isrc="ESABC2600001")
    pictures = {3: Picture(PNG, "image/png")}
    for k, v in kw.items():
        if k == "cover":
            pictures[3] = Picture(v, "image/jpeg")
        else:
            values[k] = v
    return TrackMetadata(values, pictures)


def meta_for(src: str, **kw) -> TrackMetadata:
    """Como hace la app: parte de lo que ya tiene el archivo y aplica los cambios."""
    meta = read_track(src)[0]
    new = full_meta(**kw)
    meta.values.update(new.values)
    meta.pictures.update(new.pictures)
    return meta


def structural_check(path: str) -> None:
    """Comprobación independiente del parser de la app."""
    data = open(path, "rb").read()
    assert data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    assert struct.unpack("<I", data[4:8])[0] == len(data) - 8
    pos = 12
    while pos < len(data):
        assert pos % 2 == 0, "offset impar"
        cid, size = struct.unpack("<4sI", data[pos:pos + 8])
        pos += 8 + size + (size & 1)
    assert pos == len(data), "el recorrido no termina al final exacto"


def chunk_hashes(path: str) -> dict[str, str]:
    info = parse(path)
    return {c.label + "#%d" % i: sha256_chunk(path, c) for i, c in enumerate(info.chunks)}


@pytest.mark.parametrize("name", ["01 - plain.wav", "02 - odd_bwf.wav", "03 - existing_meta.wav",
                                  "04 - bad_riffsize.wav", "05 - missing_pad.wav",
                                  "06 - foreign_axml.wav"])
@pytest.mark.parametrize("version", [3, 4])
def test_roundtrip_keeps_audio(wavs, name, version):
    src = wavs[name]
    before = parse(src)
    data_hash = sha256_chunk(src, before.data)
    fmt_hash = sha256_chunk(src, before.fmt)
    preserved = {c.label: sha256_chunk(src, c) for c in before.chunks
                 if c.label in ("bext", "cue ", "iXML", "LIST-adtl", "JUNK")}

    res = writer.save_track(src, meta_for(src), id3_version=version)
    assert res.ok, res.message
    structural_check(src)

    after = parse(src)
    assert after.warnings == []
    assert sha256_chunk(src, after.data) == data_hash
    assert sha256_chunk(src, after.fmt) == fmt_hash
    for c in after.chunks:
        if c.label in preserved:
            assert sha256_chunk(src, c) == preserved[c.label], c.label

    labels = [c.label for c in after.chunks]
    assert labels.index("axml") == labels.index("data") - 1, labels   # axml justo antes de data
    assert labels.count("id3 ") == 1 and "ID3 " not in labels
    assert labels.count("LIST-INFO") == 1
    assert labels.count("axml") == (1 if name != "06 - foreign_axml.wav" else 1)

    meta, status = read_track(src)
    assert status.has_id3 and status.has_cover
    assert meta.title == "Canción del Ñandú"
    assert meta.isrc == "ESABC2600001"
    assert meta.get("label") == "Discos Ejemplo"
    assert meta.track == 2 and meta.get("track_total") == "12"
    assert meta.get("date") == "2026"
    assert meta.cover.data == PNG

    tag = id3chunk.load(read_chunk_bytes(src, after.id3_chunks()[0]))
    assert tag.version[1] == version
    if version == 3:
        assert "TYER" in read_chunk_bytes(src, after.id3_chunks()[0]).decode("latin-1")


def test_foreign_axml_untouched(wavs):
    src = wavs["06 - foreign_axml.wav"]
    old = read_chunk_bytes(src, parse(src).first(b"axml"))
    res = writer.save_track(src, meta_for(src))
    assert res.ok
    assert any("not EBUCore" in w for w in res.warnings)
    assert read_chunk_bytes(src, parse(src).first(b"axml")) == old


def test_managed_axml_is_regenerated(wavs):
    src = wavs["03 - existing_meta.wav"]
    assert writer.save_track(src, meta_for(src)).ok
    raw = read_chunk_bytes(src, parse(src).first(b"axml")).decode()
    assert "ISRC:ESABC2600001" in raw and "Canción del Ñandú" in raw and "Discos Ejemplo" in raw
    assert writer.save_track(src, meta_for(src, isrc="ESABC2600002")).ok
    raw = read_chunk_bytes(src, parse(src).first(b"axml")).decode()
    assert raw.count("ISRC:") == 1 and "ESABC2600002" in raw


FOREIGN_EBUCORE = (b'<?xml version="1.0" encoding="UTF-8"?>\r\n'
                   b'<ns0:ebuCoreMain xmlns:ns0="urn:ebu:metadata-schema:ebuCore_2012" '
                   b'xmlns:ns1="http://purl.org/dc/elements/1.1/"><ns0:coreMetadata>'
                   b'<ns0:description><ns1:description>Notas del estudio</ns1:description>'
                   b'</ns0:description><ns0:identifier formatLabel="ISRC">'
                   b'<ns1:identifier>ISRC:ESXXX2500001</ns1:identifier></ns0:identifier>'
                   b'<!-- comentario --></ns0:coreMetadata></ns0:ebuCoreMain>')


def test_foreign_ebucore_only_isrc_changes(tmp_path):
    from make_test_wavs import chunk, fmt_chunk, pcm, riff
    p = tmp_path / "foreign.wav"
    p.write_bytes(riff([fmt_chunk(), chunk(b"data", pcm(5000, 9)), chunk(b"axml", FOREIGN_EBUCORE)]))
    res = writer.save_track(str(p), meta_for(str(p)))
    assert res.ok, res.message
    raw = read_chunk_bytes(str(p), parse(str(p)).first(b"axml"))
    assert raw == FOREIGN_EBUCORE.replace(b"ESXXX2500001", b"ESABC2600001")  # resto byte a byte


def test_existing_frames_and_info_preserved(wavs):
    src = wavs["03 - existing_meta.wav"]
    assert writer.save_track(src, meta_for(src)).ok
    info = parse(src)
    tag = id3chunk.load(read_chunk_bytes(src, info.id3_chunks()[0]))
    assert tag.getall("COMM")[0].text[0] == "Comentario de otra herramienta"
    items = dict(listinfo.parse(read_chunk_bytes(src, info.info_lists()[0])))
    assert items[b"ISFT"] == b"Pro Tools\x00"
    assert items[b"INAM"].rstrip(b"\x00").decode("utf-8") == "Canción del Ñandú"
    assert b"ISRC" not in items  # INFO/ISRC = "Source", nunca el código


def test_export_leaves_original_identical(wavs):
    src = wavs["02 - odd_bwf.wav"]
    original = hashlib.sha256(open(src, "rb").read()).hexdigest()
    dest = writer.export_path(src)
    res = writer.save_track(src, meta_for(src), dest=dest)
    assert res.ok, res.message
    assert hashlib.sha256(open(src, "rb").read()).hexdigest() == original
    assert os.path.basename(os.path.dirname(dest)) == "tagged"
    structural_check(dest)
    assert sha256_chunk(dest, parse(dest).data) == sha256_chunk(src, parse(src).data)
    assert os.path.exists(os.path.join(os.path.dirname(dest), "runout.log"))


def test_idempotent_second_save(wavs):
    src = wavs["01 - plain.wav"]
    assert writer.save_track(src, meta_for(src)).ok
    first = open(src, "rb").read()
    assert writer.save_track(src, meta_for(src)).ok
    assert open(src, "rb").read() == first


def test_corruption_is_detected_and_original_kept(wavs, monkeypatch):
    src = wavs["02 - odd_bwf.wav"]
    original = open(src, "rb").read()
    real_write_plan = writer.write_plan

    def corrupting(src_path, out, plan):
        size = real_write_plan(src_path, out, plan)
        info_end = out.tell()
        data_item_offset = 12
        for it in plan:
            if it.cid == b"data":
                break
            data_item_offset += 8 + it.size + (it.size & 1)
        out.seek(data_item_offset + 8 + 100)
        b = out.read(1)
        out.seek(data_item_offset + 8 + 100)
        out.write(bytes([b[0] ^ 0xFF]))   # un bit del audio cambiado
        out.seek(info_end)
        return size

    monkeypatch.setattr(writer, "write_plan", corrupting)
    res = writer.save_track(src, meta_for(src))
    assert not res.ok
    assert "hash" in res.message.lower() or "sha-256" in res.message.lower()
    assert open(src, "rb").read() == original
    leftovers = [f for f in os.listdir(os.path.dirname(src)) if f.endswith(".tmp")]
    assert leftovers == []


def test_rejects_rf64_and_truncated(tmp_path):
    p = tmp_path / "rf64.wav"
    p.write_bytes(b"RF64\xff\xff\xff\xffWAVEds64" + b"\x00" * 40)
    with pytest.raises(RiffError):
        parse(str(p))
    q = tmp_path / "trunc.wav"
    q.write_bytes(b"RIFF\x00\x10\x00\x00WAVE" + b"fmt " + struct.pack("<I", 16) + b"\x00" * 16
                  + b"data" + struct.pack("<I", 100000) + b"\x00" * 10)
    with pytest.raises(RiffError):
        parse(str(q))
    res = writer.save_track(str(q), meta_for(str(q)))
    assert not res.ok


def test_isrc_cleaning():
    assert clean_isrc("ES-ABC-26-00001") == "ESABC2600001"
    assert clean_isrc(" es abc 26 00001 ") == "ESABC2600001"
    assert clean_isrc("ISRC: ES-ABC-26-00001") == "ESABC2600001"
    assert is_valid_isrc("ESABC2600001")
    assert not is_valid_isrc("ESABC260001")
    assert not is_valid_isrc("E1ABC2600001")
    assert not is_valid_isrc("ESABC26A0001")


def test_axml_new_is_valid_and_readable():
    raw = axml.build_new("ESABC2600001")
    assert axml.read_isrc(raw) == "ESABC2600001"
    assert axml.update(raw, "GBXYZ2600099").count(b"ISRC:") == 1



TWO_CREATORS = (b'<ebucore:ebuCoreMain xmlns:dc="http://purl.org/dc/elements/1.1/" '
                b'xmlns:ebucore="urn:ebu:metadata-schema:ebuCore_2012"><ebucore:coreMetadata>'
                b'<ebucore:creator><ebucore:contactDetails><ebucore:name>Composer Guy</ebucore:name>'
                b'</ebucore:contactDetails><ebucore:role typeLabel="Composer"/></ebucore:creator>'
                b'<ebucore:creator><ebucore:contactDetails><ebucore:name>The Band</ebucore:name>'
                b'</ebucore:contactDetails><ebucore:role typeLabel="Performer"/></ebucore:creator>'
                b'</ebucore:coreMetadata></ebucore:ebuCoreMain>')


def test_axml_from_another_tool_is_not_regenerated():
    """Varios creadores con roles: no es el axml de la app, así que no se regenera
    (se perdería el compositor) y el artista es el intérprete, no el primer nombre."""
    assert not axml.is_managed(TWO_CREATORS)
    assert axml.read_fields(TWO_CREATORS)["artist"] == "The Band"
    new, remove, warning = axml.plan(TWO_CREATORS, {"artist": "The Band", "isrc": "ESABC2600001"})
    assert not remove and warning
    assert b"Composer Guy" in new and axml.read_isrc(new) == "ESABC2600001"


def test_axml_own_output_is_managed():
    meta = {"title": "Uno & dos", "artist": "Artista", "label": "Sello", "date": "2026-11-25",
            "isrc": "ESABC2600001", "iswc": "T-123.456.789-0", "barcode": "8435123456786",
            "catalog": "DEJ-001", "language": "spa", "copyright": "© 2026"}
    assert axml.is_managed(axml.build_full(meta))
    assert axml.is_managed(axml.build_new("ESABC2600001"))
    assert axml.read_fields(axml.build_full(meta)) == meta
    # con un comentario o un atributo de otro programa deja de ser propio
    assert not axml.is_managed(axml.build_full(meta).replace(b"</ebucore:coreMetadata>",
                                                             b"<!-- x --></ebucore:coreMetadata>"))
    assert not axml.is_managed(axml.build_full(meta).replace(b"<ebucore:title>",
                                                             b'<ebucore:title typeLabel="main">'))


def test_csv(tmp_path):
    p = tmp_path / "a.csv"
    p.write_bytes("﻿Pista;Título;ISRC\n1;Uno;ES-ABC-26-00001\n2;Dos ñ;ESABC2600002\n\n"
                  .encode("utf-8"))
    rows, warns = parse_csv(str(p))
    assert warns == []
    assert [(r.pista, r.titulo, r.isrc) for r in rows] == [
        (1, "Uno", "ESABC2600001"), (2, "Dos ñ", "ESABC2600002")]
    q = tmp_path / "b.csv"
    q.write_bytes("pista,titulo,isrc\n3,Canción,ESABC2600003\n".encode("cp1252"))
    rows, _ = parse_csv(str(q))
    assert rows[0].titulo == "Canción"



def test_csv_with_infinite_track_number(tmp_path):
    p = tmp_path / "inf.csv"
    p.write_text("pista;titulo;isrc\ninf;Uno;ESABC2600001\n1e400;Dos;ESABC2600002\n"
                 "3;Tres;ESABC2600003\n", encoding="utf-8")
    rows, warns = parse_csv(str(p))
    assert [r.pista for r in rows] == [3]
    assert len(warns) == 2


# --- regresiones de las pruebas en Windows (2026-11-25) ------------------------

NS0_AXML = (b'<?xml version="1.0" encoding="UTF-8"?>\r\n'
            b'<ns0:ebuCoreMain xmlns:ns0="urn:ebu:metadata-schema:ebuCore_2012" '
            b'xmlns:ns1="http://purl.org/dc/elements/1.1/"><ns0:coreMetadata>'
            b'<ns0:identifier formatLabel="ISRC"><ns1:identifier>ISRC:ESXXX2500001</ns1:identifier>'
            b'</ns0:identifier><!-- comentario --></ns0:coreMetadata></ns0:ebuCoreMain>')


def test_axml_with_ns0_prefixes(tmp_path):
    """'Prefix format reserved for internal use': axml con prefijos ns0/ns1."""
    from make_test_wavs import chunk, fmt_chunk, pcm, riff
    p = tmp_path / "ns0.wav"
    p.write_bytes(riff([fmt_chunk(), chunk(b"data", pcm(5000, 9)), chunk(b"axml", NS0_AXML)]))
    res = writer.save_track(str(p), meta_for(str(p)))
    assert res.ok, res.message
    raw = read_chunk_bytes(str(p), parse(str(p)).first(b"axml"))
    assert axml.read_isrc(raw) == "ESABC2600001"
    # edición quirúrgica con prefijos ns0 (axml de terceros sin ISRC)
    no_isrc = (b'<ns0:ebuCoreMain xmlns:ns0="urn:ebu:metadata-schema:ebuCore_2012">'
               b'<ns0:coreMetadata><ns0:description/></ns0:coreMetadata></ns0:ebuCoreMain>')
    out = axml.update(no_isrc, "ESABC2600001")
    assert axml.read_isrc(out) == "ESABC2600001" and b"<ns0:identifier" in out


def _jpeg(size, mode="RGB", progressive=False, noise=True):
    import io as _io
    import random as _r
    from PIL import Image
    img = Image.new(mode, size)
    if noise:
        rnd = _r.Random(1)
        img.putdata([tuple(rnd.randrange(256) for _ in mode) for _ in range(size[0] * size[1])])
    buf = _io.BytesIO()
    img.save(buf, "JPEG", quality=98, progressive=progressive)
    return buf.getvalue()


def test_cover_is_normalized(wavs):
    from PIL import Image
    import io as _io
    from runout.core.cover import MAX_BYTES, prepare_cover
    big = _jpeg((1600, 1600), mode="CMYK", progressive=True)
    assert len(big) > MAX_BYTES
    res = prepare_cover(big)
    assert res.changed and len(res.data) <= MAX_BYTES and res.mime == "image/jpeg"
    img = Image.open(_io.BytesIO(res.data))
    assert img.mode == "RGB" and not img.info.get("progressive")
    small = _jpeg((300, 300), noise=False)
    assert prepare_cover(small).changed is False      # si ya está bien, no se toca
    # al guardar, una carátula grande se reduce antes de incrustarla
    src = wavs["01 - plain.wav"]
    r = writer.save_track(src, meta_for(src, cover=big))
    assert r.ok and any("Cover converted" in w for w in r.warnings)
    meta, _ = read_track(src)
    assert len(meta.cover.data) <= MAX_BYTES


def test_export_from_tagged_copy_updates_same_copy(wavs):
    src = wavs["01 - plain.wav"]
    dest = writer.export_path(src)
    assert writer.save_track(src, meta_for(src), dest=dest).ok
    assert writer.export_path(dest) == dest          # no tagged/tagged/
    assert writer.save_track(dest, meta_for(dest, title="Otro"), dest=writer.export_path(dest)).ok
    assert read_track(dest)[0].title == "Otro"


def test_no_id3_chunk_with_only_the_length(tmp_path):
    """Un WAV sin datos para ID3 no gana un chunk id3 que solo lleva TLEN."""
    from make_test_wavs import chunk, fmt_chunk, pcm, riff
    p = tmp_path / "plain.wav"
    p.write_bytes(riff([fmt_chunk(), chunk(b"data", pcm(5000, 9))]))
    meta, _ = read_track(str(p))
    meta.set("bext_description", "Solo bext")
    res = writer.save_track(str(p), meta)
    assert res.ok, res.message
    info = parse(str(p))
    assert not info.id3_chunks()
    assert info.first(b"bext") is not None
    assert not read_track(str(p))[1].has_id3
