"""Desktop application entry point."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app import strings
from app.main_window import MainWindow
from app.theme import bind_system_theme


def main() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName(strings.APP_NAME)
    application.setApplicationDisplayName(strings.APP_NAME)
    icon_path = Path(__file__).with_name("assets") / "marklift-icon.png"
    application.setWindowIcon(QIcon(str(icon_path)))
    bind_system_theme(application)
    window = MainWindow()
    window.show()
    window.raise_()
    window.activateWindow()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
