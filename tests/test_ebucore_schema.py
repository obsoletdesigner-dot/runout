"""Valida el axml contra el esquema oficial EBUCore 2012 (lxml).

Los esquemas no se incluyen en el repositorio: EBUCore se publica bajo CC BY-NC-SA 3.0,
que no es compatible con la GPL. Se descargan la primera vez de los repositorios de la
EBU, en commits fijos, se comprueba su SHA-256 y se guardan en tests/.schemas/.
Sin conexión, estas pruebas se saltan.
"""
from __future__ import annotations

import hashlib
import os
import sys
import urllib.request

import pytest

etree = pytest.importorskip("lxml.etree")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from make_test_wavs import build_all  # noqa: E402
from test_fields import ALL  # noqa: E402
from runout.core import axml, writer  # noqa: E402
from runout.core.model import TrackMetadata  # noqa: E402
from runout.core.reader import read_track  # noqa: E402
from runout.core.riff import parse, read_chunk_bytes  # noqa: E402

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".schemas")
MXF = "https://raw.githubusercontent.com/ebu/MXFTools/2607ef6499f25557d8e0f5cdedf5b4bfc9279a29/EBUCoreSchema/"
OSCIED = "https://raw.githubusercontent.com/ebu/OSCIED/7eebadfef2a47c55db0cdc1a2e4c653a613e27ec/tools/EBUCore/schemas/"
SCHEMAS = {
    "EBU_CORE_20130107.xsd": (MXF, "183c39b642d8a1beb7c9bbd32cda71642ec621b280e52174b07b5c56bde8a1e9"),
    "simpledc20021212.xsd": (OSCIED, "507ddd93428b4969061e946dc6e9a3e84a926c5363e8fda7b223ca8a3058aaa0"),
    "xml.xsd": (OSCIED, "c43df7d7e5983b9751a1503c8c263660ae941a4d15afb050ab0d77a267012770"),
}


def _fetch_schemas() -> str:
    os.makedirs(CACHE, exist_ok=True)
    for name, (base, digest) in SCHEMAS.items():
        path = os.path.join(CACHE, name)
        if os.path.exists(path):
            with open(path, "rb") as fh:
                if hashlib.sha256(fh.read()).hexdigest() == digest:
                    continue
        try:
            with urllib.request.urlopen(base + name, timeout=20) as resp:
                data = resp.read()
        except OSError as exc:
            pytest.skip("No se pudo descargar el esquema EBUCore (%s): %s" % (name, exc))
        if hashlib.sha256(data).hexdigest() != digest:
            pytest.fail("El esquema descargado %s no coincide con el SHA-256 esperado" % name)
        with open(path, "wb") as fh:
            fh.write(data)
    return os.path.join(CACHE, "EBU_CORE_20130107.xsd")


@pytest.fixture(scope="module")
def schema():
    return etree.XMLSchema(etree.parse(_fetch_schemas()))


def _check(schema, data: bytes):
    ok = schema.validate(etree.fromstring(data.rstrip(b"\x00")))
    assert ok, "\n".join(str(e) for e in schema.error_log)


def test_schema_is_strict(schema):
    bad = (b'<ebucore:ebuCoreMain xmlns:dc="http://purl.org/dc/elements/1.1/" '
           b'xmlns:ebucore="urn:ebu:metadata-schema:ebuCore_2012"><ebucore:coreMetadata>'
           b'<ebucore:rights><dc:rights>x</dc:rights></ebucore:rights>'
           b'<ebucore:title><dc:title>t</dc:title></ebucore:title>'
           b'</ebucore:coreMetadata></ebucore:ebuCoreMain>')
    assert not schema.validate(etree.fromstring(bad))   # orden incorrecto: debe fallar


@pytest.mark.parametrize("values", [
    {"isrc": "ESABC2600001"},
    {"title": "Solo título"},
    {"date": "2026", "isrc": "ESABC2600001"},
    {"barcode": "036000291452", "catalog": "DEJ-001"},
    {k: ALL[k] for k in ("title", "artist", "label", "date", "isrc", "iswc", "barcode",
                         "catalog", "language", "copyright")},
])
def test_new_axml_is_valid(schema, values):
    _check(schema, axml.build_full(TrackMetadata(dict(values))))


def test_isrc_only_template_and_surgical_insert_are_valid(schema):
    _check(schema, axml.build_new("ESABC2600001"))
    _check(schema, axml.update(b'<ns0:ebuCoreMain xmlns:ns0="urn:ebu:metadata-schema:ebuCore_2012">'
                               b'<ns0:coreMetadata/></ns0:ebuCoreMain>', "ESABC2600001"))


def test_axml_inside_saved_wav_is_valid(schema, tmp_path):
    src = build_all(str(tmp_path))["02 - odd_bwf.wav"]
    meta = read_track(src)[0]
    meta.values.update(ALL)
    assert writer.save_track(src, meta).ok
    _check(schema, read_chunk_bytes(src, parse(src).first(b"axml")))
