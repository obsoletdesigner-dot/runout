"""Ventana principal."""
from __future__ import annotations

import os

from PySide6.QtCore import QSettings, QSize, Qt, QThread
from PySide6.QtGui import QAction, QColor, QKeySequence
from PySide6.QtWidgets import (QApplication, QButtonGroup, QDockWidget, QFileDialog, QHBoxLayout,
                               QLabel, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
                               QPushButton, QRadioButton, QSizePolicy, QSplitter, QToolBar,
                               QVBoxLayout, QWidget)

from .. import APP_NAME
from ..core import formats, writer
from ..core.csv_import import parse_csv
from ..i18n import tr, tr_n
from . import theme
from .editor_panel import EditorPanel
from .icons import app_icon, toolbar_icon
from .preferences import Preferences, PreferencesDialog
from .save_worker import SaveWorker
from .track_table import TrackTableModel, TrackTableView


def collect_audio(paths: list[str], unreadable: list[str] | None = None) -> list[str]:
    """Archivos de audio admitidos, sueltos o dentro de carpetas (sin entrar en subcarpetas).

    Las carpetas que no se pueden leer se saltan y, si se pasa `unreadable`, se apuntan ahí.
    """
    out = []
    for p in paths:
        if os.path.isdir(p):
            try:
                names = sorted(os.listdir(p))
            except OSError as exc:
                if unreadable is not None:
                    unreadable.append("%s (%s)" % (p, exc.strerror or exc))
                continue
            for name in names:
                full = os.path.join(p, name)
                if os.path.isfile(full) and formats.is_supported(name) and not name.startswith("."):
                    out.append(full)
        elif os.path.isfile(p) and formats.is_supported(p):
            out.append(p)
    return out


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(1320, 800)
        self.setAcceptDrops(True)
        self.settings = QSettings("Runout", APP_NAME)
        self.prefs = Preferences(self.settings)
        self._thread: QThread | None = None
        self._job_entries: list = []
        self._batch_ok = self._batch_bad = 0      # resultados del guardado en curso
        self._worker: SaveWorker | None = None

        self.model = TrackTableModel(self)
        self.table = TrackTableView(self.model)
        self.panel = EditorPanel()
        self.panel.setMinimumWidth(480)

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(10)
        splitter.addWidget(self.table)
        splitter.addWidget(self.panel)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([720, 580])

        # --- barra inferior: modo de guardado y botón -----------------------
        self.rb_overwrite = QRadioButton(tr("Overwrite originals"))
        self.rb_overwrite.setToolTip(tr("Saves only the tracks with changes. The audio is verified "
                                        "with SHA-256 before each file is replaced."))
        self.rb_export = QRadioButton(tr("Copies in the tagged/ subfolder"))
        self.rb_export.setToolTip(tr("Writes copies of every track to folder/tagged/ "
                                     "and leaves the originals untouched."))
        group = QButtonGroup(self)
        group.addButton(self.rb_overwrite)
        group.addButton(self.rb_export)
        if self.settings.value("mode", "export") == "overwrite":
            self.rb_overwrite.setChecked(True)
        else:
            self.rb_export.setChecked(True)
        group.buttonToggled.connect(self._update_save_button)
        self.save_btn = QPushButton(tr("Save"))
        self.save_btn.setObjectName("primary")
        self.save_btn.setMinimumWidth(170)
        self.save_btn.setShortcut(QKeySequence.Save)
        self.save_btn.clicked.connect(self.save)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(180)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(2, 4, 2, 0)
        bottom.setSpacing(14)
        mode_label = QLabel(tr("On save:"))
        mode_label.setObjectName("muted")
        bottom.addWidget(mode_label)
        bottom.addWidget(self.rb_overwrite)
        bottom.addWidget(self.rb_export)
        bottom.addStretch(1)
        bottom.addWidget(self.progress)
        bottom.addWidget(self.save_btn)

        central = QWidget()
        v = QVBoxLayout(central)
        v.setContentsMargins(10, 4, 10, 6)
        v.setSpacing(8)
        v.addWidget(splitter, 1)
        v.addLayout(bottom)
        self.setCentralWidget(central)

        # --- registro (oculto por defecto) -------------------------------------
        self.log = QPlainTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(5000)
        self.log_dock = QDockWidget(tr("Log"), self)
        self.log_dock.setObjectName("log")
        self.log_dock.setWidget(self.log)
        self.log_dock.setFeatures(QDockWidget.DockWidgetClosable)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)
        self.log_dock.setMinimumHeight(120)
        self.log_dock.hide()

        # --- barra de estado -----------------------------------------------------
        self.summary = QLabel()
        self.summary.setObjectName("muted")
        self.statusBar().addPermanentWidget(self.summary)
        self.statusBar().setSizeGripEnabled(False)

        self._build_toolbar()

        self.panel.changed.connect(self.model.refresh_all)
        self.model.edited.connect(self.panel.refresh)
        self.table.selectionModel().selectionChanged.connect(self._selection_changed)
        self.model.modelReset.connect(self._selection_changed)
        self.model.changed.connect(self._update_save_button)
        self._update_save_button()

        hints = QApplication.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(self._system_theme_changed)

    # --- interfaz ------------------------------------------------------------
    def _build_toolbar(self):
        tb = QToolBar(tr("Main"))
        tb.setObjectName("main")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setIconSize(QSize(18, 18))
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        tb.toggleViewAction().setVisible(False)
        self.setContextMenuPolicy(Qt.NoContextMenu)
        self.addToolBar(tb)
        self._toolbar = tb
        self._actions: dict[str, QAction] = {}

        def act(key, text, slot, shortcut=None, tip=None, checkable=False):
            a = QAction(text, self)
            a.setCheckable(checkable)
            a.triggered.connect(slot)
            if shortcut:
                a.setShortcut(shortcut)
            a.setToolTip(tip or text)
            tb.addAction(a)
            self._actions[key] = a
            return a

        act("add_files", tr("Add files"), self.add_files_dialog, QKeySequence.Open)
        act("add_folder", tr("Add folder"), self.add_folder_dialog)
        tb.addSeparator()
        act("csv", tr("Import CSV"), self.import_csv,
            tip=tr("CSV with columns track,title,isrc (comma or semicolon separated)"))
        tb.addSeparator()
        act("remove", tr("Remove"), self.remove_selected, QKeySequence.Delete,
            tip=tr("Removes the selected tracks from the list (does not delete files)"))
        act("reload", tr("Reload"), self.reload_all, QKeySequence.Refresh,
            tip=tr("Discards unsaved changes and reads the files again"))
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)
        log_action = act("log", tr("Log"), self.log_dock.setVisible, checkable=True,
                         tip=tr("Shows or hides the detailed log"))
        self.log_dock.visibilityChanged.connect(log_action.setChecked)
        act("prefs", tr("Preferences"), self.open_preferences, QKeySequence("Ctrl+,"),
            tip=tr("ID3 version, LIST-INFO encoding, folder.jpg, theme and language"))
        self._refresh_icons()

    def _refresh_icons(self):
        color = QColor(theme.current().text)
        for key, a in self._actions.items():
            a.setIcon(toolbar_icon(key, color))

    def open_preferences(self):
        dialog = PreferencesDialog(self.prefs, self)
        if dialog.exec():
            self._apply_theme()
            if dialog.language_changed:
                QMessageBox.information(self, tr("Preferences"),
                                        tr("A language change takes effect when Runout is restarted."))

    def _apply_theme(self):
        theme.apply(QApplication.instance(), self.prefs.theme)
        self._refresh_icons()
        self.panel.refresh()
        self.model.refresh_all()
        self.table.viewport().update()

    def _system_theme_changed(self, *args):
        if self.prefs.theme == "system":
            self._apply_theme()

    def _log(self, text: str) -> None:
        self.log.appendPlainText(text)

    def _status(self, text: str) -> None:
        self.statusBar().showMessage(text, 15000)

    def _save_candidates(self) -> list[int]:
        export = self.rb_export.isChecked()
        return [r for r, e in enumerate(self.model.entries)
                if not e.status.error and (export or e.dirty)]

    @staticmethod
    def _short(path: str, base: str) -> str:
        """Ruta relativa a la carpeta del álbum (tagged/01.wav) en vez de la ruta completa."""
        try:
            rel = os.path.relpath(path, base)
        except ValueError:   # otra unidad en Windows
            return path
        return path if rel.startswith("..") else rel

    def _update_save_button(self, *args):
        n = len(self._save_candidates())
        export = self.rb_export.isChecked()
        if n:
            text = tr_n("Export %d track", "Export %d tracks", n) if export \
                else tr_n("Save %d track", "Save %d tracks", n)
            self.save_btn.setText(text % n)
        else:
            self.save_btn.setText(tr("Export") if export else tr("Save"))
        self.save_btn.setEnabled(n > 0 and self._thread is None)
        entries = self.model.entries
        if entries:
            dirty = sum(1 for e in entries if e.dirty)
            bad = sum(1 for e in entries if e.status.error or e.errors)
            parts = [tr_n("%d track", "%d tracks", len(entries)) % len(entries)]
            if dirty:
                parts.append(tr("%d with changes") % dirty)
            if bad:
                parts.append(tr("%d with errors") % bad)
            self.summary.setText(" · ".join(parts))
        else:
            self.summary.setText("")

    def _target_rows(self) -> list[int]:
        rows = self.table.selected_rows()
        return rows if rows else list(range(len(self.model.entries)))

    # --- carga -----------------------------------------------------------------
    def dragEnterEvent(self, event):
        if self._thread is None and event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if self._thread is not None:
            event.ignore()

    def dropEvent(self, event):
        if self._thread is not None:      # no se añaden pistas mientras se guarda
            event.ignore()
            return
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        self.add_paths(paths)

    def add_paths(self, paths: list[str]) -> None:
        unreadable: list[str] = []
        wavs = collect_audio(paths, unreadable)
        for folder in unreadable:
            self._log(tr("Cannot read the folder %s") % folder)
        if not wavs:
            self._log(tr("No supported audio files found in what you dropped."))
            self._status(tr("No supported audio files found in what you dropped."))
            return
        added = self.model.add_paths(wavs)
        self._log(tr("Loaded %d files (%d were already in the list).") % (len(added), len(wavs) - len(added)))
        n_warn = sum(1 for e in self.model.entries if e.path in added and (e.status.error or e.status.warnings))
        status = tr_n("%d track loaded", "%d tracks loaded", len(added)) % len(added)
        if n_warn:
            status += " · " + tr("%d with warnings (details in the Log)") % n_warn
        self._status(status)
        for e in self.model.entries:
            if e.path in added:
                if e.status.error:
                    self._log("  ✘ %s: %s" % (os.path.basename(e.path), e.status.error))
                for w in e.status.warnings:
                    self._log("  ! %s: %s" % (os.path.basename(e.path), w))
        if wavs:
            self.settings.setValue("last_dir", os.path.dirname(wavs[0]))

    def add_files_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, tr("Add audio files"), self.settings.value("last_dir", ""),
            tr("Audio files") + " (%s)" % " ".join("*" + ext for ext in formats.EXTENSIONS))
        if files:
            self.add_paths(files)

    def add_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, tr("Add folder"), self.settings.value("last_dir", ""))
        if folder:
            self.add_paths([folder])

    def remove_selected(self):
        rows = self.table.selected_rows()
        if rows:
            self.model.remove_rows(rows)

    def reload_all(self):
        if any(e.dirty for e in self.model.entries):
            if QMessageBox.question(self, tr("Reload"), tr("Unsaved changes will be lost. Continue?")) \
                    != QMessageBox.Yes:
                return
        for e in self.model.entries:
            e.reload()
            e.result, e.result_ok = "", None
        self.model.refresh_all()
        self._log(tr("Files read again from disk."))
        self._status(tr("Files read again from disk"))

    # --- editor ---------------------------------------------------------------
    def _selection_changed(self, *args):
        rows = self.table.selected_rows()
        self.panel.set_entries([self.model.entries[r] for r in rows if r < len(self.model.entries)])

    # --- CSV ------------------------------------------------------------------
    def import_csv(self):
        if not self.model.entries:
            QMessageBox.information(self, tr("Import CSV"), tr("Load the album's audio files first."))
            return
        path, _ = QFileDialog.getOpenFileName(self, tr("Import CSV"), self.settings.value("last_dir", ""),
                                              "CSV (*.csv *.txt)")
        if not path:
            return
        rows, warnings = parse_csv(path)
        by_track = {}
        for e in self.model.entries:
            if e.pending.track is not None and not e.status.error:
                by_track.setdefault(e.pending.track, e)
        matched, unmatched = [], []
        for row in rows:
            e = by_track.get(row.pista)
            (matched if e else unmatched).append((row, e))
        lines = [tr("%d rows in the CSV, %d match loaded tracks.") % (len(rows), len(matched))]
        if unmatched:
            lines.append(tr("No loaded track for: ") + ", ".join(str(r.pista) for r, _ in unmatched))
        bad = [r for r, _ in matched if r.isrc and len(r.isrc) != 12]
        if bad:
            lines.append(tr("ISRC with a doubtful format in tracks: ") + ", ".join(str(r.pista) for r in bad))
        lines += warnings
        if not matched:
            QMessageBox.warning(self, tr("Import CSV"), "\n".join(lines))
            return
        if QMessageBox.question(self, tr("Import CSV"), "\n".join(lines) + "\n\n" + tr("Apply title and ISRC?")) \
                != QMessageBox.Yes:
            return
        for row, e in matched:
            if row.titulo:
                e.pending.set("title", row.titulo)
            if row.isrc:
                e.pending.set("isrc", row.isrc)
            e.result, e.result_ok = "", None
        self.model.refresh_all()
        self.panel.refresh()
        self._log(tr("CSV imported: %s (%d tracks updated).") % (os.path.basename(path), len(matched)))
        self._status(tr("CSV imported: %d tracks updated") % len(matched))

    # --- guardado ------------------------------------------------------------
    def _confirm_in_place_export(self, entries) -> bool:
        """Los archivos que ya están en una carpeta tagged/ se reexportan en su sitio,
        es decir, se sobrescriben. Se pide confirmación dos veces."""
        in_place = [e for e in entries
                    if writer.export_path(e.path) == os.path.abspath(e.path)]
        if not in_place:
            return True
        names = [os.path.basename(e.path) for e in in_place]
        listed = "\n".join("· " + n for n in names[:10])
        if len(names) > 10:
            listed += "\n" + tr("…and %d more") % (len(names) - 10)
        n = len(in_place)
        first = QMessageBox.warning(
            self, tr("Overwrite files"),
            tr_n("%d file is already in a tagged/ folder, so exporting will overwrite it "
                 "instead of making a new copy:",
                 "%d files are already in a tagged/ folder, so exporting will overwrite them "
                 "instead of making new copies:", n) % n
            + "\n\n" + listed + "\n\n" + tr("Overwrite them?"),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if first != QMessageBox.Yes:
            return False
        second = QMessageBox.warning(
            self, tr("Overwrite files"),
            tr_n("Are you sure? %d file will be overwritten.",
                 "Are you sure? %d files will be overwritten.", n) % n,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return second == QMessageBox.Yes

    def save(self):
        export = self.rb_export.isChecked()
        id3_version = self.prefs.id3_version
        self.settings.setValue("mode", "export" if export else "overwrite")

        candidates = [(r, e) for r, e in enumerate(self.model.entries) if not e.status.error]
        if not export:
            candidates = [(r, e) for r, e in candidates if e.dirty]
        if not candidates:
            QMessageBox.information(self, tr("Save"), tr("There are no changes to save."))
            return

        invalid = [e for _, e in candidates if e.errors]
        if invalid:
            QMessageBox.warning(self, tr("Invalid data"),
                                tr("Fix these fields before saving (they are red in the editor):") + "\n\n"
                                + "\n\n".join("· %s\n%s" % (os.path.basename(e.path), e.errors_text())
                                              for e in invalid))
            return
        dups = self.model.duplicate_isrcs()
        if dups and QMessageBox.question(
                self, tr("Duplicate ISRC"),
                tr("Some tracks share an ISRC (%s). Each recording should have its own.\n"
                   "Save anyway?") % ", ".join(sorted(dups))) != QMessageBox.Yes:
            return
        if not export and QMessageBox.question(
                self, tr("Overwrite originals"),
                tr("%d original files will be modified.\n\nThe audio is not touched: each file is "
                   "first written to a temporary file and only replaced if the SHA-256 of the data "
                   "chunk matches exactly.\n\nContinue?") % len(candidates)) != QMessageBox.Yes:
            return
        if export and not self._confirm_in_place_export([e for _, e in candidates]):
            return

        # cada trabajo se identifica por su posición en esta lista, no por la fila
        # de la tabla: las filas pueden moverse mientras se guarda
        self._job_entries = [e for _, e in candidates]
        self._batch_ok = self._batch_bad = 0
        jobs = [(i, e.path, e.pending.copy()) for i, e in enumerate(self._job_entries)]
        self._export_mode = export
        self._log(tr("Saving %d files (%s, ID3v2.%d)…") % (
            len(jobs), tr("export to /tagged") if export else tr("overwrite"), id3_version))
        self._set_busy(True, len(jobs))
        self._worker = SaveWorker(jobs, export, id3_version, self.prefs.info_encoding, self.prefs.folder_art)
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.track_done.connect(self._on_track_done)
        # métodos de la ventana (no lambdas) para que Qt los ejecute en el hilo de la interfaz
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_save_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.start()

    def _on_progress(self, done: int, total: int):
        self.progress.setValue(done)

    def _set_busy(self, busy: bool, total: int = 0):
        self.save_btn.setEnabled(not busy)
        self.panel.setEnabled(not busy)
        self.table.setEnabled(not busy)
        for tb in self.findChildren(QToolBar):
            tb.setEnabled(not busy)
        self.progress.setVisible(busy)
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(0)

    def _on_track_done(self, job: int, ok: bool, message: str, dest: str, warnings: list):
        e = self._job_entries[job]
        if ok:
            self._batch_ok += 1
        else:
            self._batch_bad += 1
        row = next((r for r, x in enumerate(self.model.entries) if x is e), None)
        if row is None:
            return
        name = os.path.basename(e.path)
        base = os.path.dirname(e.path)
        if os.path.basename(base).lower() == "tagged":
            base = os.path.dirname(base)
        for w in warnings:
            self._log("  ! %s: %s" % (name, w))
        e.extra_warnings = list(warnings)
        if ok:
            if self._export_mode and dest and os.path.abspath(dest) != os.path.abspath(e.path):
                # a partir de ahora la fila trabaja con la copia de /tagged
                e.path = dest
                e.result = tr("Exported to tagged/ (audio verified)")
            else:
                e.result = tr("Saved (audio verified)")
            e.reload()
            e.extra_warnings = list(warnings)
            e.result_ok = True
            target = self._short(dest, base)
            self._log("  ✔ %s%s · %s" % (name, "" if target == name else " → " + target, message))
        else:
            e.result, e.result_ok = "ERROR: " + message, False
            self._log(tr("  ✘ %s: %s (the original has not been modified)") % (name, message))
        self.model.refresh_row(row)

    def _on_save_finished(self):
        self._set_busy(False)
        ok, bad = self._batch_ok, self._batch_bad
        self._log(tr("Finished: %d OK, %d with errors.") % (ok, bad))
        done = (tr("%d exported") if self._export_mode else tr("%d saved")) % ok
        if bad:
            self._status(done + " · " + tr("%d with errors (originals untouched)") % bad)
        else:
            self._status(done + " · " + tr("audio verified with SHA-256"))
        if bad:
            self.log_dock.show()
            QMessageBox.warning(self, tr("Save"), tr("%d files could not be saved. Their originals "
                                                   "have not been modified. See the log.") % bad)
        self._thread = None
        self._worker = None
        self._job_entries = []
        self._update_save_button()
        self.model.drop_duplicate_paths()
        self.model.refresh_all()
        self._selection_changed()

    def closeEvent(self, event):
        if self._thread is not None:
            QMessageBox.information(self, APP_NAME, tr("Wait for the save to finish."))
            event.ignore()
            return
        if any(e.dirty for e in self.model.entries) and QMessageBox.question(
                self, APP_NAME, tr("There are unsaved changes. Quit anyway?")) != QMessageBox.Yes:
            event.ignore()
            return
        event.accept()
