"""Background conversion workers."""

from __future__ import annotations

from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from app import strings
from engine import ConversionOptions, ConversionResult, convert


class WorkerSignals(QObject):
    progress = Signal(str, int)
    finished = Signal(str, object)


class ConversionWorker(QRunnable):
    """Run one conversion outside the GUI thread."""

    def __init__(
        self,
        job_id: str,
        source: Path,
        output_dir: Path,
        include_images: bool,
    ) -> None:
        super().__init__()
        self.job_id = job_id
        self.source = source
        self.output_dir = output_dir
        self.include_images = include_images
        self.cancel_event = Event()
        self.signals = WorkerSignals()

    def cancel(self) -> None:
        self.cancel_event.set()

    @Slot()
    def run(self) -> None:
        try:
            result = convert(
                self.source,
                ConversionOptions(
                    include_images=self.include_images,
                    output_dir=self.output_dir,
                    cancel_event=self.cancel_event,
                    progress_callback=self._on_progress,
                ),
            )
        except Exception:
            result = ConversionResult(
                source=self.source,
                output_path=None,
                markdown="",
                used_ocr=False,
                warnings=[],
                error=strings.ERROR_UNKNOWN,
            )
        self.signals.finished.emit(self.job_id, result)

    def _on_progress(self, completed: int, total: int) -> None:
        percent = round((completed / total) * 100) if total else 100
        self.signals.progress.emit(self.job_id, percent)
