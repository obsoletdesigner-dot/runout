"""Editor de metadatos por secciones, para una o varias pistas a la vez.

Cada cambio se aplica al momento a las pistas seleccionadas (no hay botón
«Aplicar»). Con varias pistas seleccionadas, los campos con valores distintos
muestran «(varios valores)» y solo cambian si escribes en ellos.
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFormLayout, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
                               QStackedWidget, QVBoxLayout, QWidget)

from ..core import formats
from ..core.cover import prepare_cover
from ..core.fields import BY_KEY, FIELDS, PICTURE_TYPES, TABS, Field, fields_in_tab
from ..core.model import Picture
from ..core.validators import country_name, language_name, normalize, problem, script_name
from ..i18n import N_, tr
from . import theme
from .icons import dot_icon

MIXED = N_("(multiple values)")
# campos que no tiene sentido poner igual en varias pistas a la vez
PER_TRACK = {"track", "title", "isrc", "subtitle", "lyrics", "mb_track_id", "rg_track_gain",
             "rg_track_peak", "iswc", "title_sort", "bext_description", "bext_originator_ref",
             "bext_loudness", "bext_lra", "bext_true_peak", "bext_max_momentary",
             "bext_max_short_term", "bext_coding_history"}
MULTILINE = {"multiline", "people", "keyvalue", "ascii_multiline"}
THUMB = 64


def err_style() -> str:
    c = QColor(theme.current().red)
    return "border: 1px solid %s; background: rgba(%d,%d,%d,0.10);" % (c.name(), c.red(), c.green(), c.blue())


class FieldWidget(QWidget):
    """Un campo: control de edición + línea de ayuda/error."""
    edited = Signal(str, str)   # clave, valor normalizado

    def __init__(self, f: Field, parent=None):
        super().__init__(parent)
        self.f = f
        self.loading = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        if f.kind in MULTILINE:
            self.edit = QPlainTextEdit()
            self.edit.setTabChangesFocus(True)
            self.edit.setFixedHeight(110 if f.key in ("lyrics", "custom_txxx") else 70)
            self.edit.textChanged.connect(self._changed)
        elif f.choices:
            self.edit = QComboBox()
            self.edit.setEditable(f.kind == "media")
            for value, label in f.choices:
                self.edit.addItem(tr(label), value)
            self.edit.currentIndexChanged.connect(self._changed)
            if f.kind == "media":
                self.edit.lineEdit().textEdited.connect(self._changed)
        else:
            self.edit = QLineEdit()
            self.edit.setClearButtonEnabled(not f.readonly)
            self.edit.textEdited.connect(self._changed)
            self.edit.editingFinished.connect(self._finish)
            self.edit.setReadOnly(f.readonly)
            if f.help:
                self.edit.setPlaceholderText(tr(f.help))
        if f.help:
            self.edit.setToolTip(tr(f.help))
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setVisible(False)
        lay.addWidget(self.edit)
        lay.addWidget(self.note)

    # --- lectura/escritura del control ---------------------------------------
    def raw_text(self) -> str:
        if isinstance(self.edit, QPlainTextEdit):
            return self.edit.toPlainText()
        if isinstance(self.edit, QComboBox):
            if self.f.kind == "media":
                text = self.edit.currentText().strip()
                idx = self.edit.findText(text)
                return self.edit.itemData(idx) if idx >= 0 else text.split(" ")[0]
            return self.edit.currentData() or ""
        return self.edit.text()

    def set_value(self, value: str | None, mixed: bool = False, enabled: bool = True) -> None:
        self.loading = True
        try:
            if isinstance(self.edit, QPlainTextEdit):
                self.edit.setPlainText(value or "")
                self.edit.setPlaceholderText(tr(MIXED) if mixed else tr(self.f.help))
            elif isinstance(self.edit, QComboBox):
                idx = self.edit.findData(value or "")
                if idx < 0 and value:
                    self.edit.addItem(value, value)
                    idx = self.edit.count() - 1
                self.edit.setCurrentIndex(max(idx, 0) if not mixed else 0)
            else:
                self.edit.setText(value or "")
                self.edit.setPlaceholderText(tr(MIXED) if mixed else tr(self.f.help))
            self.setEnabled(enabled)
            self._show_state(value or "")
        finally:
            self.loading = False

    # --- validación ----------------------------------------------------------
    def _show_state(self, value: str) -> None:
        msg = problem(self.f, value) if value else None
        info = ""
        if not msg and value:
            if self.f.kind == "language":
                info = language_name(value) or ""
            elif self.f.kind == "country":
                info = country_name(value) or ""
            elif self.f.kind == "script":
                info = script_name(value) or ""
        if msg:
            self.note.setText("✘ " + msg)
            self.note.setStyleSheet("color: %s;" % theme.current().red)
            self.edit.setStyleSheet(err_style())
        elif info:
            self.note.setText("✔ " + info)
            self.note.setStyleSheet("color: %s;" % theme.current().green)
            self.edit.setStyleSheet("")
        else:
            self.note.setText("")
            self.edit.setStyleSheet("")
        self.note.setVisible(bool(msg or info))

    def _changed(self, *args) -> None:
        if self.loading:
            return
        value = normalize(self.f, self.raw_text())
        self._show_state(value)
        self.edited.emit(self.f.key, value)

    def _finish(self) -> None:
        """Al salir del campo se muestra el valor ya normalizado (ISRC sin guiones...)."""
        if self.loading or not isinstance(self.edit, QLineEdit):
            return
        value = normalize(self.f, self.edit.text())
        if value != self.edit.text() and self.edit.text():
            self.loading = True
            self.edit.setText(value)
            self.loading = False


class PictureSlot(QWidget):
    changed = Signal(int, object)   # tipo, Picture | None

    def __init__(self, ptype: int, label: str, parent=None):
        super().__init__(parent)
        self.ptype = ptype
        self.setAcceptDrops(True)
        lay = QVBoxLayout(self)
        title = QLabel("<b>%s</b>" % tr(label))
        self.view = QLabel()
        self.view.setAlignment(Qt.AlignCenter)
        self.view.setFixedSize(150, 150)
        muted = theme.current().muted
        self.view.setStyleSheet("QLabel { border: 2px dashed %s; border-radius: 6px; color: %s; }"
                                % (muted, muted))
        self.view.mousePressEvent = lambda e: self.choose()
        clear = QPushButton(tr("Remove"))
        clear.clicked.connect(lambda: self._emit(None))
        lay.addWidget(title)
        lay.addWidget(self.view)
        lay.addWidget(clear)
        self.show_picture(None)

    def show_picture(self, pic: Picture | None, mixed: bool = False) -> None:
        if mixed:
            self.view.setPixmap(QPixmap())
            self.view.setText(tr(MIXED))
            return
        if not pic:
            self.view.setPixmap(QPixmap())
            self.view.setText(tr("Drop or click\n(JPG/PNG)"))
            self.view.setToolTip("")
            return
        pm = QPixmap()
        pm.loadFromData(pic.data)
        if pm.isNull():
            self.view.setText(tr("Image"))
        else:
            self.view.setPixmap(pm.scaled(140, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.view.setToolTip("%dx%d · %s · %d KB" % (pm.width(), pm.height(), pic.mime,
                                                       len(pic.data) // 1024))

    def choose(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Choose image"), "",
                                              tr("Images (*.jpg *.jpeg *.png)"))
        if path:
            self.load_file(path)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self.load_file(url.toLocalFile())
                break

    def load_file(self, path: str) -> None:
        try:
            with open(path, "rb") as fh:
                data = fh.read()
            res = prepare_cover(data)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Imagen", str(exc))
            return
        if res.changed:
            QMessageBox.information(self, "Imagen", "\n".join(res.notes)
                                    + tr("\n\nThis way VLC, iTunes/Music and the Windows players can read it."))
        self._emit(Picture(res.data, res.mime, os.path.basename(path)))

    def _emit(self, pic):
        self.show_picture(pic)
        self.changed.emit(self.ptype, pic)


class EditorPanel(QFrame):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("editor")
        self.entries: list = []
        self.widgets: dict[str, FieldWidget] = {}
        self.slots: dict[int, PictureSlot] = {}
        self.forms: dict[str, QFormLayout] = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # --- cabecera: miniatura de la portada + pista ----------------------
        head = QFrame()
        head.setObjectName("editorHeader")
        hl = QHBoxLayout(head)
        hl.setContentsMargins(12, 10, 12, 10)
        hl.setSpacing(12)
        self.thumb = QLabel()
        self.thumb.setObjectName("thumb")
        self.thumb.setFixedSize(THUMB, THUMB)
        self.thumb.setAlignment(Qt.AlignCenter)
        hl.addWidget(self.thumb)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        self.header = QLabel()
        self.header.setObjectName("trackTitle")
        self.subheader = QLabel()
        self.subheader.setObjectName("muted")
        self.subheader.setWordWrap(True)
        self.fileline = QLabel()
        self.fileline.setObjectName("muted")
        texts.addStretch(1)
        texts.addWidget(self.header)
        texts.addWidget(self.subheader)
        texts.addWidget(self.fileline)
        texts.addStretch(1)
        hl.addLayout(texts, 1)
        lay.addWidget(head)

        # --- secciones + contenido -------------------------------------------
        self.body = QWidget()
        body = QHBoxLayout(self.body)
        body.setContentsMargins(6, 8, 0, 0)
        body.setSpacing(0)
        self.sections = QListWidget()
        self.sections.setObjectName("sections")
        self.sections.setFixedWidth(150)
        self.sections.setFocusPolicy(Qt.NoFocus)
        self.stack = QStackedWidget()
        body.addWidget(self.sections)
        body.addWidget(self.stack, 1)
        lay.addWidget(self.body, 1)
        self.empty = QLabel(tr("The tracks you select in the list are edited here."))
        self.empty.setObjectName("muted")
        self.empty.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.empty, 1)

        for tab in TABS:
            inner = QWidget()
            title = QLabel(tr(tab))
            title.setObjectName("sectionTitle")
            if tab == "Images":
                grid = QGridLayout(inner)
                grid.addWidget(title, 0, 0, 1, 2)
                for i, (ptype, label) in enumerate(PICTURE_TYPES.items()):
                    slot = PictureSlot(ptype, label)
                    slot.changed.connect(self._picture_changed)
                    self.slots[ptype] = slot
                    grid.addWidget(slot, 1 + i // 2, i % 2)
                grid.setRowStretch(3, 1)
                grid.setColumnStretch(2, 1)
            else:
                form = QFormLayout(inner)
                form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
                form.setRowWrapPolicy(QFormLayout.WrapLongRows)
                form.setVerticalSpacing(8)
                form.addRow(title)
                for f in fields_in_tab(tab):
                    w = FieldWidget(f)
                    w.edited.connect(self._field_edited)
                    self.widgets[f.key] = w
                    self.forms[f.key] = form
                    form.addRow(tr(f.label), w)
            inner.layout().setContentsMargins(14, 0, 14, 12)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setWidget(inner)
            self.stack.addWidget(scroll)
            QListWidgetItem(dot_icon(None), tr(tab), self.sections)
        self.sections.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.sections.setCurrentRow(0)
        self.set_entries([])

    def show_section(self, index: int) -> None:
        self.sections.setCurrentRow(index)

    # --- carga -----------------------------------------------------------------
    def set_entries(self, entries: list) -> None:
        self.entries = [e for e in entries if not e.status.error]
        self.body.setVisible(bool(self.entries))
        self.empty.setVisible(not self.entries)
        self.refresh()

    def _update_header(self) -> None:
        n = len(self.entries)
        if n == 0:
            self.header.setText(tr("No track selected"))
            self.subheader.setText(tr("Select one or more tracks to edit them (Ctrl+A = all)."))
            self.fileline.setText("")
        elif n == 1:
            e = self.entries[0]
            m = e.pending
            self.header.setText(m.title or os.path.splitext(os.path.basename(e.path))[0])
            parts = [m.get("artist") or m.get("album_artist"), m.get("album")]
            num = (tr("Track %d") % m.track) if m.track is not None else ""
            self.subheader.setText(" · ".join(x for x in [num] + parts if x))
            self.fileline.setText("%s · %s" % (os.path.basename(e.path), e.status.format))
        else:
            self.header.setText(tr("%d tracks selected") % n)
            self.subheader.setText(tr("Changes apply to all of them. Per-track fields "
                                      "are locked."))
            albums = {e.pending.get("album") for e in self.entries} - {None, ""}
            self.fileline.setText(albums.pop() if len(albums) == 1 else "")

        pics = [e.pending.cover for e in self.entries]
        keys = {(p.data if p else None) for p in pics}
        pm = QPixmap()
        if pics and len(keys) == 1 and pics[0]:
            pm.loadFromData(pics[0].data)
        if pm.isNull():
            self.thumb.setPixmap(QPixmap())
            self.thumb.setText(tr("multiple") if len(keys) > 1 else tr("no\ncover"))
        else:
            self.thumb.setPixmap(pm.scaled(THUMB - 2, THUMB - 2, Qt.KeepAspectRatioByExpanding,
                                           Qt.SmoothTransformation))

    def _update_section_marks(self) -> None:
        bad_tabs = {BY_KEY[k].tab for e in self.entries for k in e.errors if k in BY_KEY}
        red = QColor(theme.current().red)
        for i, tab in enumerate(TABS):
            item = self.sections.item(i)
            item.setIcon(dot_icon(red if tab in bad_tabs else None))
            item.setToolTip(tr("This section has invalid fields") if tab in bad_tabs else "")

    def _update_visibility(self) -> None:
        """Solo se muestran los campos e imágenes que admiten todos los archivos seleccionados."""
        if not self.entries:
            return
        keys = frozenset.intersection(*(formats.supported_fields(e.path) for e in self.entries))
        pics = set.intersection(*(set(formats.picture_types(e.path)) for e in self.entries))
        for key, form in self.forms.items():
            form.setRowVisible(self.widgets[key], key in keys)
        for ptype, slot in self.slots.items():
            slot.setVisible(ptype in pics)
        for i, tab in enumerate(TABS):
            visible = bool(pics) if tab == "Images" else any(f.key in keys for f in fields_in_tab(tab))
            self.sections.setRowHidden(i, not visible)
        if self.sections.isRowHidden(self.sections.currentRow()):
            first = next(i for i in range(len(TABS)) if not self.sections.isRowHidden(i))
            self.sections.setCurrentRow(first)

    def refresh(self) -> None:
        n = len(self.entries)
        self._update_visibility()
        for f in FIELDS:
            w = self.widgets[f.key]
            vals = {e.pending.get(f.key) for e in self.entries}
            mixed = len(vals) > 1
            value = next(iter(vals)) if len(vals) == 1 else ""
            w.set_value(value, mixed=mixed, enabled=not (n > 1 and f.key in PER_TRACK))
        for ptype, slot in self.slots.items():
            pics = [e.pending.pictures.get(ptype) for e in self.entries]
            keys = {(p.data if p else None) for p in pics}
            slot.show_picture(pics[0] if pics and len(keys) == 1 else None, mixed=len(keys) > 1)
        self._update_header()
        self._update_section_marks()

    # --- cambios ----------------------------------------------------------------
    def _field_edited(self, key: str, value: str) -> None:
        for e in self.entries:
            e.pending.set(key, value)
            e.result, e.result_ok = "", None
        self._update_section_marks()
        if key in ("title", "artist", "album_artist", "album", "track"):
            self._update_header()
        self.changed.emit()

    def _picture_changed(self, ptype: int, pic) -> None:
        for e in self.entries:
            if pic is None:
                e.pending.pictures.pop(ptype, None)
            else:
                e.pending.pictures[ptype] = Picture(pic.data, pic.mime, pic.desc)
            e.result, e.result_ok = "", None
        self._update_header()
        self.changed.emit()
