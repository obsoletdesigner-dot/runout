"""Chunk ``id3 ``: mutagen se usa SOLO en memoria.

mutagen nunca recibe la ruta del WAV. Aquí se convierten bytes <-> objeto ID3,
y el escritor RIFF propio se encarga de colocar esos bytes en el archivo.
"""
from __future__ import annotations

import io

from mutagen.id3 import (APIC, COMM, ID3, TLEN, TPOS, TRCK, TXXX, USLT, WXXX, Frames,
                         ID3NoHeaderError)
from mutagen.id3._util import error as ID3Error

from .fields import FIELDS, PICTURE_TYPES, managed_txxx, pictures_to_keep
from .model import Picture, TrackMetadata

PICTURE_DESC = {3: "Cover", 4: "Back cover", 8: "Artist", 20: "Label logo"}
# frames v2.4 que mutagen borra al pasar a v2.3 pero que todo el mundo lee igual (iTunes)
KEEP_IN_V23 = ("TSOA", "TSOP", "TSOT")


def load(raw: bytes | None) -> ID3 | None:
    if not raw:
        return None
    try:
        return ID3(io.BytesIO(raw))
    except (ID3NoHeaderError, ID3Error, ValueError, EOFError):
        return None


def has_cover(tag: ID3 | None) -> bool:
    return bool(tag and tag.getall("APIC"))


def _txxx(tag: ID3, name: str) -> TXXX | None:
    for fr in tag.getall("TXXX"):
        if fr.desc.upper() == name.upper():
            return fr
    return None


def _del_txxx(tag: ID3, name: str) -> None:
    for key in [k for k, fr in tag.items() if k.startswith("TXXX:") and fr.desc.upper() == name.upper()]:
        del tag[key]


def _frame_text(fr) -> str:
    if hasattr(fr, "people"):
        return "\n".join("%s: %s" % (r, n) for r, n in fr.people)
    if hasattr(fr, "url"):
        return fr.url
    # ID3TimeStamp: mutagen separa fecha y hora con espacio; se muestra en ISO con «T»
    return "; ".join(t.text.replace(" ", "T") if hasattr(t, "year") else str(t)
                     for t in fr.text) if fr.text else ""


def _read_spec(tag: ID3, spec: str) -> str:
    if spec.startswith("TXXX:"):
        fr = _txxx(tag, spec[5:])
        return _frame_text(fr) if fr else ""
    if spec in ("COMM", "USLT"):
        frames = tag.getall(spec)
        pref = [f for f in frames if f.desc == ""] or frames
        return str(pref[0].text if spec == "USLT" else "; ".join(pref[0].text)) if pref else ""
    if spec == "WXXX":
        frames = tag.getall("WXXX")
        pref = [f for f in frames if f.desc == ""] or frames
        return pref[0].url if pref else ""
    if spec.startswith("W"):
        frames = tag.getall(spec)
        return frames[0].url if frames else ""
    fr = tag.get(spec)
    return _frame_text(fr) if fr else ""


def to_metadata(tag: ID3, meta: TrackMetadata) -> None:
    for f in FIELDS:
        if not f.id3:
            continue
        value = _read_spec(tag, f.id3)
        if not value and f.id3_v23:
            value = _read_spec(tag, f.id3_v23)
        if value:
            meta.set(f.key, value.strip() if f.kind not in ("multiline",) else value)
    for fid, (num_key, total_key) in (("TRCK", ("track", "track_total")),
                                      ("TPOS", ("disc", "disc_total"))):
        fr = tag.get(fid)
        if fr and fr.text:
            num, _, total = str(fr.text[0]).partition("/")
            if num.strip().isdigit():
                meta.set(num_key, str(int(num)))
            if total.strip().isdigit():
                meta.set(total_key, str(int(total)))
    if meta.get("date"):
        meta.set("date", meta.get("date")[:19])
    managed = managed_txxx()
    custom = ["%s=%s" % (fr.desc, "; ".join(fr.text)) for fr in tag.getall("TXXX")
              if fr.desc.upper() not in managed]
    if custom:
        meta.set("custom_txxx", "\n".join(custom))
    pics = tag.getall("APIC")
    for ptype in PICTURE_TYPES:
        for p in pics:
            if p.type == ptype:
                meta.pictures[ptype] = Picture(bytes(p.data), p.mime or "image/jpeg", p.desc)
                break
    if 3 not in meta.pictures and pics and not any(p.type in PICTURE_TYPES for p in pics):
        # imagen sin tipo de portada (tipo 0 «otra»): se muestra como portada
        p = pics[0]
        meta.pictures[3] = Picture(bytes(p.data), p.mime or "image/jpeg", p.desc)


def _people(value: str) -> list[list[str]]:
    out = []
    for line in value.splitlines():
        if ":" in line:
            role, name = line.split(":", 1)
            out.append([role.strip(), name.strip()])
    return out


def build(existing_raw: bytes | None, meta: TrackMetadata, version: int = 3,
          length_ms: int | None = None) -> bytes:
    """Devuelve los bytes de la etiqueta ID3 (v2.3 o v2.4), sin relleno.

    Conserva los frames que la app no gestiona (PRIV, UFID, POPM, GEOB...).
    """
    if version not in (3, 4):
        raise ValueError("version must be 3 or 4")
    tag = load(existing_raw) or ID3()
    enc = 3 if version == 4 else 1   # UTF-8 en v2.4, UTF-16 en v2.3
    lang = meta.get("language") if len(meta.get("language")) == 3 else "XXX"

    for f in FIELDS:
        if not f.id3:
            continue
        value = meta.get(f.key)
        target = f.id3_v23 if (version == 3 and f.id3_v23) else f.id3
        # borrar cualquier versión previa (frame v2.4 y su alternativa TXXX)
        for spec in filter(None, (f.id3, f.id3_v23)):
            if spec.startswith("TXXX:"):
                _del_txxx(tag, spec[5:])
            elif spec in ("COMM", "USLT", "WXXX"):
                for k in [k for k, fr in tag.items() if k.startswith(spec) and fr.desc == ""]:
                    del tag[k]
            else:
                tag.delall(spec)
        if not value:
            continue
        if target.startswith("TXXX:"):
            tag.add(TXXX(encoding=enc, desc=target[5:], text=[value]))
        elif target == "COMM":
            tag.add(COMM(encoding=enc, lang=lang, desc="", text=[value]))
        elif target == "USLT":
            tag.add(USLT(encoding=enc, lang=lang, desc="", text=value))
        elif target == "WXXX":
            tag.add(WXXX(encoding=enc, desc="", url=value))
        elif target.startswith("W"):
            tag.add(Frames[target](url=value))
        elif target in ("TIPL", "TMCL"):
            tag.add(Frames[target](encoding=enc, people=_people(value)))
        else:
            tag.add(Frames[target](encoding=enc, text=[value]))

    for fid, cls, num_key, total_key in (("TRCK", TRCK, "track", "track_total"),
                                         ("TPOS", TPOS, "disc", "disc_total")):
        tag.delall(fid)
        num = meta.get(num_key)
        if num:
            total = meta.get(total_key)
            tag.add(cls(encoding=enc, text=[num + ("/" + total if total else "")]))

    tag.delall("TLEN")
    if length_ms:
        tag.add(TLEN(encoding=enc, text=[str(length_ms)]))

    managed = managed_txxx()
    for k in [k for k, fr in tag.items() if k.startswith("TXXX:") and fr.desc.upper() not in managed]:
        del tag[k]
    for line in meta.get("custom_txxx").splitlines():
        if "=" in line:
            desc, val = line.split("=", 1)
            if desc.strip() and desc.strip().upper() not in managed:
                tag.add(TXXX(encoding=enc, desc=desc.strip(), text=[val.strip()]))

    # imágenes: se sustituyen solo los tipos gestionados; las demás se conservan
    keep = pictures_to_keep(tag.getall("APIC"), lambda fr: fr.type)
    for key in [k for k, fr in tag.items() if k.startswith("APIC") and not any(fr is x for x in keep)]:
        del tag[key]
    for ptype, pic in meta.pictures.items():
        if pic and pic.data:
            tag.add(APIC(encoding=enc, mime=pic.mime or "image/jpeg", type=ptype,
                         desc=PICTURE_DESC.get(ptype, "Picture"), data=pic.data))

    # mutagen NO convierte los frames al guardar como v2.3; hay que hacerlo antes.
    if version == 3:
        keep = [fr for fid in KEEP_IN_V23 for fr in tag.getall(fid)]
        tag.update_to_v23()
        for fr in keep:
            tag.add(fr)
    else:
        tag.update_to_v24()

    buf = io.BytesIO()
    tag.save(buf, v2_version=version, v23_sep="/", padding=lambda info: 0)
    return buf.getvalue()
