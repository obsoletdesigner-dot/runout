"""Errores no previstos: que nunca se pierdan en silencio."""
from __future__ import annotations

import sys
import traceback

from ..i18n import tr


def install_excepthook(win) -> None:
    """Los errores no previstos van al Log de la ventana (y a la consola si la hay).

    En la versión compilada no hay consola: sin esto, una acción que falla
    simplemente no hace nada y no queda rastro de por qué.
    """
    def hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        if sys.__stderr__ is not None:
            sys.__stderr__.write(text)
        try:
            win.log.appendPlainText(tr("Unexpected error:") + "\n" + text.rstrip())
            win.log_dock.show()
            win.statusBar().showMessage(tr("Unexpected error (details in the Log)"), 15000)
        except Exception:  # la ventana ya no existe: al menos que no se pierda en silencio
            pass

    sys.excepthook = hook
