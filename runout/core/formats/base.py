"""Piezas comunes a todos los formatos: huella del audio y guardado verificado.

Cada formato define qué bytes son «el audio» (las tramas MP3, el SSND de AIFF, los
frames FLAC, los paquetes Ogg, el mdat de MP4) y cómo escribir sus etiquetas en un
archivo temporal. El guardado es siempre el mismo:

1. huella del audio del original (SHA-256 de esos bytes y de lo que los describe);
2. escritura en un temporal dentro de la carpeta de destino;
3. huella del temporal: tiene que ser idéntica, si no se aborta;
4. relectura de las etiquetas: lo releído tiene que ser lo escrito;
5. reemplazo atómico con os.replace.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass
from typing import BinaryIO, Callable

from ...i18n import tr
from ..fields import BY_KEY
from ..integrity import IntegrityError
from ..model import FileStatus, TrackMetadata
from ..writer import LOG_NAME, SaveResult, prepare_pictures

COPY_BLOCK = 1024 * 1024
# campos que se releen después de escribir para comprobar que están bien
CHECK_KEYS = ("isrc", "title", "artist", "album", "label", "catalog", "barcode")


class FormatError(Exception):
    """El archivo no tiene la estructura esperada para su formato."""


@dataclass
class SaveOptions:
    id3_version: int = 3
    info_encoding: str = "utf-8"


def hash_range(f: BinaryIO, start: int, end: int, h=None):
    """SHA-256 de los bytes [start, end) del archivo, en bloques."""
    h = h or hashlib.sha256()
    f.seek(start)
    remaining = end - start
    while remaining > 0:
        block = f.read(min(COPY_BLOCK, remaining))
        if not block:
            raise FormatError(tr("Unexpected end of file while reading %s.") % "audio")
        h.update(block)
        remaining -= len(block)
    return h


def copy_range(src: BinaryIO, out: BinaryIO, start: int, end: int | None = None) -> None:
    src.seek(start)
    remaining = None if end is None else end - start
    while remaining is None or remaining > 0:
        block = src.read(COPY_BLOCK if remaining is None else min(COPY_BLOCK, remaining))
        if not block:
            break
        out.write(block)
        if remaining is not None:
            remaining -= len(block)


class Handler:
    """Interfaz de un formato. Las subclases rellenan los métodos marcados."""
    name = ""
    fields: frozenset[str] = frozenset()       # claves de fields.py que admite
    picture_types: tuple[int, ...] = ()          # tipos de imagen que admite

    def read(self, path: str) -> tuple[TrackMetadata, FileStatus]:
        raise NotImplementedError

    def fingerprint(self, path: str) -> dict[str, str]:
        """Hashes de las partes que nunca pueden cambiar; la clave "audio" es obligatoria."""
        raise NotImplementedError

    def write(self, src: str, tmp: str, meta: TrackMetadata, options: SaveOptions,
              warnings: list[str]) -> None:
        """Escribe en `tmp` el archivo con las etiquetas nuevas. `src` nunca se modifica."""
        raise NotImplementedError

    # --- común ---------------------------------------------------------------------
    def save(self, src: str, meta: TrackMetadata, dest: str | None = None,
             options: SaveOptions | None = None, write_log: bool = True) -> SaveResult:
        options = options or SaveOptions()
        src = os.path.abspath(src)
        dest = os.path.abspath(dest or src)
        result = SaveResult(ok=False, source=src, dest=dest)
        dest_dir = os.path.dirname(dest)
        tmp_path = None
        try:
            os.makedirs(dest_dir, exist_ok=True)
            st_before = os.stat(src)
            before = self.fingerprint(src)
            result.data_sha256 = before["audio"]
            meta = prepare_pictures(self.restrict(meta), result.warnings)

            fd, tmp_path = tempfile.mkstemp(prefix="." + os.path.basename(dest) + ".",
                                            suffix=".tmp", dir=dest_dir)
            os.close(fd)
            self.write(src, tmp_path, meta, options, result.warnings)
            with open(tmp_path, "rb+") as fh:
                os.fsync(fh.fileno())

            after = self.fingerprint(tmp_path)
            for part, digest in before.items():
                if after.get(part) != digest:
                    raise IntegrityError(tr("SHA-256 of %s differs from the original. Aborted.") % part)
            self.check_reread(tmp_path, meta)

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
            result.message = tr("OK: audio intact (SHA-256 %s…)") % before["audio"][:16]
        except (FormatError, IntegrityError, OSError, ValueError) as exc:
            result.message = str(exc) or exc.__class__.__name__
        except Exception as exc:  # errores de mutagen u otros: el original no se toca
            result.message = "%s: %s" % (exc.__class__.__name__, exc)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
        if write_log:
            log(dest_dir, result)
        return result

    def restrict(self, meta: TrackMetadata) -> TrackMetadata:
        """Solo los campos e imágenes que este formato puede guardar."""
        out = TrackMetadata({k: v for k, v in meta.values.items() if k in self.fields},
                            {k: p for k, p in meta.pictures.items() if k in self.picture_types})
        return out

    def check_reread(self, path: str, meta: TrackMetadata) -> None:
        reread, status = self.read(path)
        if status.error:
            raise IntegrityError(tr("The resulting file cannot be read back: ") + status.error)
        for key in CHECK_KEYS:
            if key in self.fields and meta.get(key) and reread.get(key) != meta.get(key):
                raise IntegrityError(
                    tr("The %s field read back (%r) does not match what was written (%r).")
                    % (tr(BY_KEY[key].label), reread.get(key), meta.get(key)))


def log(dest_dir: str, result: SaveResult) -> None:
    stamp = _dt.datetime.now().isoformat(timespec="seconds")
    line = "%s\t%s\t%s\t%s\taudio_sha256=%s\t%s" % (
        stamp, "OK" if result.ok else "ERROR", result.source, result.dest,
        result.data_sha256 or "-", result.message)
    try:
        with open(os.path.join(dest_dir, LOG_NAME), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def read_safely(fn: Callable[[], tuple[TrackMetadata, FileStatus]]) -> tuple[TrackMetadata, FileStatus]:
    """Convierte cualquier fallo de lectura en un archivo «no apto» en lugar de una excepción."""
    try:
        return fn()
    except Exception as exc:
        status = FileStatus()
        status.error = str(exc) or exc.__class__.__name__
        return TrackMetadata(), status
