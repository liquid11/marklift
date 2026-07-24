"""Data models shared by the conversion engine."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event


@dataclass(slots=True)
class PageStatus:
    """Diagnostic status for a single processed page."""

    page_number: int
    used_ocr: bool = False
    warning: str | None = None


@dataclass(slots=True)
class ConversionOptions:
    """Options accepted by :func:`engine.converter.convert`.

    ``page_range`` uses one-based, inclusive page numbers because that is what
    users see in a PDF reader.
    """

    include_images: bool = True
    page_range: tuple[int, int] | None = None
    ocr_enabled: bool = True
    output_dir: Path | None = None
    overwrite_existing: bool = False
    cancel_event: Event = field(default_factory=Event, repr=False, compare=False)
    progress_callback: Callable[[int, int], None] | None = field(
        default=None, repr=False, compare=False
    )


@dataclass(slots=True)
class ConversionResult:
    """Complete, partial-free result returned for both success and failure."""

    source: Path
    output_path: Path | None
    markdown: str
    used_ocr: bool
    warnings: list[str]
    error: str | None
    pages: list[PageStatus] = field(default_factory=list)
