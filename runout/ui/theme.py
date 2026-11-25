"""Tema claro y oscuro (Fusion + paleta propia). Por defecto sigue al sistema."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication


@dataclass(frozen=True)
class Colors:
    window: str
    base: str
    alt: str
    text: str
    muted: str
    border: str
    button: str
    accent: str
    accent_text: str
    selection: str
    green: str
    amber: str
    red: str


DARK = Colors(window="#1d1e21", base="#25262a", alt="#2a2b30", text="#e7e7ea", muted="#8d8e96",
              border="#3a3b41", button="#2f3036", accent="#e0892f", accent_text="#1b1b1d",
              selection="#4a3622", green="#4cbf6b", amber="#e6a23c", red="#f0645a")
LIGHT = Colors(window="#f3f3f5", base="#ffffff", alt="#f7f7f9", text="#1d1d20", muted="#75767e",
               border="#d6d6dc", button="#fbfbfc", accent="#cf7420", accent_text="#ffffff",
               selection="#f6dfc6", green="#1e9e4a", amber="#c27c0e", red="#d33a2c")

_current = DARK


def current() -> Colors:
    return _current


def system_is_dark() -> bool:
    hints = QGuiApplication.styleHints()
    if hasattr(hints, "colorScheme"):
        scheme = hints.colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
    return QGuiApplication.palette().color(QPalette.Window).lightness() < 128


def resolve(mode: str) -> Colors:
    if mode == "dark":
        return DARK
    if mode == "light":
        return LIGHT
    return DARK if system_is_dark() else LIGHT


def apply(app: QApplication, mode: str = "system") -> Colors:
    global _current
    c = _current = resolve(mode)
    app.setStyle("Fusion")
    pal = QPalette()
    q = QColor
    for group in (QPalette.Active, QPalette.Inactive):
        pal.setColor(group, QPalette.Window, q(c.window))
        pal.setColor(group, QPalette.WindowText, q(c.text))
        pal.setColor(group, QPalette.Base, q(c.base))
        pal.setColor(group, QPalette.AlternateBase, q(c.alt))
        pal.setColor(group, QPalette.Text, q(c.text))
        pal.setColor(group, QPalette.PlaceholderText, q(c.muted))
        pal.setColor(group, QPalette.Button, q(c.button))
        pal.setColor(group, QPalette.ButtonText, q(c.text))
        pal.setColor(group, QPalette.Highlight, q(c.selection))
        pal.setColor(group, QPalette.HighlightedText, q(c.text))
        pal.setColor(group, QPalette.ToolTipBase, q(c.base))
        pal.setColor(group, QPalette.ToolTipText, q(c.text))
        pal.setColor(group, QPalette.Link, q(c.accent))
        pal.setColor(group, QPalette.Mid, q(c.border))
        pal.setColor(group, QPalette.Light, q(c.alt))
        pal.setColor(group, QPalette.Dark, q(c.border))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, q(c.muted))
    dim = q(c.muted)
    dim.setAlpha(110)
    pal.setColor(QPalette.Disabled, QPalette.PlaceholderText, dim)
    pal.setColor(QPalette.Disabled, QPalette.Base, q(c.alt))
    pal.setColor(QPalette.Disabled, QPalette.Button, q(c.window))
    app.setPalette(pal)
    app.setStyleSheet(stylesheet(c))
    return c


def stylesheet(c: Colors) -> str:
    return f"""
QToolBar {{ border: none; spacing: 2px; padding: 4px 6px; background: {c.window}; }}
QToolBar::separator {{ width: 1px; background: {c.border}; margin: 6px 6px; }}
QToolButton {{ padding: 4px 8px; border-radius: 5px; color: {c.text}; }}
QToolButton:hover {{ background: {c.alt}; }}
QToolButton:checked {{ background: {c.selection}; }}
QTableView {{ border: 1px solid {c.border}; border-radius: 6px; gridline-color: {c.border}; }}
QRadioButton::indicator, QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {c.muted};
    background: {c.base}; }}
QRadioButton::indicator {{ border-radius: 8px; }}
QCheckBox::indicator {{ border-radius: 3px; }}
QRadioButton::indicator:checked {{ border: 4px solid {c.accent}; width: 8px; height: 8px;
    border-radius: 8px; }}
QCheckBox::indicator:checked {{ background: {c.accent}; border-color: {c.accent}; }}
QHeaderView::section {{ background: {c.window}; color: {c.muted}; border: none;
    border-bottom: 1px solid {c.border}; padding: 5px 6px; font-weight: 600; }}
QListWidget#sections {{ border: none; background: transparent; outline: 0; }}
QListWidget#sections::item {{ padding: 6px 8px; border-radius: 5px; color: {c.text}; }}
QListWidget#sections::item:hover {{ background: {c.alt}; }}
QListWidget#sections::item:selected {{ background: {c.selection}; color: {c.text}; }}
QFrame#editor {{ background: {c.base}; border: 1px solid {c.border}; border-radius: 8px; }}
QFrame#editorHeader {{ border: none; border-bottom: 1px solid {c.border}; border-radius: 0; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget#qt_scrollarea_viewport > QWidget {{ background: transparent; }}
QLabel#trackTitle {{ font-size: 16px; font-weight: 600; }}
QLabel#muted {{ color: {c.muted}; }}
QLabel#sectionTitle {{ font-size: 14px; font-weight: 600; padding: 2px 0 6px 0; }}
QLabel#thumb {{ border: 1px solid {c.border}; border-radius: 4px; background: {c.alt};
    color: {c.muted}; }}
QPushButton#primary {{ background: {c.accent}; color: {c.accent_text}; border: none;
    border-radius: 6px; padding: 8px 22px; font-weight: 600; }}
QPushButton#primary:hover {{ background: {QColor(c.accent).lighter(110).name()}; }}
QPushButton#primary:disabled {{ background: {c.border}; color: {c.muted}; }}
QStatusBar {{ color: {c.muted}; }}
QStatusBar::item {{ border: none; }}
QDockWidget::title {{ padding: 4px 8px; color: {c.muted}; }}
QPlainTextEdit#log {{ border: none; font-family: "Menlo", "Consolas", "DejaVu Sans Mono", monospace;
    font-size: 12px; }}
QProgressBar {{ border: 1px solid {c.border}; border-radius: 4px; text-align: center;
    max-height: 14px; }}
QProgressBar::chunk {{ background: {c.accent}; border-radius: 3px; }}
"""
