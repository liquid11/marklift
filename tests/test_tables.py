"""Table and image conversion tests."""

from __future__ import annotations

import io
import re
from pathlib import Path

import pymupdf
import pytest
from PIL import Image

from app import strings
from engine import ConversionOptions, convert, save_conversion_result
from engine.errors import InvalidDestinationError, OutputExistsError
from engine.images import extract_page_images
from engine.tables import extract_page_tables, table_to_gfm


def _table_pdf(path: Path) -> Path:
    document = pymupdf.open()
    page = document.new_page(width=400, height=300)
    left, top, cell_width, cell_height = 50, 70, 140, 40

    for row in range(4):
        y = top + row * cell_height
        page.draw_line((left, y), (left + 2 * cell_width, y))
    for column in range(3):
        x = left + column * cell_width
        page.draw_line((x, top), (x, top + 3 * cell_height))

    values = [["Name", "Score"], ["Ada", "98"], ["Grace", "95"]]
    for row_index, row in enumerate(values):
        for column_index, value in enumerate(row):
            page.insert_text(
                (
                    left + column_index * cell_width + 8,
                    top + row_index * cell_height + 25,
                ),
                value,
                fontsize=11,
            )

    document.save(path)
    document.close()
    return path


def _image_pdf(path: Path) -> Path:
    pixels = Image.new("RGB", (80, 50), color=(32, 112, 196))
    buffer = io.BytesIO()
    pixels.save(buffer, format="PNG")

    document = pymupdf.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((50, 50), "Image fixture")
    page.insert_image(pymupdf.Rect(50, 80, 210, 180), stream=buffer.getvalue())
    document.save(path)
    document.close()
    return path


def test_table_to_gfm_escapes_cells() -> None:
    markdown = table_to_gfm(
        [["Product", "Details"], ["Widget", "A | B"], ["Gadget", "two\nlines"]]
    )

    assert markdown == (
        "| Product | Details |\n"
        "| --- | --- |\n"
        "| Widget | A \\| B |\n"
        "| Gadget | two<br>lines |"
    )


def test_low_confidence_table_is_rejected() -> None:
    assert table_to_gfm([["Name", "Value"], ["", ""], ["", ""]]) is None
    assert table_to_gfm([["Only one row", "No body"]]) is None
    assert table_to_gfm([["A", "B"], ["C"]]) is None


def test_failed_table_is_skipped_without_losing_other_tables() -> None:
    class BrokenTable:
        @staticmethod
        def extract():
            raise RuntimeError("broken table")

    class ValidTable:
        @staticmethod
        def extract():
            return [["Name", "Score"], ["Ada", "98"]]

    class Page:
        @staticmethod
        def find_tables():
            return type("Detected", (), {"tables": [BrokenTable(), ValidTable()]})()

    result = extract_page_tables(Page(), page_number=4)

    assert result.markdown == ["| Name | Score |\n| --- | --- |\n| Ada | 98 |"]
    assert result.warnings == [strings.WARNING_LOW_CONFIDENCE_TABLE.format(page=4)]


def test_detected_table_round_trips_to_gfm(tmp_path: Path) -> None:
    source = _table_pdf(tmp_path / "table.pdf")

    result = convert(source, ConversionOptions(output_dir=tmp_path / "out"))

    assert result.error is None
    assert re.search(r"\|\s*Name\s*\|\s*Score\s*\|", result.markdown)
    assert re.search(r"\|\s*-{3,}\s*\|\s*-{3,}\s*\|", result.markdown)
    assert re.search(r"\|\s*Ada\s*\|\s*98\s*\|", result.markdown)


def test_image_is_extracted_with_working_relative_link(tmp_path: Path) -> None:
    source = _image_pdf(tmp_path / "photo.pdf")
    output_dir = tmp_path / "out"

    result = convert(source, ConversionOptions(output_dir=output_dir))

    assert result.error is None
    match = re.search(r"!\[Image from page 1\]\(([^)]+)\)", result.markdown)
    assert match is not None
    assert (output_dir / Path(match.group(1))).is_file()


def test_include_images_false_skips_assets(tmp_path: Path) -> None:
    source = _image_pdf(tmp_path / "skip.pdf")
    output_dir = tmp_path / "out"

    result = convert(
        source,
        ConversionOptions(include_images=False, output_dir=output_dir),
    )

    assert result.error is None
    assert "![Image from page" not in result.markdown
    assert not (output_dir / "skip_assets").exists()


def test_failed_image_is_skipped_without_losing_other_images(tmp_path: Path) -> None:
    class Page:
        @staticmethod
        def get_images(*, full: bool):
            assert full is True
            return [(101,), (102,)]

    class Document:
        @staticmethod
        def extract_image(xref: int):
            if xref == 101:
                raise RuntimeError("broken image xref")
            return {"ext": "png", "image": b"valid-image"}

    links, files, warnings = extract_page_images(
        Document(),
        Page(),
        page_number=3,
        staging_dir=tmp_path,
        link_directory="document_assets",
    )

    assert links == ["![Image from page 3](document_assets/page-0003-image-02.png)"]
    assert [file.read_bytes() for file in files] == [b"valid-image"]
    assert warnings == [strings.WARNING_IMAGE_SKIPPED.format(page=3)]


def test_failed_image_enumeration_is_skipped(tmp_path: Path) -> None:
    class Page:
        @staticmethod
        def get_images(*, full: bool):
            raise RuntimeError("broken image list")

    links, files, warnings = extract_page_images(
        object(),
        Page(),
        page_number=5,
        staging_dir=tmp_path,
        link_directory="document_assets",
    )

    assert links == []
    assert files == []
    assert warnings == [strings.WARNING_IMAGE_SKIPPED.format(page=5)]


def test_existing_asset_folder_is_not_partially_overwritten(tmp_path: Path) -> None:
    source = _image_pdf(tmp_path / "protected.pdf")
    output_dir = tmp_path / "out"
    assets_dir = output_dir / "protected_assets"
    assets_dir.mkdir(parents=True)
    sentinel = assets_dir / "keep.txt"
    sentinel.write_text("existing asset", encoding="utf-8")

    result = convert(source, ConversionOptions(output_dir=output_dir))

    assert result.error == strings.ERROR_OUTPUT_EXISTS
    assert not (output_dir / "protected.md").exists()
    assert sentinel.read_text(encoding="utf-8") == "existing asset"


def test_explicit_overwrite_replaces_existing_asset_folder(tmp_path: Path) -> None:
    source = _image_pdf(tmp_path / "replace-assets.pdf")
    output_dir = tmp_path / "out"
    assets_dir = output_dir / "replace-assets_assets"
    assets_dir.mkdir(parents=True)
    sentinel = assets_dir / "stale.txt"
    sentinel.write_text("stale asset", encoding="utf-8")

    result = convert(
        source,
        ConversionOptions(output_dir=output_dir, overwrite_existing=True),
    )

    assert result.error is None
    assert not sentinel.exists()
    assert list(assets_dir.glob("page-*.png"))


def test_save_as_renames_asset_links_and_copies_files(tmp_path: Path) -> None:
    source = _image_pdf(tmp_path / "original.pdf")
    result = convert(source, ConversionOptions(output_dir=tmp_path / "preview"))
    destination = tmp_path / "saved" / "renamed.md"

    saved_markdown = save_conversion_result(result, destination)

    assert destination.read_text(encoding="utf-8") == saved_markdown
    assert "(renamed_assets/" in saved_markdown
    match = re.search(r"\((renamed_assets/[^)]+)\)", saved_markdown)
    assert match is not None
    assert (destination.parent / match.group(1)).is_file()


def test_save_result_does_not_replace_existing_output_by_default(tmp_path: Path) -> None:
    source = _image_pdf(tmp_path / "original.pdf")
    result = convert(source, ConversionOptions(output_dir=tmp_path / "preview"))
    destination = tmp_path / "saved" / "renamed.md"
    destination.parent.mkdir()
    destination.write_text("keep markdown\n", encoding="utf-8")

    with pytest.raises(OutputExistsError):
        save_conversion_result(result, destination)

    assert destination.read_text(encoding="utf-8") == "keep markdown\n"
    assert not (destination.parent / "renamed_assets").exists()


def test_save_result_protects_existing_asset_folder(tmp_path: Path) -> None:
    source = _image_pdf(tmp_path / "original.pdf")
    result = convert(source, ConversionOptions(output_dir=tmp_path / "preview"))
    destination = tmp_path / "saved" / "renamed.md"
    target_assets = destination.parent / "renamed_assets"
    target_assets.mkdir(parents=True)
    sentinel = target_assets / "keep.txt"
    sentinel.write_text("keep asset", encoding="utf-8")

    with pytest.raises(OutputExistsError):
        save_conversion_result(result, destination)

    assert not destination.exists()
    assert sentinel.read_text(encoding="utf-8") == "keep asset"


def test_save_result_explicit_overwrite_replaces_markdown_and_assets(tmp_path: Path) -> None:
    source = _image_pdf(tmp_path / "original.pdf")
    result = convert(source, ConversionOptions(output_dir=tmp_path / "preview"))
    destination = tmp_path / "saved" / "renamed.md"
    target_assets = destination.parent / "renamed_assets"
    target_assets.mkdir(parents=True)
    destination.write_text("old markdown\n", encoding="utf-8")
    sentinel = target_assets / "stale.txt"
    sentinel.write_text("stale asset", encoding="utf-8")

    saved_markdown = save_conversion_result(result, destination, overwrite=True)

    assert destination.read_text(encoding="utf-8") == saved_markdown
    assert "(renamed_assets/" in saved_markdown
    assert not sentinel.exists()
    assert list(target_assets.glob("page-*.png"))


def test_save_result_never_replaces_source_pdf(tmp_path: Path) -> None:
    source = _image_pdf(tmp_path / "source.pdf")
    source_bytes = source.read_bytes()
    result = convert(source, ConversionOptions(output_dir=tmp_path / "preview"))

    with pytest.raises(InvalidDestinationError):
        save_conversion_result(result, source, overwrite=True)

    assert source.read_bytes() == source_bytes
