"""Genera assets/runout.png, .ico y .icns a partir del icono dibujado en runout/ui/icons.py.

Uso: python tools/make_icons.py
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image  # noqa: E402
from PySide6.QtCore import QBuffer, QIODevice  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from runout.ui.icons import app_pixmap  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "assets")


def render(size: int) -> Image.Image:
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    app_pixmap(size).save(buf, "PNG")
    return Image.open(io.BytesIO(bytes(buf.data()))).convert("RGBA")


def main() -> None:
    QGuiApplication([])
    os.makedirs(OUT, exist_ok=True)
    big = render(1024)
    big.save(os.path.join(OUT, "runout.png"))
    render(256).save(os.path.join(OUT, "runout.ico"),
                     sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    big.save(os.path.join(OUT, "runout.icns"))


if __name__ == "__main__":
    main()
