"""Headless launch and batch-continuation smoke tests."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pymupdf

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QCloseEvent, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QFileDialog, QHeaderView, QPushButton

import app.main_window as main_window_module
from app import strings
from app.main_window import MainWindow, QueueJob, SourcePreview
from engine import ConversionResult

_APPLICATION = QApplication.instance() or QApplication([])


def _valid_pdf(path: Path) -> Path:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "UI end-to-end conversion")
    document.save(path)
    document.close()
    return path


def _wait_for_queue(application: QApplication, window: MainWindow, timeout: float = 15) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        application.processEvents()
        states = window.job_states().values()
        if states and all(
            state == strings.STATUS_DONE
            or state == strings.STATUS_CANCELLED
            or state.startswith("Failed:")
            for state in states
        ):
            return
        time.sleep(0.01)
    raise AssertionError(f"Queue did not finish: {window.job_states()}")


def test_window_launches_and_queue_continues_after_failure(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    valid = _valid_pdf(tmp_path / "valid.pdf")
    corrupt = tmp_path / "corrupt.pdf"
    corrupt.write_bytes(b"%PDF-damaged")
    window = MainWindow()

    window.enqueue_paths([corrupt, valid])
    _wait_for_queue(application, window)

    states = window.job_states()
    assert states["corrupt.pdf"].startswith("Failed:")
    assert states["valid.pdf"] == strings.STATUS_DONE
    window.close()


def test_folder_enqueue_only_adds_pdfs(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    _valid_pdf(tmp_path / "one.pdf")
    _valid_pdf(tmp_path / "two.PDF")
    (tmp_path / "notes.txt").write_text("ignore me", encoding="utf-8")
    window = MainWindow()

    window.enqueue_paths([tmp_path])
    _wait_for_queue(application, window)

    assert set(window.job_states()) == {"one.pdf", "two.PDF"}
    assert all(state == strings.STATUS_DONE for state in window.job_states().values())
    window.close()


def test_save_as_then_save_preserves_original_result_and_assets(tmp_path: Path) -> None:
    _application = QApplication.instance() or QApplication([])
    source = tmp_path / "original.pdf"
    source.write_bytes(b"%PDF-fixture")
    preview_dir = tmp_path / "preview"
    preview_assets = preview_dir / "original_assets"
    preview_assets.mkdir(parents=True)
    (preview_assets / "image.png").write_bytes(b"image")
    preview_output = preview_dir / "original.md"
    original_markdown = "![Image from page 1](original_assets/image.png)\n"
    preview_output.write_text(original_markdown, encoding="utf-8")
    result = ConversionResult(
        source=source,
        output_path=preview_output,
        markdown=original_markdown,
        used_ocr=False,
        warnings=[],
        error=None,
    )
    window = MainWindow()
    renamed = tmp_path / "saved" / "renamed.md"
    default = source.with_suffix(".md")

    window._save_to(result, renamed)
    window._save_to(result, default)

    assert result.markdown == original_markdown
    assert result.output_path == preview_output
    assert "(renamed_assets/image.png)" in renamed.read_text(encoding="utf-8")
    assert (renamed.parent / "renamed_assets" / "image.png").is_file()
    assert "(original_assets/image.png)" in default.read_text(encoding="utf-8")
    assert (default.parent / "original_assets" / "image.png").is_file()
    window.close()


def test_close_does_not_cleanup_preview_while_worker_is_active(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _application = QApplication.instance() or QApplication([])
    window = MainWindow()
    window._preview_temp.cleanup()

    class ActivePool:
        @staticmethod
        def waitForDone(milliseconds: int) -> bool:
            assert milliseconds == 5000
            return False

    class PreviewTemp:
        name = str(tmp_path)
        cleaned = False

        def cleanup(self) -> None:
            self.cleaned = True

    preview_temp = PreviewTemp()
    window._preview_temp = preview_temp
    monkeypatch.setattr(MainWindow, "thread_pool", property(lambda self: ActivePool()))

    window.closeEvent(QCloseEvent())

    assert preview_temp.cleaned is False


def test_successful_job_displays_conversion_warnings(tmp_path: Path) -> None:
    _application = QApplication.instance() or QApplication([])
    source = _valid_pdf(tmp_path / "warning.pdf")
    warning = strings.WARNING_IMAGE_SKIPPED.format(page=1)
    result = ConversionResult(
        source=source,
        output_path=tmp_path / "preview" / "warning.md",
        markdown="# Converted\n",
        used_ocr=False,
        warnings=[warning],
        error=None,
    )
    window = MainWindow()
    job = QueueJob(
        job_id="warning-job",
        source=source,
        row=0,
        preview_dir=tmp_path / "preview",
        result=result,
    )

    window._render_job(job)

    assert window.warning_label.text() == warning
    assert window.warning_label.isHidden() is False
    assert window.markdown_preview.toPlainText().strip() == "Converted"
    window.close()


def test_save_as_adds_markdown_extension_when_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _application = QApplication.instance() or QApplication([])
    source = _valid_pdf(tmp_path / "source.pdf")
    result = ConversionResult(
        source=source,
        output_path=tmp_path / "preview" / "source.md",
        markdown="# Converted\n",
        used_ocr=False,
        warnings=[],
        error=None,
    )
    window = MainWindow()
    destinations: list[Path] = []
    monkeypatch.setattr(window, "_selected_result", lambda: result)
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(tmp_path / "saved" / "report"), ""),
    )
    monkeypatch.setattr(
        window,
        "_save_to",
        lambda selected_result, destination: destinations.append(destination),
    )

    window._save_selected_as()

    assert destinations == [tmp_path / "saved" / "report.md"]
    window.close()


def test_queue_layout_is_responsive_and_starts_with_an_empty_state() -> None:
    _application = QApplication.instance() or QApplication([])
    window = MainWindow()
    header = window.queue.horizontalHeader()

    assert window.queue_stack.currentWidget() is window.queue_empty_state
    assert header.sectionResizeMode(0) == QHeaderView.ResizeMode.Stretch
    assert header.sectionResizeMode(1) == QHeaderView.ResizeMode.Stretch
    assert header.sectionResizeMode(2) == QHeaderView.ResizeMode.ResizeToContents
    assert window.save_all_button.isEnabled() is False
    assert isinstance(window.drop_zone, QPushButton)
    assert window.drop_zone.accessibleName() == strings.ACCESSIBLE_DROP_ZONE
    window.close()


def test_duplicate_enqueue_is_ignored_and_image_option_is_captured(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _application = QApplication.instance() or QApplication([])
    source = _valid_pdf(tmp_path / "source.pdf")
    window = MainWindow()
    monkeypatch.setattr(window, "_start_next", lambda: None)
    window.skip_images.setChecked(True)

    window.enqueue_paths([source, source])

    assert window.queue.rowCount() == 1
    assert len(window._jobs) == 1
    assert next(iter(window._jobs.values())).include_images is False
    assert "duplicate" in window.statusBar().currentMessage().lower()
    window.close()


def test_empty_folder_reports_that_no_pdfs_were_found(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _application = QApplication.instance() or QApplication([])
    window = MainWindow()
    monkeypatch.setattr(window, "_start_next", lambda: None)

    window.enqueue_paths([tmp_path])

    assert window.queue.rowCount() == 0
    assert window.statusBar().currentMessage() == strings.NO_PDFS_FOUND
    window.close()


def _attach_ready_job(
    window: MainWindow,
    source: Path,
    preview_path: Path,
    job_id: str,
) -> QueueJob:
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    preview_path.write_text(f"# {source.stem}\n", encoding="utf-8")
    result = ConversionResult(
        source=source,
        output_path=preview_path,
        markdown=f"# {source.stem}\n",
        used_ocr=False,
        warnings=[],
        error=None,
    )
    job = QueueJob(
        job_id=job_id,
        source=source,
        row=window.queue.rowCount(),
        preview_dir=preview_path.parent,
        status=strings.STATUS_DONE,
        progress=100,
        result=result,
    )
    window._jobs[job_id] = job
    return job


def test_save_all_writes_ready_jobs_beside_their_sources(tmp_path: Path) -> None:
    _application = QApplication.instance() or QApplication([])
    window = MainWindow()
    first_source = tmp_path / "first.pdf"
    second_source = tmp_path / "second.pdf"
    first_source.write_bytes(b"%PDF-first")
    second_source.write_bytes(b"%PDF-second")
    first = _attach_ready_job(
        window,
        first_source,
        tmp_path / "preview-first" / "first.md",
        "first",
    )
    second = _attach_ready_job(
        window,
        second_source,
        tmp_path / "preview-second" / "second.md",
        "second",
    )

    window._save_all_ready()

    assert first_source.with_suffix(".md").read_text(encoding="utf-8") == "# first\n"
    assert second_source.with_suffix(".md").read_text(encoding="utf-8") == "# second\n"
    assert first.saved_destination == first_source.with_suffix(".md")
    assert second.saved_destination == second_source.with_suffix(".md")
    assert first.status == strings.STATUS_SAVED
    assert second.status == strings.STATUS_SAVED
    assert "2 saved" in window.statusBar().currentMessage()
    window.close()


def test_save_all_can_skip_existing_outputs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _application = QApplication.instance() or QApplication([])
    window = MainWindow()
    source = tmp_path / "existing.pdf"
    source.write_bytes(b"%PDF-existing")
    destination = source.with_suffix(".md")
    destination.write_text("keep me", encoding="utf-8")
    job = _attach_ready_job(
        window,
        source,
        tmp_path / "preview" / "existing.md",
        "existing",
    )
    monkeypatch.setattr(window, "_choose_batch_conflict_action", lambda jobs: "skip")

    window._save_all_ready()

    assert destination.read_text(encoding="utf-8") == "keep me"
    assert job.saved_destination is None
    assert job.status == strings.STATUS_DONE
    assert "1 skipped" in window.statusBar().currentMessage()
    window.close()


def test_save_all_can_replace_existing_outputs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _application = QApplication.instance() or QApplication([])
    window = MainWindow()
    source = tmp_path / "replace.pdf"
    source.write_bytes(b"%PDF-replace")
    destination = source.with_suffix(".md")
    destination.write_text("old output", encoding="utf-8")
    job = _attach_ready_job(
        window,
        source,
        tmp_path / "preview" / "replace.md",
        "replace",
    )
    monkeypatch.setattr(window, "_choose_batch_conflict_action", lambda jobs: "replace")

    window._save_all_ready()

    assert destination.read_text(encoding="utf-8") == "# replace\n"
    assert job.saved_destination == destination
    assert job.status == strings.STATUS_SAVED
    window.close()


def test_save_all_cancel_writes_nothing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _application = QApplication.instance() or QApplication([])
    window = MainWindow()
    source = tmp_path / "cancel.pdf"
    source.write_bytes(b"%PDF-cancel")
    destination = source.with_suffix(".md")
    destination.write_text("keep existing", encoding="utf-8")
    job = _attach_ready_job(
        window,
        source,
        tmp_path / "preview" / "cancel.md",
        "cancel",
    )
    monkeypatch.setattr(window, "_choose_batch_conflict_action", lambda jobs: "cancel")

    window._save_all_ready()

    assert destination.read_text(encoding="utf-8") == "keep existing"
    assert job.saved_destination is None
    assert job.status == strings.STATUS_DONE
    window.close()


def test_save_all_continues_after_one_save_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _application = QApplication.instance() or QApplication([])
    window = MainWindow()
    good_source = tmp_path / "good.pdf"
    bad_source = tmp_path / "bad.pdf"
    good_source.write_bytes(b"%PDF-good")
    bad_source.write_bytes(b"%PDF-bad")
    good = _attach_ready_job(
        window,
        good_source,
        tmp_path / "preview-good" / "good.md",
        "good",
    )
    bad = _attach_ready_job(
        window,
        bad_source,
        tmp_path / "preview-bad" / "bad.md",
        "bad",
    )
    real_save = main_window_module.save_conversion_result

    def fail_one(result, destination, *, overwrite=False):
        if result.source == bad_source:
            raise OSError
        return real_save(result, destination, overwrite=overwrite)

    monkeypatch.setattr(main_window_module, "save_conversion_result", fail_one)

    window._save_all_ready()

    assert good.saved_destination == good_source.with_suffix(".md")
    assert good_source.with_suffix(".md").is_file()
    assert bad.saved_destination is None
    assert bad.status == strings.STATUS_SAVE_FAILED
    assert "1 failed" in window.statusBar().currentMessage()
    window.close()


def test_copy_action_reports_success(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow()
    source = tmp_path / "copy.pdf"
    source.write_bytes(b"%PDF-copy")
    job = _attach_ready_job(
        window,
        source,
        tmp_path / "preview" / "copy.md",
        "copy",
    )
    window._selected_job_id = job.job_id

    window._copy_selected()

    assert application.clipboard().text() == "# copy\n"
    assert window.statusBar().currentMessage() == strings.COPY_SUCCESS
    window.close()


def test_source_preview_rescales_the_original_pixmap() -> None:
    _application = QApplication.instance() or QApplication([])
    preview = SourcePreview()
    preview.resize(240, 180)
    original = QPixmap(600, 900)
    original.fill()

    preview.set_source_pixmap(original)

    displayed = preview.pixmap()
    assert displayed.isNull() is False
    assert displayed.width() <= preview.contentsRect().width()
    assert displayed.height() <= preview.contentsRect().height()


def test_marklift_brand_and_icon_are_available() -> None:
    icon_path = Path(main_window_module.__file__).with_name("assets") / "marklift-icon.png"

    assert strings.APP_NAME == "Marklift"
    assert strings.APP_TITLE == "Marklift"
    assert icon_path.is_file()
    assert QIcon(str(icon_path)).isNull() is False
