# -*- mode: python ; coding: utf-8 -*-
# Receta de PyInstaller para Windows, macOS y Linux.
# Uso (en cada sistema):  pyinstaller --noconfirm --clean runout.spec
import re
import sys

from PyInstaller.utils.hooks import collect_data_files

# Módulos de Qt que la app no usa: se excluyen para reducir el tamaño.
QT_EXCLUDES = [
    "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebChannel",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.Qt3DCore",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtPdf", "PySide6.QtSql",
    "PySide6.QtTest", "PySide6.QtBluetooth", "PySide6.QtPositioning", "PySide6.QtSensors",
    "PySide6.QtSerialPort", "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtSvg",
    "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtUiTools", "tkinter",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    # tablas ISO 639-3 / 3166 / 15924 (con sus traducciones) y los idiomas de la interfaz
    datas=collect_data_files("pycountry") + [("runout/locales/*.json", "runout/locales")],
    hiddenimports=[],
    excludes=QT_EXCLUDES,
    noarchive=False,
)
pyz = PYZ(a.pure)

with open("runout/__init__.py", encoding="utf-8") as fh:
    VERSION = re.search(r'__version__ = "([^"]+)"', fh.read()).group(1)

# Iconos generados con: python tools/make_icons.py
ICON_WIN = "assets/runout.ico"
ICON_MAC = "assets/runout.icns"

if sys.platform == "darwin":
    # macOS: carpeta + bundle Runout.app (onefile no se recomienda en macOS)
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Runout",
              console=False, upx=False, argv_emulation=False, icon=ICON_MAC)
    coll = COLLECT(exe, a.binaries, a.datas, name="Runout", upx=False)
    app = BUNDLE(coll, name="Runout.app", icon=ICON_MAC, bundle_identifier="io.github.obsoletdesigner-dot.runout",
                 info_plist={"NSHighResolutionCapable": True,
                             "CFBundleShortVersionString": VERSION,
                             "CFBundleVersion": VERSION})
else:
    # Windows y Linux: un único ejecutable
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="Runout",
              console=False, upx=False, runtime_tmpdir=None,
              icon=ICON_WIN if sys.platform == "win32" else None)
