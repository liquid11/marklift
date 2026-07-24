"""Build the Windows one-folder application with its offline OCR runtime."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENTRY_POINT = PROJECT_ROOT / "src" / "app" / "main.py"
INSTALLER_SCRIPT = PROJECT_ROOT / "src" / "packaging" / "installer.iss"
VENDOR_TESSERACT = PROJECT_ROOT / "vendor" / "tesseract"
APP_ASSETS = PROJECT_ROOT / "src" / "app" / "assets"
APP_ICON_PNG = APP_ASSETS / "marklift-icon.png"
APP_ICON_ICO = APP_ASSETS / "marklift-icon.ico"
APP_NAME = "Marklift"


def validate_configuration() -> None:
    required = [
        ENTRY_POINT,
        INSTALLER_SCRIPT,
        PROJECT_ROOT / "pyproject.toml",
        APP_ICON_PNG,
        APP_ICON_ICO,
    ]
    missing = [path for path in required if not path.is_file()]
    if missing:
        joined = ", ".join(str(path) for path in missing)
        raise SystemExit(f"Packaging configuration is incomplete: {joined}")


def _tesseract_sources() -> list[Path]:
    candidates: list[Path] = []
    configured = os.environ.get("TESSERACT_ROOT")
    if configured:
        candidates.append(Path(configured))
    candidates.extend(
        [
            Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Tesseract-OCR",
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
            / "Tesseract-OCR",
        ]
    )
    return candidates


def prepare_tesseract_bundle() -> None:
    """Copy only the English runtime into the reproducible vendor directory."""

    executable = VENDOR_TESSERACT / "tesseract.exe"
    english_data = VENDOR_TESSERACT / "tessdata" / "eng.traineddata"
    if executable.is_file() and english_data.is_file():
        return

    source = next(
        (
            candidate
            for candidate in _tesseract_sources()
            if (candidate / "tesseract.exe").is_file()
            and (candidate / "tessdata" / "eng.traineddata").is_file()
        ),
        None,
    )
    if source is None:
        raise SystemExit(
            "Tesseract wasn't found. Install the English Windows build or set "
            "TESSERACT_ROOT before packaging."
        )

    VENDOR_TESSERACT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "tesseract.exe", executable)
    for library in sorted(source.glob("*.dll")):
        shutil.copy2(library, VENDOR_TESSERACT / library.name)
    english_data.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "tessdata" / "eng.traineddata", english_data)


def _pyinstaller_command() -> list[str]:
    tesseract_data = f"{VENDOR_TESSERACT}{os.pathsep}vendor/tesseract"
    application_assets = f"{APP_ASSETS}{os.pathsep}app/assets"
    return [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--noupx",
        "--name",
        APP_NAME,
        "--icon",
        str(APP_ICON_ICO),
        "--paths",
        str(PROJECT_ROOT / "src"),
        "--collect-all",
        "pymupdf4llm",
        "--add-data",
        tesseract_data,
        "--add-data",
        application_assets,
        "--exclude-module",
        "tkinter",
        "--exclude-module",
        "pymupdf_layout",
        str(ENTRY_POINT),
    ]


def build() -> int:
    validate_configuration()
    if platform.system() != "Windows":
        print("Packaging configuration is valid; skipping the Windows-only build.")
        return 0

    prepare_tesseract_bundle()
    build_environment = os.environ.copy()
    build_environment.pop("PYTHONPATH", None)
    subprocess.run(
        _pyinstaller_command(),
        cwd=PROJECT_ROOT,
        check=True,
        env=build_environment,
    )

    application = PROJECT_ROOT / "dist" / APP_NAME / f"{APP_NAME}.exe"
    bundled_tesseract = list((PROJECT_ROOT / "dist" / APP_NAME).rglob("tesseract.exe"))
    bundled_english = list((PROJECT_ROOT / "dist" / APP_NAME).rglob("eng.traineddata"))
    bundled_icon = list((PROJECT_ROOT / "dist" / APP_NAME).rglob(APP_ICON_PNG.name))
    if (
        not application.is_file()
        or not bundled_tesseract
        or not bundled_english
        or not bundled_icon
    ):
        raise SystemExit("PyInstaller completed, but the offline runtime is incomplete.")

    print(f"Built {application}")
    print(f"Bundled OCR runtime: {bundled_tesseract[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
