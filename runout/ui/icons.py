"""Iconos dibujados con QPainter: no dependen de archivos externos ni de QtSvg."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

ACCENT = QColor("#e0892f")
LABEL_RED = QColor("#c8412f")


def _canvas(size: int) -> tuple[QPixmap, QPainter]:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size / 24.0, size / 24.0)   # se dibuja en una rejilla de 24×24
    return pm, p


def _pen(color: QColor, width: float = 1.8) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def _icon(draw, color: QColor, sizes=(16, 20, 24, 32, 48)) -> QIcon:
    icon = QIcon()
    for s in sizes:
        pm, p = _canvas(s)
        p.setPen(_pen(color))
        p.setBrush(Qt.NoBrush)
        draw(p)
        p.end()
        icon.addPixmap(pm)
    return icon


# --- barra de herramientas -------------------------------------------------------
def _file_plus(p: QPainter):
    path = QPainterPath()
    path.moveTo(14, 3); path.lineTo(6, 3); path.lineTo(6, 21); path.lineTo(18, 21); path.lineTo(18, 7)
    path.lineTo(14, 3); path.lineTo(14, 7); path.lineTo(18, 7)
    p.drawPath(path)
    p.drawLine(QPointF(12, 11), QPointF(12, 17))
    p.drawLine(QPointF(9, 14), QPointF(15, 14))


def _folder(p: QPainter):
    path = QPainterPath()
    path.moveTo(3, 7); path.lineTo(3, 19); path.lineTo(21, 19); path.lineTo(21, 9); path.lineTo(11, 9)
    path.lineTo(9, 6); path.lineTo(4, 6); path.closeSubpath()
    p.drawPath(path)


def _table(p: QPainter):
    p.drawRoundedRect(QRectF(3, 5, 18, 14), 2, 2)
    p.drawLine(QPointF(3, 10), QPointF(21, 10))
    p.drawLine(QPointF(3, 14.5), QPointF(21, 14.5))
    p.drawLine(QPointF(9, 10), QPointF(9, 19))


def _remove(p: QPainter):
    p.drawLine(QPointF(4, 7), QPointF(20, 7))
    p.drawLine(QPointF(9, 7), QPointF(10, 4)); p.drawLine(QPointF(10, 4), QPointF(14, 4))
    p.drawLine(QPointF(14, 4), QPointF(15, 7))
    path = QPainterPath()
    path.moveTo(6, 7); path.lineTo(7, 20); path.lineTo(17, 20); path.lineTo(18, 7)
    p.drawPath(path)


def _reload(p: QPainter):
    p.drawArc(QRectF(4.5, 4.5, 15, 15), 60 * 16, 290 * 16)
    p.drawLine(QPointF(15.8, 5.2), QPointF(16.5, 9))
    p.drawLine(QPointF(15.8, 5.2), QPointF(19.5, 4.5))


def _log(p: QPainter):
    for y, x2 in ((6, 20), (10, 16), (14, 20), (18, 13)):
        p.drawLine(QPointF(4, y), QPointF(x2, y))


def _sliders(p: QPainter):
    for y, knob in ((6, 15), (12, 8), (18, 13)):
        p.drawLine(QPointF(4, y), QPointF(20, y))
        p.save()
        p.setBrush(p.pen().color())
        p.drawEllipse(QPointF(knob, y), 2, 2)
        p.restore()


TOOLBAR = {"add_files": _file_plus, "add_folder": _folder, "csv": _table, "remove": _remove,
           "reload": _reload, "log": _log, "prefs": _sliders}


def toolbar_icon(name: str, color: QColor) -> QIcon:
    return _icon(TOOLBAR[name], color)


def dot_icon(color: QColor | None, size: int = 10) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    if color is not None:
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawEllipse(QRectF(1, 1, size - 2, size - 2))
        p.end()
    return QIcon(pm)


def drop_pixmap(color: QColor, size: int = 96) -> QPixmap:
    pm, p = _canvas(size)
    p.setPen(_pen(color, 1.2))
    path = QPainterPath()
    path.moveTo(3, 14); path.lineTo(3, 20); path.lineTo(21, 20); path.lineTo(21, 14)
    p.drawPath(path)
    p.drawLine(QPointF(12, 3), QPointF(12, 15))
    p.drawLine(QPointF(7.5, 10.5), QPointF(12, 15))
    p.drawLine(QPointF(16.5, 10.5), QPointF(12, 15))
    p.end()
    return pm


# --- icono de la aplicación ------------------------------------------------------
def app_pixmap(size: int = 256) -> QPixmap:
    """Vinilo visto desde arriba: surcos, la espiral final (runout) y la galleta."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size / 100.0, size / 100.0)
    c = QPointF(50, 50)

    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#151517"))
    p.drawEllipse(c, 47, 47)

    groove = QPen(QColor(255, 255, 255, 28), 0.6)
    p.setBrush(Qt.NoBrush)
    p.setPen(groove)
    r = 44.0
    while r > 27:
        p.drawEllipse(c, r, r)
        r -= 2.2

    # espiral de salida, de la última pista a la galleta
    spiral = QPainterPath()
    turns, r0, r1 = 2.2, 26.0, 18.5
    steps = 160
    for i in range(steps + 1):
        t = i / steps
        a = -math.pi / 2 + t * turns * 2 * math.pi
        rr = r0 + (r1 - r0) * t
        pt = QPointF(50 + rr * math.cos(a), 50 + rr * math.sin(a))
        spiral.moveTo(pt) if i == 0 else spiral.lineTo(pt)
    p.setPen(QPen(ACCENT, 1.4, Qt.SolidLine, Qt.RoundCap))
    p.drawPath(spiral)

    # brillo
    shine = QPen(QColor(255, 255, 255, 60), 2.2, Qt.SolidLine, Qt.RoundCap)
    p.setPen(shine)
    p.drawArc(QRectF(12, 12, 76, 76), 110 * 16, 40 * 16)
    p.drawArc(QRectF(12, 12, 76, 76), 290 * 16, 40 * 16)

    p.setPen(Qt.NoPen)
    p.setBrush(LABEL_RED)
    p.drawEllipse(c, 15, 15)
    p.setBrush(QBrush(QColor("#151517")))
    p.drawEllipse(c, 2.2, 2.2)
    p.end()
    return pm


def app_icon() -> QIcon:
    icon = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(app_pixmap(s))
    return icon
