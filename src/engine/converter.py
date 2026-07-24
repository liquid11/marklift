"""PDF-to-Markdown conversion orchestration."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from builtins import __import__ as _builtin_import
from pathlib import Path
from threading import Lock
from types import ModuleType

import pymupdf

from app import strings
from engine.errors import (
    CancelledError,
    ConversionError,
    CorruptPdfError,
    EncryptedPdfError,
    InvalidDestinationError,
    InvalidPageRangeError,
    OutputExistsError,
    message_for_exception,
    validate_pdf_file,
)
from engine.images import extract_page_images
from engine.models import ConversionOptions, ConversionResult, PageStatus
from engine.ocr import ocr_page
from engine.tables import extract_page_tables

_markdown_engine: ModuleType | None = None
_markdown_engine_lock = Lock()


def _load_markdown_engine() -> ModuleType:
    """Load pymupdf4llm without activating its non-streaming layout model."""

    global _markdown_engine
    if _markdown_engine is not None:
        return _markdown_engine

    with _markdown_engine_lock:
        if _markdown_engine is not None:
            return _markdown_engine

        import builtins

        def import_without_layout(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "pymupdf.layout":
                raise ImportError("The optional layout backend is intentionally disabled.")
            return _builtin_import(name, globals, locals, fromlist, level)

        original_import = builtins.__import__
        builtins.__import__ = import_without_layout
        try:
            markdown_engine = _builtin_import("pymupdf4llm")
        finally:
            builtins.__import__ = original_import

        # Cache only after configuration succeeds so a transient initialization
        # failure cannot poison later conversion attempts.
        markdown_engine.use_layout(False)
        _markdown_engine = markdown_engine
        return markdown_engine


def _failed(source: Path, message: str) -> ConversionResult:
    return ConversionResult(
        source=source,
        output_path=None,
        markdown="",
        used_ocr=False,
        warnings=[],
        error=message,
    )


def _page_indexes(page_count: int, page_range: tuple[int, int] | None) -> range:
    if page_range is None:
        return range(page_count)

    start, end = page_range
    if start < 1 or end < start or end > page_count:
        raise InvalidPageRangeError
    return range(start - 1, end)


def _normalise_markdown(markdown: str) -> str:
    """Return stable line endings and whitespace without changing structure."""

    unified = markdown.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in unified.split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + ("\n" if lines else "")


def _write_atomically(
    output_path: Path,
    markdown: str,
    *,
    overwrite: bool = True,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not overwrite:
        try:
            handle = output_path.open("x", encoding="utf-8", newline="\n")
        except FileExistsError as exc:
            raise OutputExistsError from exc
        try:
            with handle:
                handle.write(markdown)
        except Exception:
            output_path.unlink(missing_ok=True)
            raise
        return

    descriptor, temporary_name = tempfile.mkstemp(
        dir=output_path.parent,
        prefix=f".{output_path.stem}-",
        suffix=".tmp",
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(markdown)
        temporary_path.replace(output_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _contains_gfm_table(markdown: str) -> bool:
    return any(re.match(r"^\|\s*:?-{3,}", line) for line in markdown.splitlines())


def _publish_assets(
    staging_dir: Path,
    assets_dir: Path,
    *,
    overwrite: bool,
) -> Path | None:
    """Publish a complete staged asset directory and return any backup path."""

    backup_dir: Path | None = None
    if assets_dir.exists():
        if not overwrite:
            raise OutputExistsError
        backup_name = tempfile.mkdtemp(
            dir=assets_dir.parent,
            prefix=f".{assets_dir.name}-backup-",
        )
        backup_dir = Path(backup_name)
        backup_dir.rmdir()
        assets_dir.replace(backup_dir)

    try:
        staging_dir.replace(assets_dir)
    except Exception:
        if backup_dir is not None and backup_dir.exists():
            backup_dir.replace(assets_dir)
        raise
    return backup_dir


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.exists():
        shutil.rmtree(path, ignore_errors=True)


def _restore_assets(assets_dir: Path, backup_dir: Path | None) -> None:
    """Remove a failed publication and restore the previous asset directory."""

    _remove_path(assets_dir)
    if backup_dir is not None and backup_dir.exists():
        backup_dir.replace(assets_dir)


def render_page_thumbnail(
    path: str | Path,
    page_number: int = 1,
    max_width: int = 480,
) -> bytes | None:
    """Render a source-page PNG for the UI without exposing PyMuPDF there."""

    document = None
    try:
        source = Path(path)
        validate_pdf_file(source)
        document = pymupdf.open(source)
        if document.needs_pass or document.is_repaired:
            return None
        if page_number < 1 or page_number > document.page_count:
            return None
        page = document.load_page(page_number - 1)
        scale = min(max_width / page.rect.width, 2.0)
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
        return pixmap.tobytes("png")
    except Exception:
        return None
    finally:
        if document is not None:
            document.close()


def save_conversion_result(
    result: ConversionResult,
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> str:
    """Save a preview result and copy its staged image assets.

    The desktop UI obtains confirmation before opting into replacement.
    """

    target = Path(destination)
    if target.resolve() == result.source.resolve():
        raise InvalidDestinationError
    markdown = result.markdown
    source_assets_name = f"{result.source.stem}_assets"
    target_assets_name = f"{target.stem}_assets"
    if source_assets_name != target_assets_name:
        markdown = markdown.replace(
            f"({source_assets_name}/",
            f"({target_assets_name}/",
        )

    source_assets: Path | None = None
    if result.output_path is not None:
        candidate = result.output_path.parent / source_assets_name
        if candidate.is_dir():
            source_assets = candidate
    target_assets = target.parent / target_assets_name

    if not overwrite and (
        target.exists() or (source_assets is not None and target_assets.exists())
    ):
        raise OutputExistsError

    assets_backup: Path | None = None
    assets_published = False
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        if source_assets is not None:
            with tempfile.TemporaryDirectory(
                dir=target.parent,
                prefix=f".{target.stem}-save-assets-",
            ) as staging_name:
                staged_assets = Path(staging_name) / target_assets_name
                shutil.copytree(source_assets, staged_assets)
                assets_backup = _publish_assets(
                    staged_assets,
                    target_assets,
                    overwrite=overwrite,
                )
                assets_published = True
        _write_atomically(target, markdown, overwrite=overwrite)
    except Exception:
        if assets_published:
            _restore_assets(target_assets, assets_backup)
        raise
    if assets_backup is not None:
        _remove_path(assets_backup)
    return markdown


def convert(
    path: str | Path,
    options: ConversionOptions | None = None,
) -> ConversionResult:
    """Convert a PDF page-by-page and return failures instead of raising."""

    source = Path(path)
    options = options or ConversionOptions()

    try:
        validate_pdf_file(source)
        output_dir = Path(options.output_dir or source.parent)
        output_path = output_dir / f"{source.stem}.md"
        if output_path.exists() and not options.overwrite_existing:
            raise OutputExistsError
        output_dir.mkdir(parents=True, exist_ok=True)
        markdown_engine = _load_markdown_engine()
        assets_name = f"{source.stem}_assets"
        assets_dir = output_dir / assets_name

        try:
            document = pymupdf.open(source)
        except (pymupdf.EmptyFileError, pymupdf.FileDataError, RuntimeError) as exc:
            raise CorruptPdfError from exc

        try:
            if document.needs_pass:
                raise EncryptedPdfError
            if document.is_repaired:
                raise CorruptPdfError

            indexes = _page_indexes(document.page_count, options.page_range)
            total = len(indexes)
            chunks: list[str] = []
            page_statuses: list[PageStatus] = []
            warnings: list[str] = []
            staged_images: list[Path] = []
            used_ocr = False

            with tempfile.TemporaryDirectory(
                dir=output_dir,
                prefix=f".{source.stem}-assets-",
            ) as staging_name:
                staging_dir = Path(staging_name)

                for completed, page_index in enumerate(indexes):
                    if options.cancel_event.is_set():
                        raise CancelledError

                    page = document.load_page(page_index)
                    page_used_ocr = False
                    if options.ocr_enabled and not page.get_text().strip():
                        ocr_result = ocr_page(page)
                        if ocr_result.unavailable:
                            if strings.WARNING_OCR_UNAVAILABLE not in warnings:
                                warnings.append(strings.WARNING_OCR_UNAVAILABLE)
                            page_markdown = ""
                        else:
                            page_markdown = ocr_result.text
                            page_used_ocr = True
                            used_ocr = True
                            if strings.NOTICE_OCR_USED not in warnings:
                                warnings.append(strings.NOTICE_OCR_USED)
                    else:
                        page_markdown = markdown_engine.to_markdown(
                            document,
                            pages=[page_index],
                            show_progress=False,
                            write_images=False,
                        )
                    page_markdown = _normalise_markdown(page_markdown)

                    page_tables = extract_page_tables(page, page_index + 1)
                    warnings.extend(page_tables.warnings)
                    if page_tables.markdown and not _contains_gfm_table(page_markdown):
                        page_markdown = _normalise_markdown(
                            "\n".join([page_markdown, *page_tables.markdown])
                        )

                    if options.include_images:
                        image_links, image_files, image_warnings = extract_page_images(
                            document,
                            page,
                            page_index + 1,
                            staging_dir,
                            assets_name,
                        )
                        staged_images.extend(image_files)
                        warnings.extend(image_warnings)
                        if image_links:
                            page_markdown = _normalise_markdown(
                                "\n".join([page_markdown, *image_links])
                            )

                    chunks.append(page_markdown)
                    page_statuses.append(
                        PageStatus(page_number=page_index + 1, used_ocr=page_used_ocr)
                    )

                    if options.progress_callback is not None:
                        options.progress_callback(completed + 1, total)

                if options.cancel_event.is_set():
                    raise CancelledError

                markdown = _normalise_markdown("\n".join(chunks))
                assets_backup: Path | None = None
                assets_published = False
                try:
                    if staged_images:
                        assets_backup = _publish_assets(
                            staging_dir,
                            assets_dir,
                            overwrite=options.overwrite_existing,
                        )
                        assets_published = True
                    _write_atomically(
                        output_path,
                        markdown,
                        overwrite=options.overwrite_existing,
                    )
                except Exception:
                    if assets_published:
                        _restore_assets(assets_dir, assets_backup)
                    raise
                if assets_backup is not None:
                    _remove_path(assets_backup)
                return ConversionResult(
                    source=source,
                    output_path=output_path,
                    markdown=markdown,
                    used_ocr=used_ocr,
                    warnings=warnings,
                    error=None,
                    pages=page_statuses,
                )
        finally:
            document.close()
    except ConversionError as exc:
        return _failed(source, message_for_exception(exc))
    except (pymupdf.EmptyFileError, pymupdf.FileDataError, RuntimeError):
        return _failed(source, strings.ERROR_CORRUPT)
    except Exception:
        return _failed(source, strings.ERROR_UNKNOWN)
