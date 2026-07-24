"""OCR fallback tests."""

from __future__ import annotations

import io
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw

from app import strings
from engine import ConversionOptions, convert
from engine.ocr import OcrResult, ocr_page


def _image_only_pdf(path: Path) -> Path:
    image = Image.new("RGB", (600, 200), "white")
    ImageDraw.Draw(image).text((30, 70), "SCANNED PAGE", fill="black")
    stream = io.BytesIO()
    image.save(stream, format="PNG")

    document = pymupdf.open()
    page = document.new_page(width=612, height=792)
    page.insert_image(pymupdf.Rect(50, 200, 562, 370), stream=stream.getvalue())
    document.save(path)
    document.close()
    return path


def test_image_only_page_uses_ocr(monkeypatch, tmp_path: Path) -> None:
    source = _image_only_pdf(tmp_path / "scan.pdf")

    monkeypatch.setattr(
        "engine.converter.ocr_page",
        lambda page: OcrResult(text="SCANNED PAGE\nSecond OCR line"),
    )

    result = convert(source, ConversionOptions(include_images=False, output_dir=tmp_path / "out"))

    assert result.error is None
    assert "SCANNED PAGE" in result.markdown
    assert result.used_ocr is True
    assert result.pages[0].used_ocr is True
    assert strings.NOTICE_OCR_USED in result.warnings


def test_ocr_renders_at_300_dpi(monkeypatch, tmp_path: Path) -> None:
    source = _image_only_pdf(tmp_path / "resolution.pdf")
    document = pymupdf.open(source)
    captured_size: list[tuple[int, int]] = []

    monkeypatch.setattr("engine.ocr.resolve_tesseract_binary", lambda: Path("tesseract.exe"))

    def fake_image_to_string(image: Image.Image, lang: str) -> str:
        assert lang == "eng"
        captured_size.append(image.size)
        return "Rasterized text"

    monkeypatch.setattr("engine.ocr.pytesseract.image_to_string", fake_image_to_string)

    result = ocr_page(document[0])
    document.close()

    assert result.text == "Rasterized text"
    assert captured_size == [(2550, 3300)]


def test_missing_tesseract_warns_and_skips(monkeypatch, tmp_path: Path) -> None:
    source = _image_only_pdf(tmp_path / "missing-ocr.pdf")
    monkeypatch.setattr(
        "engine.converter.ocr_page",
        lambda page: OcrResult(text="", unavailable=True),
    )

    result = convert(source, ConversionOptions(include_images=False, output_dir=tmp_path / "out"))

    assert result.error is None
    assert result.used_ocr is False
    assert result.markdown == ""
    assert strings.WARNING_OCR_UNAVAILABLE in result.warnings


def test_ocr_can_be_disabled(monkeypatch, tmp_path: Path) -> None:
    source = _image_only_pdf(tmp_path / "disabled.pdf")

    def unexpected_ocr(page) -> OcrResult:
        raise AssertionError("OCR should not run")

    monkeypatch.setattr("engine.converter.ocr_page", unexpected_ocr)

    result = convert(
        source,
        ConversionOptions(
            include_images=False,
            ocr_enabled=False,
            output_dir=tmp_path / "out",
        ),
    )

    assert result.error is None
    assert result.used_ocr is False

