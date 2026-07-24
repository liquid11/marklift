"""System-aware visual theme for the desktop application."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication


def _is_dark(application: QApplication) -> bool:
    """Return whether the current Windows/Qt color scheme is dark."""

    try:
        scheme = application.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
    except AttributeError:
        pass
    window_color = application.palette().color(QPalette.ColorRole.Window)
    return window_color.lightness() < 128


def _stylesheet(dark: bool) -> str:
    if dark:
        colors = {
            "background": "#17191c",
            "surface": "#202328",
            "surface_alt": "#272b31",
            "hover": "#30353c",
            "text": "#f3f4f6",
            "muted": "#b8bec8",
            "border": "#3d434c",
            "accent": "#60a5fa",
            "accent_hover": "#7db5fb",
            "accent_text": "#0b1220",
            "success": "#86efac",
            "success_bg": "#173828",
            "warning": "#fcd34d",
            "warning_bg": "#3b2f12",
            "danger": "#fca5a5",
        }
    else:
        colors = {
            "background": "#f3f5f8",
            "surface": "#ffffff",
            "surface_alt": "#f7f8fa",
            "hover": "#edf1f5",
            "text": "#18212f",
            "muted": "#596474",
            "border": "#d6dce4",
            "accent": "#2563eb",
            "accent_hover": "#1d4ed8",
            "accent_text": "#ffffff",
            "success": "#166534",
            "success_bg": "#dcfce7",
            "warning": "#92400e",
            "warning_bg": "#fef3c7",
            "danger": "#b91c1c",
        }

    return f"""
        QWidget {{
            color: {colors["text"]};
            font-family: "Segoe UI";
            font-size: 10pt;
        }}
        QWidget#appRoot {{
            background: {colors["background"]};
        }}
        QFrame#appHeader {{
            background: transparent;
        }}
        QLabel#appTitle {{
            font-size: 18pt;
            font-weight: 600;
        }}
        QLabel#sectionTitle {{
            font-size: 11pt;
            font-weight: 600;
        }}
        QLabel#secondaryText, QLabel#fileContext, QLabel#optionHelp {{
            color: {colors["muted"]};
        }}
        QLabel#offlineBadge {{
            color: {colors["success"]};
            background: {colors["success_bg"]};
            border: 1px solid {colors["success"]};
            border-radius: 11px;
            padding: 4px 10px;
            font-weight: 600;
        }}
        QFrame#card {{
            background: {colors["surface"]};
            border: 1px solid {colors["border"]};
            border-radius: 10px;
        }}
        QPushButton {{
            background: {colors["surface_alt"]};
            border: 1px solid {colors["border"]};
            border-radius: 6px;
            min-height: 30px;
            padding: 3px 12px;
        }}
        QPushButton:hover {{
            background: {colors["hover"]};
        }}
        QPushButton:focus {{
            border: 2px solid {colors["accent"]};
            padding: 2px 11px;
        }}
        QPushButton:disabled {{
            color: {colors["muted"]};
            background: {colors["surface_alt"]};
        }}
        QPushButton[primary="true"] {{
            color: {colors["accent_text"]};
            background: {colors["accent"]};
            border-color: {colors["accent"]};
            font-weight: 600;
        }}
        QPushButton[primary="true"]:hover {{
            background: {colors["accent_hover"]};
            border-color: {colors["accent_hover"]};
        }}
        QPushButton[primary="true"]:disabled {{
            color: {colors["muted"]};
            background: {colors["surface_alt"]};
            border-color: {colors["border"]};
        }}
        QPushButton#dropZone {{
            color: {colors["text"]};
            background: {colors["surface_alt"]};
            border: 2px dashed {colors["border"]};
            border-radius: 8px;
            min-height: 78px;
            padding: 12px;
            font-size: 11pt;
            font-weight: 600;
        }}
        QPushButton#dropZone:hover, QPushButton#dropZone:focus {{
            color: {colors["accent"]};
            background: {colors["hover"]};
            border-color: {colors["accent"]};
        }}
        QCheckBox {{
            spacing: 7px;
        }}
        QCheckBox::indicator {{
            width: 17px;
            height: 17px;
        }}
        QTableWidget {{
            background: {colors["surface"]};
            alternate-background-color: {colors["surface_alt"]};
            border: 0;
            gridline-color: transparent;
            selection-background-color: {colors["hover"]};
            selection-color: {colors["text"]};
        }}
        QHeaderView::section {{
            color: {colors["muted"]};
            background: {colors["surface_alt"]};
            border: 0;
            border-bottom: 1px solid {colors["border"]};
            padding: 8px;
            font-weight: 600;
        }}
        QProgressBar {{
            background: {colors["surface_alt"]};
            border: 0;
            border-radius: 3px;
            min-height: 6px;
            max-height: 6px;
        }}
        QProgressBar::chunk {{
            background: {colors["accent"]};
            border-radius: 3px;
        }}
        QLabel#queueState[kind="ready"], QLabel#queueState[kind="saved"] {{
            color: {colors["success"]};
        }}
        QLabel#queueState[kind="failed"] {{
            color: {colors["danger"]};
        }}
        QLabel#queueState[kind="cancelled"] {{
            color: {colors["muted"]};
        }}
        QLabel#queueState[kind="active"] {{
            color: {colors["accent"]};
        }}
        QLabel#warningCallout {{
            color: {colors["warning"]};
            background: {colors["warning_bg"]};
            border: 1px solid {colors["warning"]};
            border-radius: 6px;
            padding: 9px;
        }}
        QLabel#sourceCanvas, QTextBrowser#markdownCanvas {{
            color: {colors["text"]};
            background: {colors["surface_alt"]};
            border: 1px solid {colors["border"]};
            border-radius: 6px;
            padding: 8px;
        }}
        QSplitter::handle {{
            background: {colors["background"]};
            width: 10px;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 12px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical {{
            background: {colors["border"]};
            border-radius: 5px;
            min-height: 28px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QStatusBar {{
            color: {colors["muted"]};
            background: {colors["background"]};
            border-top: 1px solid {colors["border"]};
        }}
        QMessageBox {{
            background: {colors["surface"]};
        }}
    """


def apply_theme(application: QApplication) -> None:
    """Apply the theme that matches the current system color scheme."""

    application.setStyleSheet(_stylesheet(_is_dark(application)))


def bind_system_theme(application: QApplication) -> None:
    """Apply the current theme and keep it synchronized with Windows."""

    apply_theme(application)

    def refresh_theme(_scheme: Qt.ColorScheme | None = None) -> None:
        apply_theme(application)

    application.styleHints().colorSchemeChanged.connect(refresh_theme)
    application._marklift_theme_callback = refresh_theme  # type: ignore[attr-defined]
