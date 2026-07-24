"""Paths and icons bundled with the application."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon

ASSET_DIR = Path(__file__).with_name("assets")


def asset_path(*parts: str) -> Path:
    """Return an asset path that works in source, wheel, and PyInstaller builds."""

    return ASSET_DIR.joinpath(*parts)


def icon(name: str) -> QIcon:
    """Load one of Marklift's application-owned icons."""

    return QIcon(str(asset_path("icons", f"{name}.svg")))


def application_icon() -> QIcon:
    """Load the branded application icon."""

    return QIcon(str(asset_path("marklift-icon.png")))
