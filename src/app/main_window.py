"""Single-window desktop interface."""

from __future__ import annotations

import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QCloseEvent,
    QDragEnterEvent,
    QDropEvent,
    QPixmap,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app import strings
from app.worker import ConversionWorker
from engine import ConversionResult, render_page_thumbnail, save_conversion_result


class DropZone(QPushButton):
    """Keyboard-operable file picker that also accepts local file drops."""

    paths_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__(strings.DROP_ZONE)
        self.setObjectName("dropZone")
        self.setAccessibleName(strings.ACCESSIBLE_DROP_ZONE)
        self.setAcceptDrops(True)
        self.setMinimumHeight(82)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and any(
            url.isLocalFile() for url in event.mimeData().urls()
        ):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.paths_dropped.emit(paths)
            event.acceptProposedAction()


class SourcePreview(QLabel):
    """A source-page preview that remains crisp when the window is resized."""

    def __init__(self) -> None:
        super().__init__(strings.NO_SOURCE_PREVIEW)
        self._source_pixmap: QPixmap | None = None
        self.setObjectName("sourceCanvas")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAccessibleName(strings.ACCESSIBLE_SOURCE_PREVIEW)
        self.setMinimumSize(300, 240)

    def set_source_pixmap(self, pixmap: QPixmap) -> None:
        self._source_pixmap = pixmap
        self.setText("")
        self._rescale_pixmap()

    def clear_source_pixmap(self, message: str = strings.NO_SOURCE_PREVIEW) -> None:
        self._source_pixmap = None
        self.setPixmap(QPixmap())
        self.setText(message)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._rescale_pixmap()

    def _rescale_pixmap(self) -> None:
        if self._source_pixmap is None or self._source_pixmap.isNull():
            return
        available = self.contentsRect().size()
        self.setPixmap(
            self._source_pixmap.scaled(
                available,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )


class QueueStatusWidget(QWidget):
    """Compact queue status with an optional determinate progress bar."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(4)

        self.state_label = QLabel(strings.STATUS_WAITING)
        self.state_label.setObjectName("queueState")
        self.state_label.setProperty("kind", "waiting")
        self.state_label.setWordWrap(True)
        layout.addWidget(self.state_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.hide()
        layout.addWidget(self.progress)

    def set_status(
        self,
        text: str,
        *,
        progress: int = 0,
        show_progress: bool = False,
        kind: str = "waiting",
    ) -> None:
        self.state_label.setText(text)
        self.state_label.setAccessibleName(text)
        self.state_label.setProperty("kind", kind)
        self.state_label.style().unpolish(self.state_label)
        self.state_label.style().polish(self.state_label)
        self.progress.setValue(max(0, min(progress, 100)))
        self.progress.setAccessibleName(text)
        self.progress.setVisible(show_progress)


@dataclass(slots=True)
class QueueJob:
    job_id: str
    source: Path
    row: int
    preview_dir: Path
    include_images: bool = True
    status: str = strings.STATUS_WAITING
    progress: int = 0
    result: ConversionResult | None = None
    worker: ConversionWorker | None = None
    saved_destination: Path | None = None
    save_error: str | None = None


BatchConflictChoice = Literal["replace", "skip", "cancel"]


class MainWindow(QMainWindow):
    """The application's single, keyboard-accessible main window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(strings.APP_NAME)
        application = QApplication.instance()
        if application is not None:
            self.setWindowIcon(application.windowIcon())
        self.resize(1180, 800)
        self.setMinimumSize(960, 680)

        self._preview_temp = tempfile.TemporaryDirectory(
            prefix="marklift-preview-",
            ignore_cleanup_errors=True,
        )
        self._jobs: dict[str, QueueJob] = {}
        self._status_widgets: dict[str, QueueStatusWidget] = {}
        self._current_job_id: str | None = None
        self._selected_job_id: str | None = None

        self._build_ui()
        self.thread_pool.setMaxThreadCount(1)

    @property
    def thread_pool(self):
        from PySide6.QtCore import QThreadPool

        return QThreadPool.globalInstance()

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("appRoot")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 16, 20, 10)
        layout.setSpacing(12)

        layout.addWidget(self._build_header())
        layout.addWidget(self._build_intake_card())
        layout.addWidget(self._build_queue_card())
        layout.addWidget(self._build_preview_splitter(), stretch=1)

        self.setCentralWidget(central)
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().showMessage(strings.STATUSBAR_READY)

        self.setTabOrder(self.drop_zone, self.add_files_button)
        self.setTabOrder(self.add_files_button, self.add_folder_button)
        self.setTabOrder(self.add_folder_button, self.skip_images)
        self.setTabOrder(self.skip_images, self.queue)
        self.setTabOrder(self.queue, self.copy_button)
        self.setTabOrder(self.copy_button, self.save_as_button)
        self.setTabOrder(self.save_as_button, self.save_button)

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("appHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(2, 0, 2, 0)
        header_layout.setSpacing(12)

        icon = QLabel()
        app_icon = self.windowIcon()
        if app_icon.isNull():
            app_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        icon.setPixmap(app_icon.pixmap(38, 38))
        icon.setAccessibleName(strings.APP_TITLE)
        header_layout.addWidget(icon)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(1)
        title = QLabel(strings.APP_TITLE)
        title.setObjectName("appTitle")
        subtitle = QLabel(strings.APP_SUBTITLE)
        subtitle.setObjectName("secondaryText")
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        offline_badge = QLabel(strings.OFFLINE_BADGE)
        offline_badge.setObjectName("offlineBadge")
        offline_badge.setAccessibleName(strings.OFFLINE_TRUST)
        header_layout.addWidget(offline_badge)
        return header

    def _build_intake_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(9)

        self.drop_zone = DropZone()
        self.drop_zone.clicked.connect(self._choose_files)
        self.drop_zone.paths_dropped.connect(self.enqueue_paths)
        card_layout.addWidget(self.drop_zone)

        controls = QHBoxLayout()
        controls.setSpacing(8)

        self.add_files_button = QPushButton(strings.ADD_PDFS)
        self.add_files_button.setProperty("primary", True)
        self.add_files_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton)
        )
        self.add_files_button.clicked.connect(self._choose_files)
        controls.addWidget(self.add_files_button)

        self.add_folder_button = QPushButton(strings.ADD_FOLDER)
        self.add_folder_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)
        )
        self.add_folder_button.clicked.connect(self._choose_folder)
        controls.addWidget(self.add_folder_button)
        controls.addStretch()

        options = QVBoxLayout()
        options.setSpacing(0)
        self.skip_images = QCheckBox(strings.SKIP_IMAGES)
        option_help = QLabel(strings.SKIP_IMAGES_HELP)
        option_help.setObjectName("optionHelp")
        options.addWidget(self.skip_images)
        options.addWidget(option_help)
        controls.addLayout(options)
        card_layout.addLayout(controls)
        return card

    def _build_queue_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(12, 10, 12, 9)
        header.setSpacing(9)
        title = QLabel(strings.QUEUE_TITLE)
        title.setObjectName("sectionTitle")
        header.addWidget(title)
        self.queue_summary = QLabel(strings.QUEUE_SUMMARY_EMPTY)
        self.queue_summary.setObjectName("secondaryText")
        header.addWidget(self.queue_summary)
        header.addStretch()
        self.save_all_button = QPushButton(strings.SAVE_ALL)
        self.save_all_button.setProperty("primary", True)
        self.save_all_button.setEnabled(False)
        self.save_all_button.clicked.connect(self._save_all_ready)
        header.addWidget(self.save_all_button)
        card_layout.addLayout(header)

        self.queue_stack = QStackedWidget()
        self.queue_stack.setMinimumHeight(156)

        empty_state = QWidget()
        empty_layout = QVBoxLayout(empty_state)
        empty_layout.setContentsMargins(20, 20, 20, 22)
        empty_layout.addStretch()
        empty_title = QLabel(strings.QUEUE_EMPTY_TITLE)
        empty_title.setObjectName("sectionTitle")
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_help = QLabel(strings.QUEUE_EMPTY_HELP)
        empty_help.setObjectName("secondaryText")
        empty_help.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_title)
        empty_layout.addWidget(empty_help)
        empty_layout.addStretch()
        self.queue_stack.addWidget(empty_state)
        self.queue_empty_state = empty_state

        self.queue = QTableWidget(0, 3)
        self.queue.setHorizontalHeaderLabels(
            [strings.QUEUE_FILE, strings.QUEUE_STATUS, strings.QUEUE_ACTION]
        )
        self.queue.setAccessibleName(strings.ACCESSIBLE_QUEUE)
        self.queue.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.queue.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.queue.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.queue.setAlternatingRowColors(True)
        self.queue.setShowGrid(False)
        self.queue.verticalHeader().hide()
        self.queue.verticalHeader().setDefaultSectionSize(50)
        queue_header = self.queue.horizontalHeader()
        queue_header.setStretchLastSection(False)
        queue_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        queue_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        queue_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.queue.itemSelectionChanged.connect(self._show_selected_job)
        self.queue_stack.addWidget(self.queue)
        card_layout.addWidget(self.queue_stack)
        return card

    def _build_preview_splitter(self) -> QSplitter:
        preview_splitter = QSplitter(Qt.Orientation.Horizontal)
        preview_splitter.setChildrenCollapsible(False)

        source_panel = QFrame()
        source_panel.setObjectName("card")
        source_layout = QVBoxLayout(source_panel)
        source_layout.setContentsMargins(12, 10, 12, 12)
        source_layout.setSpacing(8)
        source_layout.addLayout(self._preview_header(strings.SOURCE_PREVIEW, source=True))
        self.source_preview = SourcePreview()
        source_layout.addWidget(self.source_preview, stretch=1)

        markdown_panel = QFrame()
        markdown_panel.setObjectName("card")
        markdown_layout = QVBoxLayout(markdown_panel)
        markdown_layout.setContentsMargins(12, 10, 12, 12)
        markdown_layout.setSpacing(8)
        markdown_layout.addLayout(
            self._preview_header(strings.MARKDOWN_PREVIEW, source=False)
        )
        self.markdown_preview = QTextBrowser()
        self.markdown_preview.setObjectName("markdownCanvas")
        self.markdown_preview.setAccessibleName(strings.ACCESSIBLE_MARKDOWN_PREVIEW)
        self.markdown_preview.setOpenExternalLinks(False)
        self.markdown_preview.setPlainText(strings.NO_MARKDOWN_PREVIEW)
        markdown_layout.addWidget(self.markdown_preview, stretch=1)

        self.warning_label = QLabel()
        self.warning_label.setObjectName("warningCallout")
        self.warning_label.setAccessibleName(strings.ACCESSIBLE_WARNINGS)
        self.warning_label.setWordWrap(True)
        self.warning_label.hide()
        markdown_layout.addWidget(self.warning_label)

        action_row = QHBoxLayout()
        action_row.addStretch()
        self.copy_button = QPushButton(strings.COPY)
        self.save_as_button = QPushButton(strings.SAVE_AS)
        self.save_button = QPushButton(strings.SAVE)
        self.save_button.setProperty("primary", True)
        self.copy_button.clicked.connect(self._copy_selected)
        self.save_as_button.clicked.connect(self._save_selected_as)
        self.save_button.clicked.connect(self._save_selected)
        for button in (self.copy_button, self.save_as_button, self.save_button):
            button.setEnabled(False)
            action_row.addWidget(button)
        markdown_layout.addLayout(action_row)

        preview_splitter.addWidget(source_panel)
        preview_splitter.addWidget(markdown_panel)
        preview_splitter.setSizes([540, 540])
        return preview_splitter

    def _preview_header(self, title_text: str, *, source: bool) -> QHBoxLayout:
        header = QHBoxLayout()
        title = QLabel(title_text)
        title.setObjectName("sectionTitle")
        header.addWidget(title)
        header.addStretch()
        context = QLabel(strings.NO_FILE_SELECTED)
        context.setObjectName("fileContext")
        context.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        header.addWidget(context)
        if source:
            self.source_filename = context
        else:
            self.markdown_filename = context
        return header

    def _choose_files(self) -> None:
        filenames, _ = QFileDialog.getOpenFileNames(
            self,
            strings.OPEN_DIALOG_TITLE,
            "",
            strings.PDF_FILE_FILTER,
        )
        if filenames:
            self.enqueue_paths([Path(filename) for filename in filenames])

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            strings.FOLDER_DIALOG_TITLE,
            "",
        )
        if folder:
            self.enqueue_paths([Path(folder)])

    def enqueue_paths(self, paths: list[Path]) -> None:
        sources: list[Path] = []
        for path in paths:
            if path.is_dir():
                sources.extend(
                    sorted(
                        child
                        for child in path.rglob("*")
                        if child.is_file() and child.suffix.lower() == ".pdf"
                    )
                )
            elif path.is_file() and path.suffix.lower() == ".pdf":
                sources.append(path)

        existing = {job.source.resolve() for job in self._jobs.values()}
        new_sources: list[Path] = []
        duplicate_count = 0
        for source in sources:
            resolved = source.resolve()
            if resolved in existing:
                duplicate_count += 1
                continue
            existing.add(resolved)
            new_sources.append(source)

        if not new_sources:
            message = (
                strings.DUPLICATES_SKIPPED.format(count=duplicate_count)
                if duplicate_count
                else strings.NO_PDFS_FOUND
            )
            self._show_message(message)
            return

        include_images = not self.skip_images.isChecked()
        for source in new_sources:
            job_id = uuid.uuid4().hex
            row = self.queue.rowCount()
            self.queue.insertRow(row)
            preview_dir = Path(self._preview_temp.name) / job_id
            job = QueueJob(
                job_id=job_id,
                source=source,
                row=row,
                preview_dir=preview_dir,
                include_images=include_images,
            )
            self._jobs[job_id] = job

            file_item = QTableWidgetItem(source.name)
            file_item.setToolTip(str(source))
            file_item.setData(Qt.ItemDataRole.UserRole, job_id)
            self.queue.setItem(row, 0, file_item)

            status_item = QTableWidgetItem()
            status_item.setData(
                Qt.ItemDataRole.AccessibleTextRole,
                strings.STATUS_WAITING,
            )
            self.queue.setItem(row, 1, status_item)
            status_widget = QueueStatusWidget()
            self._status_widgets[job_id] = status_widget
            self.queue.setCellWidget(row, 1, status_widget)

            cancel_button = QPushButton(strings.CANCEL)
            cancel_button.clicked.connect(
                lambda checked=False, value=job_id: self.cancel_job(value)
            )
            self.queue.setCellWidget(row, 2, cancel_button)

        self.queue_stack.setCurrentWidget(self.queue)
        if self.queue.currentRow() < 0:
            self.queue.selectRow(0)
        feedback = strings.FILES_ADDED.format(count=len(new_sources))
        if duplicate_count:
            feedback = (
                f"{feedback} {strings.DUPLICATES_SKIPPED.format(count=duplicate_count)}"
            )
        self._show_message(feedback)
        self._update_queue_summary()
        self._update_actions()
        self._start_next()

    def _start_next(self) -> None:
        if self._current_job_id is not None:
            return
        job = next(
            (
                candidate
                for candidate in self._jobs.values()
                if candidate.status == strings.STATUS_WAITING
            ),
            None,
        )
        if job is None:
            return

        self._current_job_id = job.job_id
        job.progress = 0
        self._set_status(
            job,
            strings.STATUS_CONVERTING.format(percent=0),
            progress=0,
            kind="active",
        )
        worker = ConversionWorker(
            job_id=job.job_id,
            source=job.source,
            output_dir=job.preview_dir,
            include_images=job.include_images,
        )
        job.worker = worker
        worker.signals.progress.connect(self._update_progress)
        worker.signals.finished.connect(self._conversion_finished)
        self.thread_pool.start(worker)

    def _update_progress(self, job_id: str, percent: int) -> None:
        job = self._jobs[job_id]
        job.progress = percent
        self._set_status(
            job,
            strings.STATUS_CONVERTING.format(percent=percent),
            progress=percent,
            kind="active",
        )

    def _conversion_finished(self, job_id: str, result: ConversionResult) -> None:
        job = self._jobs[job_id]
        job.result = result
        job.worker = None
        job.progress = 100
        if result.error == strings.ERROR_CANCELLED:
            status = strings.STATUS_CANCELLED
            kind = "cancelled"
        elif result.error:
            status = strings.STATUS_FAILED.format(message=result.error)
            kind = "failed"
        else:
            status = strings.STATUS_DONE
            kind = "ready"
        self._set_status(job, status, progress=100, kind=kind)
        self._hide_cancel_action(job)

        self._current_job_id = None
        if self._selected_job_id == job_id:
            self._render_job(job)
        self._start_next()

    def cancel_job(self, job_id: str) -> None:
        job = self._jobs[job_id]
        button = self.queue.cellWidget(job.row, 2)
        if isinstance(button, QPushButton):
            button.setEnabled(False)
        if job.worker is not None:
            self._set_status(
                job,
                strings.STATUS_CANCELLING,
                progress=job.progress,
                kind="active",
            )
            job.worker.cancel()
        elif job.status == strings.STATUS_WAITING:
            self._set_status(job, strings.STATUS_CANCELLED, kind="cancelled")
            self._hide_cancel_action(job)
            self._start_next()

    def _set_status(
        self,
        job: QueueJob,
        status: str,
        *,
        progress: int | None = None,
        kind: str = "waiting",
    ) -> None:
        job.status = status
        if progress is not None:
            job.progress = progress
        item = self.queue.item(job.row, 1)
        if item is not None:
            item.setText("")
            item.setData(Qt.ItemDataRole.AccessibleTextRole, status)
            item.setToolTip(status)
        status_widget = self._status_widgets.get(job.job_id)
        if status_widget is not None:
            show_progress = status.startswith("Converting") or status == strings.STATUS_CANCELLING
            status_widget.set_status(
                status,
                progress=job.progress,
                show_progress=show_progress,
                kind=kind,
            )
        self._update_queue_summary()
        self._update_actions()

    def _hide_cancel_action(self, job: QueueJob) -> None:
        button = self.queue.cellWidget(job.row, 2)
        if isinstance(button, QPushButton):
            button.setEnabled(False)
            button.hide()
            self.queue.removeCellWidget(job.row, 2)
            button.deleteLater()

    def _show_selected_job(self) -> None:
        row = self.queue.currentRow()
        item = self.queue.item(row, 0) if row >= 0 else None
        if item is None:
            return
        job_id = item.data(Qt.ItemDataRole.UserRole)
        self._selected_job_id = job_id
        self._render_job(self._jobs[job_id])

    def _render_job(self, job: QueueJob) -> None:
        self.source_filename.setText(job.source.name)
        self.source_filename.setToolTip(str(job.source))
        self.markdown_filename.setText(job.source.name)
        self.markdown_filename.setToolTip(str(job.source))

        thumbnail = render_page_thumbnail(job.source)
        pixmap = QPixmap()
        if thumbnail and pixmap.loadFromData(thumbnail, "PNG"):
            self.source_preview.set_source_pixmap(pixmap)
        else:
            self.source_preview.clear_source_pixmap()

        ready = job.result is not None and job.result.error is None
        if ready:
            self.markdown_preview.setMarkdown(job.result.markdown)
            self.warning_label.setText("\n".join(job.result.warnings))
            self.warning_label.setVisible(bool(job.result.warnings))
        elif job.result is not None and job.result.error:
            self.markdown_preview.setPlainText(job.result.error)
            self.warning_label.hide()
        else:
            self.markdown_preview.setPlainText(strings.NO_MARKDOWN_PREVIEW)
            self.warning_label.hide()
        self._update_actions()

    def _selected_job(self) -> QueueJob | None:
        if self._selected_job_id is None:
            return None
        return self._jobs.get(self._selected_job_id)

    def _selected_result(self) -> ConversionResult | None:
        job = self._selected_job()
        return job.result if job is not None else None

    def _save_selected(self) -> None:
        result = self._selected_result()
        if result is not None:
            self._save_to(result, result.source.with_suffix(".md"))

    def _save_selected_as(self) -> None:
        result = self._selected_result()
        if result is None:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self,
            strings.SAVE_AS_TITLE,
            str(result.source.with_suffix(".md")),
            strings.MARKDOWN_FILE_FILTER,
        )
        if filename:
            destination = Path(filename)
            if not destination.suffix:
                destination = destination.with_suffix(".md")
            self._save_to(result, destination)

    def _save_to(self, result: ConversionResult, destination: Path) -> bool:
        if destination.resolve() == result.source.resolve():
            QMessageBox.warning(
                self,
                strings.SAVE_FAILED_TITLE,
                strings.ERROR_INVALID_DESTINATION,
            )
            return False

        overwrite = False
        if self._output_conflicts(result, destination):
            answer = QMessageBox.question(
                self,
                strings.OVERWRITE_TITLE,
                strings.OVERWRITE_MESSAGE.format(filename=destination.name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False
            overwrite = True

        job = self._job_for_result(result)
        try:
            save_conversion_result(result, destination, overwrite=overwrite)
        except Exception:
            if job is not None:
                job.save_error = strings.SAVE_FAILED_MESSAGE
                self._set_status(job, strings.STATUS_SAVE_FAILED, kind="failed")
            QMessageBox.warning(
                self,
                strings.SAVE_FAILED_TITLE,
                strings.SAVE_FAILED_MESSAGE,
            )
            return False

        if job is not None:
            self._mark_saved(job, destination)
        self._show_message(strings.SAVE_SUCCESS.format(destination=destination))
        return True

    @staticmethod
    def _output_conflicts(result: ConversionResult, destination: Path) -> bool:
        if destination.exists():
            return True
        if result.output_path is None:
            return False
        source_assets = result.output_path.parent / f"{result.source.stem}_assets"
        target_assets = destination.parent / f"{destination.stem}_assets"
        return source_assets.is_dir() and target_assets.exists()

    def _job_for_result(self, result: ConversionResult) -> QueueJob | None:
        return next(
            (job for job in self._jobs.values() if job.result is result),
            None,
        )

    def _mark_saved(self, job: QueueJob, destination: Path) -> None:
        job.saved_destination = destination
        job.save_error = None
        self._set_status(job, strings.STATUS_SAVED, progress=100, kind="saved")

    def _copy_selected(self) -> None:
        result = self._selected_result()
        if result is not None and result.error is None:
            QApplication.clipboard().setText(result.markdown)
            self._show_message(strings.COPY_SUCCESS)

    def _save_all_ready(self) -> None:
        candidates = self._pending_save_jobs()
        if not candidates:
            return

        conflict_jobs = [
            job
            for job in candidates
            if self._output_conflicts(job.result, job.source.with_suffix(".md"))
        ]
        choice: BatchConflictChoice = "replace"
        if conflict_jobs:
            choice = self._choose_batch_conflict_action(conflict_jobs)
            if choice == "cancel":
                return

        conflict_ids = {job.job_id for job in conflict_jobs}
        saved = 0
        skipped = 0
        failed = 0
        for job in candidates:
            has_conflict = job.job_id in conflict_ids
            if has_conflict and choice == "skip":
                skipped += 1
                continue
            destination = job.source.with_suffix(".md")
            try:
                save_conversion_result(
                    job.result,
                    destination,
                    overwrite=has_conflict and choice == "replace",
                )
            except Exception:
                failed += 1
                job.save_error = strings.SAVE_FAILED_MESSAGE
                self._set_status(job, strings.STATUS_SAVE_FAILED, kind="failed")
                continue
            saved += 1
            self._mark_saved(job, destination)

        self._show_message(
            strings.BATCH_SAVE_SUMMARY.format(
                saved=saved,
                skipped=skipped,
                failed=failed,
            ),
            timeout=7000,
        )

    def _choose_batch_conflict_action(
        self,
        conflict_jobs: list[QueueJob],
    ) -> BatchConflictChoice:
        filenames = "\n".join(f"• {job.source.name}" for job in conflict_jobs)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(strings.BATCH_CONFLICT_TITLE)
        box.setText(
            strings.BATCH_CONFLICT_MESSAGE.format(
                count=len(conflict_jobs),
                filenames=filenames,
            )
        )
        replace_button = box.addButton(
            strings.REPLACE_EXISTING,
            QMessageBox.ButtonRole.AcceptRole,
        )
        skip_button = box.addButton(
            strings.SKIP_EXISTING,
            QMessageBox.ButtonRole.DestructiveRole,
        )
        cancel_button = box.addButton(
            QMessageBox.StandardButton.Cancel,
        )
        box.setDefaultButton(skip_button)
        box.exec()
        clicked = box.clickedButton()
        if clicked is replace_button:
            return "replace"
        if clicked is skip_button:
            return "skip"
        if clicked is cancel_button:
            return "cancel"
        return "cancel"

    def _pending_save_jobs(self) -> list[QueueJob]:
        return [
            job
            for job in self._jobs.values()
            if job.result is not None
            and job.result.error is None
            and job.saved_destination is None
        ]

    def _update_queue_summary(self) -> None:
        total = len(self._jobs)
        if total == 0:
            self.queue_summary.setText(strings.QUEUE_SUMMARY_EMPTY)
            return
        completed = sum(
            job.status
            not in {
                strings.STATUS_WAITING,
                strings.STATUS_CANCELLING,
            }
            and not job.status.startswith("Converting")
            for job in self._jobs.values()
        )
        self.queue_summary.setText(
            strings.QUEUE_SUMMARY.format(completed=completed, total=total)
        )

    def _update_actions(self) -> None:
        selected = self._selected_job()
        ready = (
            selected is not None
            and selected.result is not None
            and selected.result.error is None
        )
        for button in (self.save_button, self.save_as_button, self.copy_button):
            button.setEnabled(ready)

        pending_count = len(self._pending_save_jobs())
        self.save_all_button.setEnabled(pending_count > 0)
        self.save_all_button.setText(
            strings.SAVE_ALL_COUNT.format(count=pending_count)
            if pending_count
            else strings.SAVE_ALL
        )

    def _show_message(self, message: str, *, timeout: int = 5000) -> None:
        self.statusBar().showMessage(message, timeout)

    def job_states(self) -> dict[str, str]:
        """Expose queue state for headless smoke tests."""

        return {job.source.name: job.status for job in self._jobs.values()}

    def closeEvent(self, event: QCloseEvent) -> None:
        for job in self._jobs.values():
            if job.worker is not None:
                job.worker.cancel()
        workers_finished = self.thread_pool.waitForDone(5000)
        if workers_finished:
            self._preview_temp.cleanup()
        super().closeEvent(event)
