"""Typed conversion errors and plain-language error mapping."""

from __future__ import annotations

from pathlib import Path

from app import strings


class ConversionError(Exception):
    """Base class for failures safe to present in plain language."""


class NotPdfError(ConversionError):
    """The selected file is not a PDF."""


class CorruptPdfError(ConversionError):
    """The selected PDF cannot be parsed safely."""


class EncryptedPdfError(ConversionError):
    """The PDF requires a password."""


class InvalidPageRangeError(ConversionError):
    """The requested one-based page range does not exist."""


class OutputExistsError(ConversionError):
    """The requested Markdown output path already exists."""


class InvalidDestinationError(ConversionError):
    """The Markdown destination is the source PDF itself."""


class CancelledError(ConversionError):
    """Conversion was cancelled by the caller."""


def validate_pdf_file(path: Path) -> None:
    """Perform deterministic checks before handing input to the PDF parser."""

    if path.suffix.lower() != ".pdf":
        raise NotPdfError

    try:
        with path.open("rb") as handle:
            signature = handle.read(5)
    except OSError as exc:
        raise CorruptPdfError from exc

    if not signature:
        raise CorruptPdfError
    if signature != b"%PDF-":
        raise NotPdfError


def message_for_exception(exception: BaseException) -> str:
    """Map internal exception types to approved user-facing copy."""

    if isinstance(exception, EncryptedPdfError):
        return strings.ERROR_ENCRYPTED
    if isinstance(exception, NotPdfError):
        return strings.ERROR_NOT_PDF
    if isinstance(exception, InvalidPageRangeError):
        return strings.ERROR_PAGE_RANGE
    if isinstance(exception, OutputExistsError):
        return strings.ERROR_OUTPUT_EXISTS
    if isinstance(exception, InvalidDestinationError):
        return strings.ERROR_INVALID_DESTINATION
    if isinstance(exception, CancelledError):
        return strings.ERROR_CANCELLED
    if isinstance(exception, CorruptPdfError):
        return strings.ERROR_CORRUPT
    return strings.ERROR_UNKNOWN
