"""Conversion engine tests."""

from __future__ import annotations

from pathlib import Path
from threading import Event

import pymupdf
import pytest

from app import strings
from engine import ConversionOptions, convert


def _new_pdf(path: Path, pages: list[list[tuple[str, float]]]) -> Path:
    document = pymupdf.open()
    for page_lines in pages:
        page = document.new_page()
        y = 72
        for text, size in page_lines:
            page.insert_text((72, y), text, fontsize=size)
            y += size + 30
    document.save(path)
    document.close()
    return path


@pytest.fixture
def simple_text_pdf(tmp_path: Path) -> Path:
    return _new_pdf(
        tmp_path / "simple-text.pdf",
        [[("Simple Document", 24), ("A short paragraph for conversion.", 11)]],
    )


@pytest.fixture
def multi_heading_pdf(tmp_path: Path) -> Path:
    return _new_pdf(
        tmp_path / "headings.pdf",
        [
            [
                ("Main Heading", 24),
                ("Section Heading", 18),
                ("Section text with enough body copy to establish the base font.", 11),
            ]
        ],
    )


@pytest.fixture
def list_pdf(tmp_path: Path) -> Path:
    return _new_pdf(
        tmp_path / "list.pdf",
        [[("Shopping List", 24), ("- Apples", 11), ("- Bananas", 11)]],
    )


def test_simple_text_is_converted(simple_text_pdf: Path, tmp_path: Path) -> None:
    result = convert(simple_text_pdf, ConversionOptions(output_dir=tmp_path / "out"))

    assert result.error is None
    assert "# Simple Document" in result.markdown
    assert "A short paragraph for conversion." in result.markdown
    assert result.output_path is not None
    assert result.output_path.read_text(encoding="utf-8") == result.markdown


def test_heading_structure_is_preserved(multi_heading_pdf: Path, tmp_path: Path) -> None:
    result = convert(multi_heading_pdf, ConversionOptions(output_dir=tmp_path))

    assert "# Main Heading" in result.markdown
    assert "## Section Heading" in result.markdown
    assert "Section text with enough body copy" in result.markdown


def test_bullet_list_is_markdown(list_pdf: Path, tmp_path: Path) -> None:
    result = convert(list_pdf, ConversionOptions(output_dir=tmp_path))

    assert "-  Apples" in result.markdown or "- Apples" in result.markdown
    assert "Bananas" in result.markdown


def test_page_range_is_one_based_and_inclusive(tmp_path: Path) -> None:
    source = _new_pdf(
        tmp_path / "pages.pdf",
        [[("First page", 11)], [("Second page", 11)], [("Third page", 11)]],
    )

    result = convert(source, ConversionOptions(page_range=(2, 2), output_dir=tmp_path / "out"))

    assert result.error is None
    assert "Second page" in result.markdown
    assert "First page" not in result.markdown
    assert "Third page" not in result.markdown


def test_cancellation_discards_partial_output(tmp_path: Path) -> None:
    source = _new_pdf(
        tmp_path / "cancel.pdf",
        [[("Page one", 11)], [("Page two", 11)], [("Page three", 11)]],
    )
    cancel = Event()

    def cancel_after_first(completed: int, total: int) -> None:
        assert total == 3
        if completed == 1:
            cancel.set()

    result = convert(
        source,
        ConversionOptions(
            output_dir=tmp_path / "out",
            cancel_event=cancel,
            progress_callback=cancel_after_first,
        ),
    )

    assert result.error == strings.ERROR_CANCELLED
    assert result.markdown == ""
    assert result.output_path is None
    assert not (tmp_path / "out" / "cancel.md").exists()


def test_invalid_page_range_returns_result(simple_text_pdf: Path) -> None:
    result = convert(simple_text_pdf, ConversionOptions(page_range=(2, 4)))

    assert result.error is not None
    assert result.output_path is None


def test_output_is_deterministic(simple_text_pdf: Path, tmp_path: Path) -> None:
    first = convert(simple_text_pdf, ConversionOptions(output_dir=tmp_path / "first"))
    second = convert(simple_text_pdf, ConversionOptions(output_dir=tmp_path / "second"))

    assert first.markdown == second.markdown
