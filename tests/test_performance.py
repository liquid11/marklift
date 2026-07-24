"""Opt-in non-blocking performance target."""

from __future__ import annotations

import time
import warnings
from pathlib import Path

import pymupdf
import pytest

from engine import ConversionOptions, convert


@pytest.mark.performance
def test_100_page_text_conversion_target(tmp_path: Path) -> None:
    source = tmp_path / "one-hundred-pages.pdf"
    document = pymupdf.open()
    for page_number in range(1, 101):
        page = document.new_page()
        page.insert_text((72, 72), f"Page {page_number}")
        page.insert_text((72, 100), "A short performance fixture paragraph.")
    document.save(source)
    document.close()

    started = time.perf_counter()
    result = convert(
        source,
        ConversionOptions(
            include_images=False,
            ocr_enabled=False,
            output_dir=tmp_path / "out",
        ),
    )
    elapsed = time.perf_counter() - started

    assert result.error is None
    assert "Page 100" in result.markdown
    if elapsed >= 30:
        warnings.warn(
            f"100-page conversion took {elapsed:.2f}s; the product target is under 30s.",
            stacklevel=1,
        )
