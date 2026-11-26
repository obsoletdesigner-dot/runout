"""Ventana principal sin pantalla (Qt offscreen) y con la configuración en un temporal."""
from __future__ import annotations

import os
import shutil
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QMimeData, QPointF, Qt, QSettings, QUrl  # noqa: E402
from PySide6.QtGui import QDropEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from runout.ui.main_window import MainWindow  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    # nunca tocar la configuración real del usuario: pytest gestiona y limpia esta carpeta
    settings_dir = str(tmp_path_factory.mktemp("settings"))
    QSettings.setPath(QSettings.NativeFormat, QSettings.UserScope, settings_dir)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, settings_dir)
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    win = MainWindow()
    yield win
    win._thread = None
    win.deleteLater()


def _copy(tmp_path, name, dest_name):
    dest = tmp_path / dest_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(os.path.join(FIXTURES, name), dest)
    return str(dest)


def test_save_result_goes_to_its_own_track_after_rows_move(window, tmp_path):
    z = _copy(tmp_path, "sample.flac", "z.flac")
    window.model.add_paths([z])
    entry_z = window.model.entries[0]

    # empieza un guardado de z…
    window._job_entries = [entry_z]
    window._export_mode = True
    # …y entra otra pista que se ordena delante, así que z pasa a la fila 1
    a = _copy(tmp_path, "sample.flac", "a.flac")
    window.model.add_paths([a])
    assert window.model.entries[1] is entry_z

    dest = _copy(tmp_path, "sample.flac", "tagged/z.flac")
    window._on_track_done(0, True, "ok", dest, [])

    assert entry_z.path == dest
    entry_a = window.model.entries[0]
    assert entry_a.path == os.path.abspath(a)
    assert entry_a.result_ok is None


def test_drop_is_ignored_while_saving(window, tmp_path):
    a = _copy(tmp_path, "sample.flac", "a.flac")
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(a)])
    ev = QDropEvent(QPointF(5, 5), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)

    window._thread = object()           # simula un guardado en marcha
    window.dropEvent(ev)
    assert window.model.entries == []

    window._thread = None
    window.dropEvent(ev)
    assert len(window.model.entries) == 1
