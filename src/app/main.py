"""Desktop application entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app import strings
from app.main_window import MainWindow
from app.resources import application_icon
from app.theme import bind_system_theme


def main() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName(strings.APP_NAME)
    application.setApplicationDisplayName(strings.APP_NAME)
    application.setWindowIcon(application_icon())
    bind_system_theme(application)
    window = MainWindow()
    window.show()
    window.raise_()
    window.activateWindow()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
