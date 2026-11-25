"""Verificación estructural y por hash del archivo temporal."""
from __future__ import annotations

import hashlib
import os

from ..i18n import tr
from .riff import RiffError, iter_chunk_payload, parse


class IntegrityError(Exception):
    """La verificación falló: el original no se reemplaza."""


def verify_output(tmp_path: str, plan, original_data_hash: str, original_fmt_hash: str) -> None:
    """Relee el temporal como un archivo desconocido y lo compara con el plan.

    Comprueba: tamaño RIFF, offsets pares, recorrido hasta el final exacto,
    SHA-256 de data/fmt igual al original y SHA-256 de cada chunk igual al
    que se pretendía escribir (los copiados, igual al del original).
    """
    try:
        out = parse(tmp_path)
    except RiffError as exc:
        raise IntegrityError(tr("The resulting file is not a valid WAV: %s") % exc) from exc

    size = os.path.getsize(tmp_path)
    if out.warnings:
        raise IntegrityError(tr("The resulting file has structural warnings: ")
                             + "; ".join(out.warnings))
    if out.riff_size != size - 8:
        raise IntegrityError(tr("Wrong RIFF size (%d, expected %d).") % (out.riff_size, size - 8))
    if len(out.chunks) != len(plan):
        raise IntegrityError(tr("Unexpected number of chunks (%d, expected %d).")
                             % (len(out.chunks), len(plan)))
    if out.chunks and out.chunks[-1].end != size:
        raise IntegrityError(tr("The last chunk does not end at the end of the file."))

    with open(tmp_path, "rb") as f:
        for chunk, item in zip(out.chunks, plan):
            if chunk.offset % 2:
                raise IntegrityError(tr("Chunk %s starts at an odd offset.") % chunk.label)
            if chunk.cid != item.cid or chunk.size != item.size:
                raise IntegrityError(tr("Chunk %s does not match the plan.") % chunk.label)
            h = hashlib.sha256()
            for block in iter_chunk_payload(f, chunk):
                h.update(block)
            digest = h.hexdigest()
            if digest != item.expected_sha256:
                raise IntegrityError(tr("The hash of chunk %s does not match.") % chunk.label)
            if chunk.cid == b"data" and digest != original_data_hash:
                raise IntegrityError(tr("Audio (data) SHA-256 differs from the original. Aborted."))
            if chunk.cid == b"fmt " and digest != original_fmt_hash:
                raise IntegrityError(tr("fmt SHA-256 differs from the original. Aborted."))
