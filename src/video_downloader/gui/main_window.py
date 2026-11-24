from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from video_downloader.config.settings import AppConfig
from video_downloader.core.errors import DownloadError, DownloadInterruptedError
from video_downloader.core.models import AudioFormat, DownloadRequest, ProgressStatus, Quality
from video_downloader.core.service import DownloadService
from video_downloader.core.url_parsing import extract_urls
from video_downloader.core.validation import validate_url
from video_downloader.gui.download_worker import BatchDownloadWorker, InfoWorker

_COLOR_OK = QColor("#2e7d32")
_COLOR_FAIL = QColor("#c62828")
_COLOR_SKIP = QColor("#8d6e00")
_COLOR_ACTIVE = QColor("#1565c0")


class MainWindow(QMainWindow):
    def __init__(self, service: DownloadService, config: AppConfig) -> None:
        super().__init__()
        self._service = service
        self._config = config
        self._output_dir = config.output_dir
        self._batch_worker: Optional[BatchDownloadWorker] = None
        self._info_worker: Optional[InfoWorker] = None
        # worker index -> (row in the list widget, url)
        self._batch_rows: list[tuple[int, str]] = []
        self._batch_done = 0
        self._batch_failures: list[tuple[str, str]] = []

        self.setWindowTitle("Video Downloader 2")
        self.resize(640, 520)

        hint = QLabel(
            "Paste one URL or many: one per line, separated by spaces/commas, "
            "or glued together (https://...https://...)."
        )
        hint.setWordWrap(True)

        self._url_input = QPlainTextEdit()
        self._url_input.setPlaceholderText("https://...")
        self._url_input.setFixedHeight(100)
        self._url_input.textChanged.connect(self._update_url_count)

        self._url_count_label = QLabel("")

        self._quality_combo = QComboBox()
        for quality in Quality:
            self._quality_combo.addItem(quality.value, quality)

        self._audio_only_checkbox = QCheckBox("Audio only")
        self._audio_format_combo = QComboBox()
        for audio_format in AudioFormat:
            self._audio_format_combo.addItem(audio_format.value, audio_format)
        self._audio_format_combo.setToolTip("mp3 plays on almost every car stereo / player")
        self._audio_format_combo.setEnabled(False)
        self._audio_only_checkbox.toggled.connect(self._audio_format_combo.setEnabled)

        self._output_label = QLabel(str(self._output_dir))
        self._output_button = QPushButton("Choose folder...")
        self._output_button.clicked.connect(self._choose_output_dir)

        self._info_button = QPushButton("Get Info")
        self._info_button.clicked.connect(self._on_get_info)

        self._download_button = QPushButton("Download")
        self._download_button.setToolTip("Ctrl+Enter")
        self._download_button.clicked.connect(self._on_download)

        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.setEnabled(False)
        self._cancel_button.clicked.connect(self._on_cancel)

        self._clear_button = QPushButton("Clear")
        self._clear_button.clicked.connect(self._on_clear)

        self._overall_label = QLabel("")
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)

        self._items_list = QListWidget()

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)

        layout = QVBoxLayout()
        layout.addWidget(hint)
        layout.addWidget(self._url_input)
        layout.addWidget(self._url_count_label)

        options_row = QHBoxLayout()
        options_row.addWidget(QLabel("Quality:"))
        options_row.addWidget(self._quality_combo)
        options_row.addWidget(self._audio_only_checkbox)
        options_row.addWidget(self._audio_format_combo)
        options_row.addStretch(1)
        layout.addLayout(options_row)

        output_row = QHBoxLayout()
        output_row.addWidget(self._output_label, 1)
        output_row.addWidget(self._output_button)
        layout.addLayout(output_row)

        buttons_row = QHBoxLayout()
        buttons_row.addWidget(self._info_button)
        buttons_row.addWidget(self._download_button)
        buttons_row.addWidget(self._cancel_button)
        buttons_row.addWidget(self._clear_button)
        layout.addLayout(buttons_row)

        layout.addWidget(self._overall_label)
        layout.addWidget(self._progress_bar)
        layout.addWidget(self._items_list, 1)
        layout.addWidget(self._status_label)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        for keys in ("Ctrl+Return", "Ctrl+Enter"):
            QShortcut(QKeySequence(keys), self, activated=self._on_download)

    # ---- input -------------------------------------------------------------

    def _update_url_count(self) -> None:
        parsed = extract_urls(self._url_input.toPlainText())
        if not parsed.urls and not parsed.ignored:
            self._url_count_label.setText("")
            return
        parts = [f"{len(parsed.urls)} URL(s) detected"]
        if parsed.duplicates:
            parts.append(f"{parsed.duplicates} duplicate(s) ignored")
        if parsed.ignored:
            parts.append(f"{len(parsed.ignored)} without http(s):// will be skipped")
        self._url_count_label.setText(" · ".join(parts))

    def _choose_output_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose output folder", str(self._output_dir))
        if chosen:
            self._output_dir = Path(chosen)
            self._output_label.setText(str(self._output_dir))

    # ---- info --------------------------------------------------------------

    def _on_get_info(self) -> None:
        parsed = extract_urls(self._url_input.toPlainText())
        if not parsed.urls:
            return
        url = parsed.urls[0]
        self._info_button.setEnabled(False)
        suffix = f" (first of {len(parsed.urls)} URLs)" if len(parsed.urls) > 1 else ""
        self._status_label.setText(f"Fetching info{suffix}...")
        self._info_worker = InfoWorker(self._service, url)
        self._info_worker.succeeded.connect(self._on_info_succeeded)
        self._info_worker.failed.connect(self._on_info_failed)
        self._info_worker.finished.connect(lambda: self._info_button.setEnabled(True))
        self._info_worker.start()

    def _on_info_succeeded(self, info) -> None:
        duration = f", {info.duration_seconds:.0f}s" if info.duration_seconds else ""
        self._status_label.setText(f"{info.title} ({info.extractor}{duration})")

    def _on_info_failed(self, error: DownloadError) -> None:
        self._status_label.setText("")
        QMessageBox.critical(self, "Error", error.user_message)

    # ---- download ----------------------------------------------------------

    def _on_download(self) -> None:
        if self._batch_worker is not None and self._batch_worker.isRunning():
            return

        parsed = extract_urls(self._url_input.toPlainText())
        if not parsed.urls and not parsed.ignored:
            QMessageBox.warning(self, "Missing URL", "Please enter at least one URL first.")
            return

        self._items_list.clear()
        self._batch_rows = []
        self._batch_done = 0
        self._batch_failures = []

        for fragment in parsed.ignored:
            self._add_row(f"SKIPPED  {fragment}  — must start with http:// or https://", _COLOR_SKIP)

        quality: Quality = self._quality_combo.currentData()
        requests: list[DownloadRequest] = []
        for candidate in parsed.urls:
            try:
                url = validate_url(candidate)
            except DownloadError as error:
                self._add_row(f"SKIPPED  {candidate}  — {error.user_message}", _COLOR_SKIP)
                continue
            row = self._add_row(f"WAITING  {url}", None)
            self._batch_rows.append((row, url))
            requests.append(
                DownloadRequest(
                    url=url,
                    output_dir=self._output_dir,
                    quality=quality,
                    audio_only=self._audio_only_checkbox.isChecked(),
                    audio_format=self._audio_format_combo.currentData(),
                    timeout_seconds=self._config.timeout_seconds,
                )
            )

        if not requests:
            self._status_label.setText("No valid URL to download.")
            return

        self._set_running(True)
        self._progress_bar.setValue(0)
        self._update_overall()
        self._status_label.setText("starting...")

        self._batch_worker = BatchDownloadWorker(self._service, requests)
        self._batch_worker.item_started.connect(self._on_item_started)
        self._batch_worker.item_progress.connect(self._on_item_progress)
        self._batch_worker.item_finished.connect(self._on_item_finished)
        self._batch_worker.item_failed.connect(self._on_item_failed)
        self._batch_worker.batch_finished.connect(self._on_batch_finished)
        self._batch_worker.start()

    def _on_item_started(self, index: int) -> None:
        row, url = self._batch_rows[index]
        self._set_row(row, f"STARTING  {url}", _COLOR_ACTIVE)
        self._progress_bar.setValue(0)
        self._items_list.scrollToItem(self._items_list.item(row))

    def _on_item_progress(self, index: int, event) -> None:
        row, url = self._batch_rows[index]
        percent_text = ""
        if event.total_bytes:
            percent = int((event.downloaded_bytes or 0) / event.total_bytes * 100)
            self._progress_bar.setValue(percent)
            percent_text = f" {percent}%"
        elif event.status == ProgressStatus.POSTPROCESSING:
            self._progress_bar.setValue(100)
        self._set_row(row, f"{event.status.value.upper()}{percent_text}  {url}", _COLOR_ACTIVE)
        self._status_label.setText(f"{event.status.value}{percent_text}")

    def _on_item_finished(self, index: int, result) -> None:
        row, url = self._batch_rows[index]
        self._set_row(row, f"DONE  {url}  → {result.file_path}", _COLOR_OK)
        self._batch_done += 1
        self._update_overall()

    def _on_item_failed(self, index: int, error: DownloadError) -> None:
        row, url = self._batch_rows[index]
        label = "CANCELLED" if isinstance(error, DownloadInterruptedError) else "FAILED"
        self._set_row(row, f"{label}  {url}  — {error.user_message}", _COLOR_FAIL)
        self._batch_done += 1
        self._batch_failures.append((url, error.user_message))
        self._update_overall()

    def _on_batch_finished(self) -> None:
        self._set_running(False)
        total = len(self._batch_rows)
        ok = total - len(self._batch_failures)
        if not self._batch_failures:
            self._progress_bar.setValue(100)
            if total == 1:
                self._status_label.setText(self._items_list.item(self._batch_rows[0][0]).text())
            else:
                self._status_label.setText(f"All {total} downloads finished.")
            return

        self._status_label.setText(f"Finished: {ok} succeeded, {len(self._batch_failures)} failed.")
        if total == 1:
            QMessageBox.critical(self, "Download failed", self._batch_failures[0][1])
        else:
            details = "\n".join(f"• {url}\n   {message}" for url, message in self._batch_failures)
            QMessageBox.warning(
                self,
                "Some downloads failed",
                f"{ok} of {total} downloads succeeded.\n\nFailed:\n{details}",
            )

    def _on_cancel(self) -> None:
        if self._batch_worker is not None:
            self._batch_worker.cancel_token.cancel()
            self._status_label.setText("Cancelling...")

    def _on_clear(self) -> None:
        if self._batch_worker is not None and self._batch_worker.isRunning():
            return
        self._url_input.clear()
        self._items_list.clear()
        self._overall_label.setText("")
        self._progress_bar.setValue(0)
        self._status_label.setText("")

    # ---- helpers -----------------------------------------------------------

    def _set_running(self, running: bool) -> None:
        self._download_button.setEnabled(not running)
        self._clear_button.setEnabled(not running)
        self._url_input.setReadOnly(running)
        self._cancel_button.setEnabled(running)

    def _update_overall(self) -> None:
        total = len(self._batch_rows)
        self._overall_label.setText(f"Overall: {self._batch_done}/{total} processed")

    def _add_row(self, text: str, color: Optional[QColor]) -> int:
        item = QListWidgetItem(text)
        if color is not None:
            item.setForeground(color)
        self._items_list.addItem(item)
        return self._items_list.count() - 1

    def _set_row(self, row: int, text: str, color: Optional[QColor]) -> None:
        item = self._items_list.item(row)
        if item is None:
            return
        item.setText(text)
        if color is not None:
            item.setForeground(color)
