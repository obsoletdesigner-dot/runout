"""Escritura segura: temporal -> verificación -> reemplazo atómico.

Reglas:
* ``fmt ``, ``data`` y cualquier chunk que la app no gestiona (``cue ``, ``LIST-adtl``, ``iXML``...) se copian byte a byte.
* ``axml`` va siempre justo antes de ``data``.
* ``LIST-INFO``, ``id3 `` y ``bext`` existentes se sustituyen en su sitio.
  ``LIST-INFO`` e ``id3 `` nuevos se añaden al final; un ``bext`` nuevo, al
  principio (convención BWF).
* Un ``bext`` cuyos campos no cambian se copia byte a byte.
* El original no se toca hasta que el temporal supera todas las comprobaciones.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import os
import shutil
import struct
import tempfile
from dataclasses import dataclass, field

from ..i18n import tr
from . import axml, bext, id3chunk, listinfo
from .cover import prepare_cover
from .isrc import clean_isrc, is_valid_isrc
from .integrity import IntegrityError, verify_output
from .fields import BY_KEY, PICTURE_TYPES
from .model import Picture, TrackMetadata
from .validators import validate_values
from .reader import read_track
from .riff import MAX_RIFF_SIZE, Chunk, RiffError, iter_chunk_payload, parse, read_chunk_bytes, sha256_chunk

LOG_NAME = "runout.log"


@dataclass
class PlanItem:
    cid: bytes
    source: Chunk | None = None     # copiar este chunk del original
    payload: bytes | None = None    # o escribir estos bytes
    expected_sha256: str = ""       # se rellena al escribir

    @property
    def size(self) -> int:
        return self.source.size if self.source is not None else len(self.payload or b"")


@dataclass
class SaveResult:
    ok: bool
    source: str
    dest: str = ""
    message: str = ""
    data_sha256: str = ""
    warnings: list[str] = field(default_factory=list)


def prepare_pictures(meta: TrackMetadata, warnings: list[str]) -> TrackMetadata:
    out = meta
    for ptype, pic in meta.pictures.items():
        if not pic or not pic.data:
            continue
        try:
            prepared = prepare_cover(pic.data)
        except ValueError as exc:
            warnings.append(tr("Could not check the %s image (%s); it is embedded as is.")
                            % (tr(PICTURE_TYPES.get(ptype, str(ptype))), exc))
            continue
        if prepared.changed:
            if out is meta:
                out = meta.copy()
            out.pictures[ptype] = Picture(prepared.data, prepared.mime, pic.desc)
            warnings.extend("%s: %s" % (tr(PICTURE_TYPES.get(ptype, "Image")), n) for n in prepared.notes)
    return out


def _length_ms(path: str, info) -> int | None:
    fmt = read_chunk_bytes(path, info.fmt)
    if len(fmt) < 12:
        return None
    byte_rate = struct.unpack_from("<I", fmt, 8)[0]
    return info.data.size * 1000 // byte_rate if byte_rate else None


def build_plan(path: str, meta: TrackMetadata, id3_version: int = 3,
               warnings: list[str] | None = None, info_encoding: str = "utf-8") -> list[PlanItem]:
    warnings = warnings if warnings is not None else []
    errors = validate_values(meta.values)
    if errors:
        raise ValueError(tr("Invalid data: ") + "; ".join(
            "%s: %s" % (tr(BY_KEY[k].label), v) for k, v in errors.items()))
    meta = prepare_pictures(meta, warnings)
    # INFO/ISRC: algunos programas (REAPER, Sound Forge) guardan ahí el código ISRC.
    # Si ya contiene un código ISRC, se mantiene igual que el ISRC de la pista para
    # que nunca queden dos códigos distintos en el mismo archivo.
    src_info = meta.get("info_source")
    if src_info and is_valid_isrc(clean_isrc(src_info)) and meta.isrc and clean_isrc(src_info) != meta.isrc:
        meta = meta.copy()
        meta.set("info_source", meta.isrc)
        warnings.append(tr("INFO/ISRC held a different ISRC code (%s); it has been updated to %s.")
                        % (src_info, meta.isrc))
    info = parse(path)
    warnings.extend(info.warnings)

    infos = info.info_lists()
    id3s = info.id3_chunks()
    axmls = info.find(b"axml")
    bexts = info.find(b"bext")

    new_info = listinfo.build(read_chunk_bytes(path, infos[0]) if infos else None, meta, info_encoding)

    old_id3 = read_chunk_bytes(path, id3s[0]) if id3s else None
    new_id3 = id3chunk.build(old_id3, meta, id3_version, _length_ms(path, info))
    if len(new_id3) <= 10 and not id3s:
        new_id3 = None  # etiqueta vacía: no se crea

    old_axml = read_chunk_bytes(path, axmls[0]) if axmls else None
    new_axml, drop_axml, note = axml.plan(old_axml, meta)
    if note:
        warnings.append(note)
    if len(axmls) > 1:
        warnings.append(tr("There are %d axml chunks; only the first one is managed.") % len(axmls))

    new_bext = bext.build(read_chunk_bytes(path, bexts[0]) if bexts else None, meta)

    plan: list[PlanItem] = []
    if new_bext is not None and not bexts:
        plan.append(PlanItem(b"bext", payload=new_bext))   # bext nuevo: al principio (BWF)
    info_done = id3_done = bext_done = False
    first_axml = axmls[0] if axmls else None
    for c in info.chunks:
        if c is first_axml and (new_axml is not None or drop_axml):
            continue  # se reubica antes de data (o se elimina si se ha vaciado)
        if c.cid == b"bext" and not bext_done:
            bext_done = True
            if new_bext is not None:
                plan.append(PlanItem(b"bext", payload=new_bext))
                continue
        if c.is_info_list():
            if not info_done and new_info is not None:
                plan.append(PlanItem(b"LIST", payload=new_info))
            info_done = True
            continue
        if c.is_id3():
            if not id3_done and new_id3 is not None:
                plan.append(PlanItem(b"id3 ", payload=new_id3))
            id3_done = True
            continue
        if c.cid == b"data" and new_axml is not None:
            plan.append(PlanItem(b"axml", payload=new_axml))
        plan.append(PlanItem(c.cid, source=c))

    if not info_done and new_info is not None:
        plan.append(PlanItem(b"LIST", payload=new_info))
    if not id3_done and new_id3 is not None:
        plan.append(PlanItem(b"id3 ", payload=new_id3))

    total = 4 + sum(8 + it.size + (it.size & 1) for it in plan)
    if total > MAX_RIFF_SIZE:
        raise RiffError(tr("The resulting file would exceed 4 GB; it cannot be saved as RIFF."))
    return plan


def write_plan(src: str, out, plan: list[PlanItem]) -> int:
    """Escribe el WAV completo en el objeto de archivo `out`. Devuelve el tamaño RIFF."""
    out.write(b"RIFF\x00\x00\x00\x00WAVE")
    with open(src, "rb") as f:
        for item in plan:
            h = hashlib.sha256()
            out.write(struct.pack("<4sI", item.cid, item.size))
            if item.source is not None:
                for block in iter_chunk_payload(f, item.source):
                    h.update(block)
                    out.write(block)
            else:
                h.update(item.payload)
                out.write(item.payload)
            if item.size & 1:
                out.write(b"\x00")
            item.expected_sha256 = h.hexdigest()
    end = out.tell()
    riff_size = end - 8
    out.seek(4)
    out.write(struct.pack("<I", riff_size))
    out.seek(end)
    return riff_size


def _log(dest_dir: str, line: str) -> None:
    try:
        with open(os.path.join(dest_dir, LOG_NAME), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def save_track(src: str, meta: TrackMetadata, dest: str | None = None,
               id3_version: int = 3, write_log: bool = True,
               info_encoding: str = "utf-8") -> SaveResult:
    """Guarda los metadatos de `src` en `dest` (por defecto, sobrescribe `src`)."""
    src = os.path.abspath(src)
    dest = os.path.abspath(dest or src)
    result = SaveResult(ok=False, source=src, dest=dest)
    dest_dir = os.path.dirname(dest)
    tmp_path = None
    try:
        os.makedirs(dest_dir, exist_ok=True)
        st_before = os.stat(src)
        info = parse(src)
        original_data_hash = sha256_chunk(src, info.data)
        original_fmt_hash = sha256_chunk(src, info.fmt)
        result.data_sha256 = original_data_hash

        plan = build_plan(src, meta, id3_version, result.warnings, info_encoding)

        fd, tmp_path = tempfile.mkstemp(prefix="." + os.path.basename(dest) + ".",
                                        suffix=".tmp", dir=dest_dir)
        with os.fdopen(fd, "w+b") as out:
            write_plan(src, out, plan)
            out.flush()
            os.fsync(out.fileno())

        verify_output(tmp_path, plan, original_data_hash, original_fmt_hash)

        # comprobación semántica: lo que se relee es lo que se quería escribir
        reread, status = read_track(tmp_path)
        if status.error:
            raise IntegrityError(tr("The resulting file cannot be read back: ") + status.error)
        for key in ("isrc", "title", "artist", "album", "label", "catalog", "barcode"):
            if meta.get(key) and reread.get(key) != meta.get(key):
                raise IntegrityError(tr("The %s field read back (%r) does not match what was written (%r).")
                                     % (tr(BY_KEY[key].label), reread.get(key), meta.get(key)))

        st_now = os.stat(src)
        if (st_now.st_size, st_now.st_mtime_ns) != (st_before.st_size, st_before.st_mtime_ns):
            raise IntegrityError(tr("The original changed while saving; cancelled."))

        try:
            shutil.copymode(src, tmp_path)
        except OSError:
            pass
        os.replace(tmp_path, dest)
        tmp_path = None
        result.ok = True
        result.message = tr("OK: data intact (SHA-256 %s…)") % original_data_hash[:16]
    except (RiffError, IntegrityError, OSError, ValueError) as exc:
        result.message = str(exc) or exc.__class__.__name__
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
    if write_log:
        stamp = _dt.datetime.now().isoformat(timespec="seconds")
        _log(dest_dir, "%s\t%s\t%s\t%s\tdata_sha256=%s\t%s" % (
            stamp, "OK" if result.ok else "ERROR", src, dest, result.data_sha256 or "-",
            result.message))
    return result


def export_path(src: str, subfolder: str = "tagged") -> str:
    """Destino en modo exportar. Si el archivo ya es una copia de /tagged, se
    actualiza esa misma copia (no se crea tagged/tagged/)."""
    src = os.path.abspath(src)
    folder = os.path.dirname(src)
    if os.path.basename(folder).lower() == subfolder.lower():
        return src
    return os.path.join(folder, subfolder, os.path.basename(src))


FOLDER_ART = "folder.jpg"


def write_folder_art(folder: str, picture) -> str | None:
    """Guarda la portada como folder.jpg en la carpeta (la usan el Explorador y los
    reproductores de Windows, que no leen la carátula incrustada en WAV).
    No toca ningún WAV. Devuelve la ruta escrita, o None si no hacía falta."""
    import io as _io

    from PIL import Image

    if not picture or not picture.data:
        return None
    prepared = prepare_cover(picture.data)      # RGB, sin progresivo, máx. 2 MB
    data = prepared.data
    if prepared.mime != "image/jpeg":
        img = Image.open(_io.BytesIO(data)).convert("RGB")
        buf = _io.BytesIO()
        img.save(buf, "JPEG", quality=92)
        data = buf.getvalue()
    path = os.path.join(folder, FOLDER_ART)
    try:
        with open(path, "rb") as fh:
            if fh.read() == data:
                return None
    except OSError:
        pass
    tmp = path + ".tmp"
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return path
