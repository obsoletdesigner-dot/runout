"""Punto de entrada: python main.py [archivos o carpetas WAV...]"""
import sys

from PySide6.QtCore import QLibraryInfo, QSettings, QTranslator
from PySide6.QtWidgets import QApplication

from runout import APP_NAME
from runout.i18n import set_language
from runout.ui import theme
from runout.ui.icons import app_icon
from runout.ui.main_window import MainWindow
from runout.ui.preferences import Preferences


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Runout")
    app.setWindowIcon(app_icon())
    prefs = Preferences(QSettings("Runout", APP_NAME))
    language = set_language(prefs.language)
    if language != "en":
        # botones y diálogos estándar de Qt (Cancelar, Sí, No...) en el mismo idioma
        qt_translator = QTranslator(app)
        if qt_translator.load("qtbase_" + language, QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
            app.installTranslator(qt_translator)
    theme.apply(app, prefs.theme)
    win = MainWindow()
    # app.arguments() ya no lleva las opciones propias de Qt (-style, -platform...),
    # que PySide6 deja en sys.argv
    paths = app.arguments()[1:]
    if paths:
        win.add_paths(paths)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
