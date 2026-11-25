"""Preparación de la carátula para que la lean todos los reproductores.

Problemas típicos de las carátulas de imprenta que impiden verlas en VLC o
en los reproductores de Windows: más de 2 MB, color CMYK, JPEG progresivo o
tamaños enormes (p. ej. 6000x6000). Aquí se convierten a JPEG RGB baseline,
de 3000x3000 como máximo y 2 MB como máximo. La imagen solo se recomprime si
hace falta; el audio no tiene nada que ver con esto.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field

from PIL import Image, ImageOps

from ..i18n import tr


MAX_BYTES = 2 * 1024 * 1024
MAX_SIDE = 3000


@dataclass
class CoverResult:
    data: bytes
    mime: str
    width: int
    height: int
    changed: bool
    notes: list[str] = field(default_factory=list)


def _encode_jpeg(img: Image.Image, quality: int) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality, optimize=True, progressive=False, subsampling="4:2:0")
    return buf.getvalue()


def prepare_cover(data: bytes, max_bytes: int = MAX_BYTES, max_side: int = MAX_SIDE) -> CoverResult:
    """Devuelve la carátula lista para incrustar. Lanza ValueError si no es una imagen."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:  # Pillow lanza varios tipos
        raise ValueError(tr("Not a valid JPG/PNG image (%s).") % exc) from exc
    fmt = (img.format or "").upper()
    if fmt not in ("JPEG", "PNG"):
        raise ValueError(tr("The cover must be JPG or PNG (it is %s).") % (fmt or tr("unknown")))

    notes: list[str] = []
    progressive = bool(img.info.get("progressive") or img.info.get("progression"))
    needs = []
    if len(data) > max_bytes:
        needs.append(tr("it weighs %.1f MB") % (len(data) / 1e6))
    if img.mode not in ("RGB", "L") and not (fmt == "PNG" and img.mode in ("RGBA", "P", "LA")):
        needs.append(tr("it is in %s") % img.mode)
    if progressive:
        needs.append(tr("it is a progressive JPEG"))
    if max(img.size) > max_side:
        needs.append(tr("it measures %dx%d") % img.size)

    if not needs:
        mime = "image/jpeg" if fmt == "JPEG" else "image/png"
        return CoverResult(data, mime, img.width, img.height, False)

    notes.append(tr("Cover converted to RGB JPEG because %s.") % ", ".join(dict.fromkeys(needs)))
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[-1])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")   # CMYK, L, I;16... -> RGB
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.LANCZOS)

    out = b""
    for _ in range(8):
        for quality in (92, 88, 84, 80, 75, 70):
            out = _encode_jpeg(img, quality)
            if len(out) <= max_bytes:
                break
        if len(out) <= max_bytes:
            break
        w, h = img.size
        img = img.resize((max(1, int(w * 0.85)), max(1, int(h * 0.85))), Image.LANCZOS)
    if len(out) > max_bytes:
        raise ValueError(tr("Could not shrink the cover below %d MB.") % (max_bytes // 1024 // 1024))
    notes.append(tr("Result: %dx%d, %.2f MB.") % (img.width, img.height, len(out) / 1e6))
    return CoverResult(out, "image/jpeg", img.width, img.height, True, notes)


def image_size(data: bytes) -> tuple[int, int, int]:
    """Ancho, alto y bits por píxel de una imagen (0, 0, 0 si no se puede leer)."""
    try:
        img = Image.open(io.BytesIO(data))
        depth = {"1": 1, "L": 8, "P": 8, "RGB": 24, "RGBA": 32, "CMYK": 32}.get(img.mode, 24)
        return img.width, img.height, depth
    except Exception:
        return 0, 0, 0
