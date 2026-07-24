"""Conversion error tests."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from app import strings
from engine import ConversionOptions, convert
from engine.errors import (
    CancelledError,
    CorruptPdfError,
    EncryptedPdfError,
    InvalidDestinationError,
    InvalidPageRangeError,
    NotPdfError,
    OutputExistsError,
    message_for_exception,
)


def _valid_pdf(path: Path) -> Path:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Hostile fixture source")
    document.save(path)
    document.close()
    return path


def _encrypted_pdf(path: Path) -> Path:
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "Secret")
    document.save(
        path,
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner-password",
        user_pw="user-password",
        permissions=0,
    )
    document.close()
    return path


@pytest.mark.parametrize(
    ("exception", "message"),
    [
        (EncryptedPdfError(), strings.ERROR_ENCRYPTED),
        (NotPdfError(), strings.ERROR_NOT_PDF),
        (CorruptPdfError(), strings.ERROR_CORRUPT),
        (InvalidPageRangeError(), strings.ERROR_PAGE_RANGE),
        (OutputExistsError(), strings.ERROR_OUTPUT_EXISTS),
        (InvalidDestinationError(), strings.ERROR_INVALID_DESTINATION),
        (CancelledError(), strings.ERROR_CANCELLED),
    ],
)
def test_typed_errors_map_to_plain_language(exception: Exception, message: str) -> None:
    assert message_for_exception(exception) == message


def test_zero_byte_pdf_is_reported_as_corrupt(tmp_path: Path) -> None:
    source = tmp_path / "empty.pdf"
    source.write_bytes(b"")

    result = convert(source)

    assert result.error == strings.ERROR_CORRUPT


def test_wrong_extension_is_not_a_pdf(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("not a PDF", encoding="utf-8")

    result = convert(source)

    assert result.error == strings.ERROR_NOT_PDF


def test_text_renamed_to_pdf_is_not_a_pdf(tmp_path: Path) -> None:
    source = tmp_path / "pretend.pdf"
    source.write_text("plain text with a misleading extension", encoding="utf-8")

    result = convert(source)

    assert result.error == strings.ERROR_NOT_PDF


def test_encrypted_pdf_has_specific_message(tmp_path: Path) -> None:
    result = convert(_encrypted_pdf(tmp_path / "encrypted.pdf"))

    assert result.error == strings.ERROR_ENCRYPTED
    assert "enter the password" not in result.error.lower()
    assert result.markdown == ""
    assert result.output_path is None


def test_existing_markdown_is_not_overwritten_by_default(tmp_path: Path) -> None:
    source = _valid_pdf(tmp_path / "existing.pdf")
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    output = output_dir / "existing.md"
    output.write_text("keep this content\n", encoding="utf-8")

    result = convert(source, ConversionOptions(output_dir=output_dir))

    assert result.error == strings.ERROR_OUTPUT_EXISTS
    assert result.output_path is None
    assert output.read_text(encoding="utf-8") == "keep this content\n"


def test_existing_markdown_can_be_explicitly_replaced(tmp_path: Path) -> None:
    source = _valid_pdf(tmp_path / "replace.pdf")
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    output = output_dir / "replace.md"
    output.write_text("old content\n", encoding="utf-8")

    result = convert(
        source,
        ConversionOptions(output_dir=output_dir, overwrite_existing=True),
    )

    assert result.error is None
    assert result.output_path == output
    assert output.read_text(encoding="utf-8") == result.markdown
    assert output.read_text(encoding="utf-8") != "old content\n"


def test_truncated_pdf_never_raises(tmp_path: Path) -> None:
    valid = _valid_pdf(tmp_path / "valid.pdf")
    truncated = tmp_path / "truncated.pdf"
    content = valid.read_bytes()
    truncated.write_bytes(content[: len(content) // 2])

    result = convert(truncated, ConversionOptions(output_dir=tmp_path / "out"))

    assert result.error == strings.ERROR_CORRUPT
    assert result.markdown == ""
    assert result.output_path is None


def test_missing_file_never_raises(tmp_path: Path) -> None:
    result = convert(tmp_path / "missing.pdf")

    assert result.error == strings.ERROR_CORRUPT
    assert result.output_path is None
