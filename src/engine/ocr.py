"""OCR fallback for image-only PDF pages."""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytesseract
from PIL import Image


@dataclass(slots=True)
class OcrResult:
    text: str
    unavailable: bool = False


def _bundled_tesseract_candidates() -> list[Path]:
    candidates: list[Path] = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        candidates.append(Path(bundle_root) / "vendor" / "tesseract" / "tesseract.exe")
    if getattr(sys, "frozen", False):
        executable_root = Path(sys.executable).resolve().parent
        candidates.append(executable_root / "vendor" / "tesseract" / "tesseract.exe")
    project_root = Path(__file__).resolve().parents[2]
    candidates.append(project_root / "vendor" / "tesseract" / "tesseract.exe")
    return candidates


def resolve_tesseract_binary() -> Path | None:
    """Prefer the packaged binary, then allow a developer PATH installation."""

    for candidate in _bundled_tesseract_candidates():
        if candidate.is_file():
            return candidate
    path_binary = shutil.which("tesseract")
    return Path(path_binary) if path_binary else None


def ocr_page(page: Any) -> OcrResult:
    """Rasterize one page at 300 DPI and read its English text locally."""

    binary = resolve_tesseract_binary()
    if binary is None:
        return OcrResult(text="", unavailable=True)

    try:
        pixmap = page.get_pixmap(dpi=300, alpha=False)
        image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
        pytesseract.pytesseract.tesseract_cmd = str(binary)
        text = pytesseract.image_to_string(image, lang="eng")
        return OcrResult(text=text.strip())
    except (OSError, RuntimeError, pytesseract.TesseractError, pytesseract.TesseractNotFoundError):
        return OcrResult(text="", unavailable=True)
