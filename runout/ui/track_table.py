"""Tabla de pistas: modelo editable + indicadores de estado."""
from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass, field

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QRect, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QStyledItemDelegate, QTableView

from ..core.fields import BY_KEY
from ..core.model import FileStatus, TrackMetadata
from ..core.formats import read_track
from ..core.validators import normalize, validate_values
from ..i18n import N_, tr
from . import theme
from .icons import drop_pixmap


def _color(name: str, alpha: int = 255) -> QColor:
    c = QColor(getattr(theme.current(), name))
    c.setAlpha(alpha)
    return c


# estado de cada fila: (símbolo, color)
STATE_OK, STATE_DIRTY, STATE_WARN, STATE_SAVED, STATE_ERROR = range(5)
STATE_GLYPH = {STATE_OK: ("✔", "muted"), STATE_DIRTY: ("●", "amber"), STATE_WARN: ("▲", "amber"),
               STATE_SAVED: ("✔", "green"), STATE_ERROR: ("✘", "red")}


@dataclass
class TrackEntry:
    path: str
    original: TrackMetadata
    pending: TrackMetadata
    status: FileStatus
    result: str = ""                     # último resultado de guardado
    result_ok: bool | None = None
    extra_warnings: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: str) -> "TrackEntry":
        meta, status = read_track(path)
        return cls(path=path, original=meta, pending=meta.copy(), status=status)

    def reload(self) -> None:
        meta, status = read_track(self.path)
        self.original, self.pending, self.status = meta, meta.copy(), status

    @property
    def dirty(self) -> bool:
        return self.pending.differs_from(self.original)

    @property
    def errors(self) -> dict[str, str]:
        return validate_values(self.pending.values)

    @property
    def isrc_error(self) -> str | None:
        return self.errors.get("isrc")

    def errors_text(self) -> str:
        return "\n".join("%s: %s" % (tr(BY_KEY[k].label), v) for k, v in self.errors.items())


class Col:
    TRACK, FILE, TITLE, ISRC, ID3, COVER, AXML, STATE = range(8)
    HEADERS = ["#", N_("File"), N_("Title"), "ISRC", N_("Tags"), N_("Cover"), "AXML", N_("Status")]
    HEADER_TIPS = {ID3: N_("Metadata tags in the file (ID3, Vorbis Comments or MP4)"), COVER: N_("Cover embedded in the file"),
                   AXML: N_("ISRC in the axml chunk (EBU Tech 3352, WAV only)"),
                   STATE: N_("Hover over each row to see the details")}
    EDITABLE = {TRACK, TITLE, ISRC}


class TrackTableModel(QAbstractTableModel):
    changed = Signal()
    edited = Signal()   # el usuario ha editado una celda (para refrescar el editor)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.entries: list[TrackEntry] = []

    # --- carga -----------------------------------------------------------
    def add_paths(self, paths: list[str]) -> list[str]:
        known = {os.path.normcase(os.path.abspath(e.path)) for e in self.entries}
        new = []
        for p in paths:
            key = os.path.normcase(os.path.abspath(p))
            if key not in known:
                known.add(key)
                new.append(TrackEntry.load(os.path.abspath(p)))
        if new:
            self.beginResetModel()
            self.entries.extend(new)
            self.entries.sort(key=lambda e: (e.pending.track is None, e.pending.track or 0,
                                             os.path.basename(e.path).lower()))
            self.endResetModel()
            self.changed.emit()
        return [e.path for e in new]

    def drop_duplicate_paths(self) -> None:
        """Tras exportar, una fila puede apuntar a una copia que ya estaba en la lista."""
        seen, keep = set(), []
        for e in self.entries:
            key = os.path.normcase(os.path.abspath(e.path))
            if key not in seen:
                seen.add(key)
                keep.append(e)
        if len(keep) != len(self.entries):
            self.beginResetModel()
            self.entries = keep
            self.endResetModel()

    def remove_rows(self, rows: list[int]) -> None:
        self.beginResetModel()
        for r in sorted(set(rows), reverse=True):
            del self.entries[r]
        self.endResetModel()
        self.changed.emit()

    def refresh_row(self, row: int) -> None:
        self.dataChanged.emit(self.index(row, 0), self.index(row, Col.STATE))
        self.changed.emit()

    def refresh_all(self) -> None:
        if self.entries:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.entries) - 1, Col.STATE))
        self.changed.emit()

    def duplicate_isrcs(self) -> set[str]:
        counts = Counter(e.pending.isrc for e in self.entries if e.pending.isrc)
        return {k for k, v in counts.items() if v > 1}

    # --- Qt --------------------------------------------------------------
    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.entries)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(Col.HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return tr(Col.HEADERS[section])
        if orientation == Qt.Horizontal and role == Qt.ToolTipRole:
            tip = Col.HEADER_TIPS.get(section)
            return tr(tip) if tip else None
        return None

    def flags(self, index):
        f = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        entry = self.entries[index.row()]
        if index.column() in Col.EDITABLE and not entry.status.error:
            f |= Qt.ItemIsEditable
        return f

    def _state_text(self, e: TrackEntry) -> str:
        if e.status.error:
            return tr("Not usable: ") + e.status.error
        errors = e.errors
        if errors:
            if list(errors) == ["isrc"]:
                return tr("Invalid ISRC")
            return tr("Invalid data (%d): %s") % (len(errors), ", ".join(tr(BY_KEY[k].label) for k in errors))
        if e.pending.isrc and e.pending.isrc in self.duplicate_isrcs():
            return tr("Duplicate ISRC")
        if e.result:
            return e.result
        if e.dirty:
            return tr("Unsaved changes")
        if e.status.warnings:
            return tr("Warning: ") + e.status.warnings[0]
        return tr("No changes")

    def _state_kind(self, e: TrackEntry) -> int:
        if e.status.error or e.errors or e.result_ok is False:
            return STATE_ERROR
        if e.pending.isrc and e.pending.isrc in self.duplicate_isrcs():
            return STATE_ERROR
        if e.result_ok:
            return STATE_SAVED
        if e.dirty:
            return STATE_DIRTY
        if e.status.warnings:
            return STATE_WARN
        return STATE_OK

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        e = self.entries[index.row()]
        col = index.column()
        m = e.pending

        if role in (Qt.DisplayRole, Qt.EditRole):
            if col == Col.TRACK:
                return m.track if m.track is not None else ""
            if col == Col.FILE:
                parent = os.path.basename(os.path.dirname(e.path))
                name = os.path.basename(e.path)
                return "tagged/" + name if parent.lower() == "tagged" else name
            if col == Col.TITLE:
                return m.title
            if col == Col.ISRC:
                return m.isrc
            if col == Col.STATE:
                return STATE_GLYPH[self._state_kind(e)][0] if role == Qt.DisplayRole \
                    else self._state_text(e)
            if role == Qt.DisplayRole and col == Col.AXML and e.status.format != "WAV":
                return "–"
            if role == Qt.DisplayRole and col in (Col.ID3, Col.COVER, Col.AXML):
                flag = {Col.ID3: e.status.has_tags, Col.COVER: e.status.has_cover,
                        Col.AXML: e.status.has_axml_isrc}[col]
                return "✔" if flag else "✘"
            return None

        if role == Qt.ForegroundRole:
            if col == Col.AXML and e.status.format != "WAV":
                return QBrush(_color("muted"))
            if col in (Col.ID3, Col.COVER, Col.AXML):
                flag = {Col.ID3: e.status.has_tags, Col.COVER: e.status.has_cover,
                        Col.AXML: e.status.has_axml_isrc}[col]
                return QBrush(_color("green" if flag else "red"))
            if col == Col.STATE:
                return QBrush(_color(STATE_GLYPH[self._state_kind(e)][1]))
            return None

        if role == Qt.BackgroundRole:
            if col == Col.ISRC and (e.isrc_error or (m.isrc and m.isrc in self.duplicate_isrcs())):
                return QBrush(_color("red", 55))
            if col in Col.EDITABLE and e.dirty and self._field_changed(e, col):
                return QBrush(_color("amber", 45))
            return None

        if role == Qt.FontRole and col in Col.EDITABLE and self._field_changed(e, col):
            f = QFont()
            f.setItalic(True)
            return f

        if role == Qt.TextAlignmentRole and col in (Col.TRACK, Col.ID3, Col.COVER, Col.AXML, Col.STATE):
            return Qt.AlignCenter

        if role == Qt.ToolTipRole:
            if col == Col.ISRC and e.isrc_error:
                return e.isrc_error
            if col == Col.FILE:
                tips = [e.path, tr("Format: %s") % e.status.format]
                if e.status.chunk_labels:
                    tips.append(tr("Structure: %s") % ", ".join(e.status.chunk_labels))
                tips += e.status.warnings + e.extra_warnings
                return "\n".join(tips)
            if col == Col.STATE:
                return "\n".join([self._state_text(e)] + ([e.errors_text()] if e.errors else [])
                                  + e.status.warnings + e.extra_warnings)
        return None

    def _field_changed(self, e: TrackEntry, col: int) -> bool:
        attr = {Col.TRACK: "track", Col.TITLE: "title", Col.ISRC: "isrc"}.get(col)
        return bool(attr) and getattr(e.pending, attr) != getattr(e.original, attr)

    def setData(self, index, value, role=Qt.EditRole):
        if role != Qt.EditRole or not index.isValid():
            return False
        e = self.entries[index.row()]
        col = index.column()
        text = str(value).strip() if value is not None else ""
        key = {Col.TRACK: "track", Col.TITLE: "title", Col.ISRC: "isrc"}.get(col)
        if key is None:
            return False
        e.pending.set(key, normalize(BY_KEY[key], text))
        e.result, e.result_ok = "", None
        # el ISRC afecta al estado de otras filas (duplicados)
        self.refresh_all() if col == Col.ISRC else self.refresh_row(index.row())
        self.edited.emit()
        return True


class KeepColorDelegate(QStyledItemDelegate):
    """Las filas seleccionadas mantienen el color de los indicadores (✔ verde, ✘ rojo)."""

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        brush = index.data(Qt.ForegroundRole)
        if brush is not None:
            option.palette.setBrush(QPalette.HighlightedText, brush)


class TrackTableView(QTableView):
    def __init__(self, model: TrackTableModel, parent=None):
        super().__init__(parent)
        self.setModel(model)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
                             | QAbstractItemView.AnyKeyPressed)
        self.setAlternatingRowColors(True)
        self.setItemDelegate(KeepColorDelegate(self))
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(30)
        h = self.horizontalHeader()
        h.setStretchLastSection(False)
        h.setHighlightSections(False)
        h.setMinimumSectionSize(36)
        for col, width in ((Col.TRACK, 44), (Col.ISRC, 124), (Col.ID3, 52), (Col.COVER, 64),
                           (Col.AXML, 56), (Col.STATE, 58)):
            h.setSectionResizeMode(col, QHeaderView.Fixed)
            self.setColumnWidth(col, width)
        h.setSectionResizeMode(Col.FILE, QHeaderView.Interactive)
        self.setColumnWidth(Col.FILE, 200)
        h.setSectionResizeMode(Col.TITLE, QHeaderView.Stretch)
        model.modelReset.connect(self.viewport().update)

    def selected_rows(self) -> list[int]:
        return sorted({i.row() for i in self.selectionModel().selectedRows()})

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.model().rowCount():
            return
        # lista vacía: invitación a soltar la carpeta del álbum
        p = QPainter(self.viewport())
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.viewport().rect()
        muted = _color("muted")
        icon = drop_pixmap(muted, 72)
        cy = rect.center().y() - 40
        p.drawPixmap(rect.center().x() - 36, cy - 50, icon)
        f = QFont(self.font())
        f.setPointSizeF(f.pointSizeF() * 1.35)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        p.setPen(QColor(theme.current().text))
        p.drawText(QRect(rect.left(), cy + 32, rect.width(), 30), Qt.AlignCenter,
                   tr("Drop the album folder here"))
        p.setFont(self.font())
        p.setPen(muted)
        p.drawText(QRect(rect.left(), cy + 64, rect.width(), 24), Qt.AlignCenter,
                   tr("or several audio files · WAV, AIFF, FLAC, MP3, M4A, Ogg and Opus"))
        p.end()
