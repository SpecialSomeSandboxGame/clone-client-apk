"""Theme stylesheets with a small design system for the desktop UI."""

from __future__ import annotations

LIGHT = {
    "bg": "#f6f8fa",
    "card": "#ffffff",
    "input": "#ffffff",
    "border": "#d0d7de",
    "text": "#1f2328",
    "muted": "#57606a",
    "accent": "#0969da",
    "accent_hover": "#0550ae",
    "success": "#1a7f37",
    "warning": "#9a6700",
    "error": "#cf222e",
    "secondary": "#f6f8fa",
    "secondary_hover": "#eef2f6",
    "disabled": "#8c959f",
}

DARK = {
    "bg": "#0d1117",
    "card": "#161b22",
    "input": "#0d1117",
    "border": "#30363d",
    "text": "#e6edf3",
    "muted": "#8b949e",
    "accent": "#2f81f7",
    "accent_hover": "#58a6ff",
    "success": "#3fb950",
    "warning": "#d29922",
    "error": "#f85149",
    "secondary": "#21262d",
    "secondary_hover": "#30363d",
    "disabled": "#484f58",
}

_TEMPLATE = """
QMainWindow, QWidget#page {
    background-color: %(bg)s;
}
QWidget {
    color: %(text)s;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QScrollArea, QScrollArea > QWidget > QWidget, QWidget#scrollContent {
    background: transparent;
    border: none;
}
QFrame#card {
    background-color: %(card)s;
    border: 1px solid %(border)s;
    border-radius: 10px;
}
QFrame#footer {
    background-color: %(card)s;
    border-top: 1px solid %(border)s;
}
QFrame#resultCard {
    background-color: %(card)s;
    border: 1px solid %(border)s;
    border-radius: 10px;
}
QFrame#resultCard[state="success"] {
    border-color: %(success)s;
}
QFrame#resultCard[state="error"] {
    border-color: %(error)s;
}
QFrame#resultCard[state="neutral"] {
    border-color: %(border)s;
}
QLabel {
    background: transparent;
}
QLabel#appTitle {
    font-size: 18pt;
    font-weight: 700;
}
QLabel#subtitle, QLabel#muted {
    color: %(muted)s;
}
QLabel#sectionTitle {
    font-size: 12pt;
    font-weight: 600;
}
QLabel#fieldLabel {
    color: %(muted)s;
    font-size: 9pt;
    font-weight: 600;
}
QLabel#error {
    color: %(error)s;
}
QLabel#warning {
    color: %(warning)s;
}
QLabel#success {
    color: %(success)s;
}
QLabel#resultSuccess {
    color: %(success)s;
    font-size: 12pt;
    font-weight: 600;
}
QLabel#resultError {
    color: %(error)s;
    font-size: 12pt;
    font-weight: 600;
}
QLabel#resultNeutral {
    color: %(text)s;
    font-size: 12pt;
    font-weight: 600;
}
QLabel#mono {
    font-family: "Consolas", monospace;
}
QLabel#stagePending {
    color: %(muted)s;
}
QLabel#stageRunning {
    color: %(accent)s;
    font-weight: 600;
}
QLabel#stageDone {
    color: %(success)s;
    font-weight: 600;
}
QLabel#stageFailed {
    color: %(error)s;
    font-weight: 600;
}
QPushButton {
    background-color: %(secondary)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 6px;
    padding: 6px 12px;
}
QPushButton:hover {
    background-color: %(secondary_hover)s;
}
QPushButton:pressed {
    background-color: %(border)s;
}
QPushButton:disabled {
    color: %(disabled)s;
    background-color: %(secondary)s;
}
QPushButton#primary {
    background-color: %(accent)s;
    color: #ffffff;
    border: none;
    font-weight: 600;
    padding: 9px 18px;
}
QPushButton#primary:hover {
    background-color: %(accent_hover)s;
}
QPushButton#primary:disabled {
    background-color: %(disabled)s;
    color: #ffffff;
}
QPushButton#ghost {
    background: transparent;
    color: %(accent)s;
    border: none;
    padding: 4px 6px;
}
QPushButton#ghost:hover {
    background-color: %(secondary_hover)s;
}
QPushButton#ghost:disabled {
    color: %(muted)s;
}
QToolButton {
    background: transparent;
    color: %(accent)s;
    border: none;
    padding: 2px 4px;
}
QToolButton:disabled {
    color: %(muted)s;
}
QToolButton:hover {
    background-color: %(secondary_hover)s;
    border-radius: 4px;
}
QLineEdit, QComboBox {
    background-color: %(input)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: %(accent)s;
    selection-color: #ffffff;
}
QLineEdit:focus, QComboBox:focus {
    border-color: %(accent)s;
}
QLineEdit[invalid="true"] {
    border-color: %(error)s;
}
QLineEdit[invalid="true"]:focus {
    border-color: %(error)s;
}
QLineEdit {
    placeholder-text-color: %(muted)s;
}
QPlainTextEdit {
    background-color: %(input)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 6px;
    padding: 8px;
    font-family: "Consolas", monospace;
    font-size: 9pt;
}
QProgressBar {
    background-color: %(input)s;
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: %(accent)s;
    border-radius: 4px;
}
QProgressBar[state="success"]::chunk {
    background-color: %(success)s;
}
QProgressBar[state="error"]::chunk {
    background-color: %(error)s;
}
QProgressBar[state="neutral"]::chunk {
    background-color: %(muted)s;
}
QTabWidget::pane {
    border: none;
}
QTabBar::tab {
    background: transparent;
    color: %(muted)s;
    padding: 8px 16px;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected {
    color: %(text)s;
    border-bottom-color: %(accent)s;
    font-weight: 600;
}
QTabBar::tab:hover {
    color: %(text)s;
}
QComboBox QAbstractItemView {
    background-color: %(card)s;
    color: %(text)s;
    selection-background-color: %(accent)s;
    selection-color: #ffffff;
}
QSplitter::handle {
    background: transparent;
}
"""


def stylesheet_for(theme: str) -> str:
    colors = DARK if theme == "dark" else LIGHT
    return _TEMPLATE % colors
