"""Guardado en un hilo aparte para no congelar la interfaz."""
from __future__ import annotations

import os

from PySide6.QtCore import QObject, Signal, Slot

from ..core import formats, writer
from ..core.model import TrackMetadata
from ..i18n import tr


class SaveWorker(QObject):
    progress = Signal(int, int)                 # hechos, total
    track_done = Signal(int, bool, str, str, list)   # fila, ok, mensaje, destino, avisos
    finished = Signal()

    def __init__(self, jobs: list[tuple[int, str, TrackMetadata]], export: bool,
                 id3_version: int, info_encoding: str = "utf-8", folder_art: bool = False):
        super().__init__()
        self.jobs = jobs
        self.export = export
        self.options = formats.SaveOptions(id3_version=id3_version, info_encoding=info_encoding)
        self.folder_art = folder_art
        self._cancel = False

    def cancel(self):
        self._cancel = True

    @Slot()
    def run(self):
        total = len(self.jobs)
        for done, (row, path, meta) in enumerate(self.jobs, start=1):
            if self._cancel:
                break
            dest = writer.export_path(path) if self.export else None
            try:
                res = formats.save_track(path, meta, dest, self.options)
                if res.ok and self.folder_art and meta.cover:
                    try:
                        art = writer.write_folder_art(os.path.dirname(res.dest), meta.cover)
                        if art:
                            res.warnings.append(tr("Cover also saved as %s")
                                            % os.path.relpath(art, os.path.dirname(path)))
                    except Exception as exc:  # la portada externa nunca bloquea el guardado
                        res.warnings.append(tr("Could not save folder.jpg: %s") % exc)
                self.track_done.emit(row, res.ok, res.message, res.dest, res.warnings)
            except Exception as exc:  # nunca dejar el hilo colgado
                self.track_done.emit(row, False, tr("Unexpected error: %s") % exc, "", [])
            self.progress.emit(done, total)
        self.finished.emit()
