"""Build the Windows one-folder application with its offline OCR runtime."""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENTRY_POINT = PROJECT_ROOT / "src" / "app" / "main.py"
INSTALLER_SCRIPT = PROJECT_ROOT / "src" / "packaging" / "installer.iss"
VENDOR_TESSERACT = PROJECT_ROOT / "vendor" / "tesseract"
APP_ASSETS = PROJECT_ROOT / "src" / "app" / "assets"
APP_ICON_PNG = APP_ASSETS / "marklift-icon.png"
APP_ICON_ICO = APP_ASSETS / "marklift-icon.ico"
APP_NAME = "Marklift"
VERSION_INFO_FILE = PROJECT_ROOT / "build" / "marklift-version-info.txt"
ACTION_ICONS = (
    "add-files.svg",
    "add-folder.svg",
    "cancel.svg",
    "copy.svg",
    "save-all.svg",
    "save-as.svg",
    "save.svg",
)


def project_version() -> str:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as handle:
        version = tomllib.load(handle)["project"]["version"]
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit("The project version must use numeric major.minor.patch format.")
    return version


def validate_configuration() -> str:
    required = [
        ENTRY_POINT,
        INSTALLER_SCRIPT,
        PROJECT_ROOT / "pyproject.toml",
        APP_ICON_PNG,
        APP_ICON_ICO,
        *(APP_ASSETS / "icons" / name for name in ACTION_ICONS),
    ]
    missing = [path for path in required if not path.is_file()]
    if missing:
        joined = ", ".join(str(path) for path in missing)
        raise SystemExit(f"Packaging configuration is incomplete: {joined}")

    version = project_version()
    installer_text = INSTALLER_SCRIPT.read_text(encoding="utf-8")
    installer_match = re.search(r'^#define MyAppVersion "([^"]+)"', installer_text, re.MULTILINE)
    installer_version = installer_match.group(1) if installer_match else None
    if installer_version != version:
        raise SystemExit(
            "Version mismatch: pyproject.toml uses "
            f"{version}, but installer.iss uses {installer_version or 'no version'}."
        )
    return version


def write_version_info(version: str) -> Path:
    """Create deterministic Windows version metadata for the packaged executable."""

    major, minor, patch = (int(part) for part in version.split("."))
    VERSION_INFO_FILE.parent.mkdir(parents=True, exist_ok=True)
    VERSION_INFO_FILE.write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, 0),
    prodvers=({major}, {minor}, {patch}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0),
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'Marklift'),
          StringStruct('FileDescription', 'Marklift'),
          StringStruct('FileVersion', '{version}'),
          StringStruct('InternalName', 'Marklift'),
          StringStruct('OriginalFilename', 'Marklift.exe'),
          StringStruct('ProductName', 'Marklift'),
          StringStruct('ProductVersion', '{version}'),
        ],
      ),
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])]),
  ],
)
""",
        encoding="utf-8",
        newline="\n",
    )
    return VERSION_INFO_FILE


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


def _pyinstaller_command(version_info_file: Path) -> list[str]:
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
        "--version-file",
        str(version_info_file),
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
    version = validate_configuration()
    if platform.system() != "Windows":
        print("Packaging configuration is valid; skipping the Windows-only build.")
        return 0

    prepare_tesseract_bundle()
    version_info_file = write_version_info(version)
    build_environment = os.environ.copy()
    build_environment.pop("PYTHONPATH", None)
    subprocess.run(
        _pyinstaller_command(version_info_file),
        cwd=PROJECT_ROOT,
        check=True,
        env=build_environment,
    )

    application = PROJECT_ROOT / "dist" / APP_NAME / f"{APP_NAME}.exe"
    bundled_tesseract = list((PROJECT_ROOT / "dist" / APP_NAME).rglob("tesseract.exe"))
    bundled_english = list((PROJECT_ROOT / "dist" / APP_NAME).rglob("eng.traineddata"))
    bundled_icon = list((PROJECT_ROOT / "dist" / APP_NAME).rglob(APP_ICON_PNG.name))
    bundled_action_icons = [
        PROJECT_ROOT / "dist" / APP_NAME / "_internal" / "app" / "assets" / "icons" / name
        for name in ACTION_ICONS
    ]
    if (
        not application.is_file()
        or not bundled_tesseract
        or not bundled_english
        or not bundled_icon
        or not all(path.is_file() for path in bundled_action_icons)
    ):
        raise SystemExit("PyInstaller completed, but the offline runtime is incomplete.")

    print(f"Built {application}")
    print(f"Bundled OCR runtime: {bundled_tesseract[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
