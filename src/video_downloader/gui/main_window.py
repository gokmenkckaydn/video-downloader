from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from video_downloader.config.settings import AppConfig
from video_downloader.core.errors import DownloadError
from video_downloader.core.models import DownloadRequest, Quality
from video_downloader.core.service import DownloadService
from video_downloader.gui.download_worker import DownloadWorker, InfoWorker


class MainWindow(QMainWindow):
    def __init__(self, service: DownloadService, config: AppConfig) -> None:
        super().__init__()
        self._service = service
        self._config = config
        self._output_dir = config.output_dir
        self._download_worker: Optional[DownloadWorker] = None
        self._info_worker: Optional[InfoWorker] = None

        self.setWindowTitle("Video Downloader")
        self.resize(480, 260)

        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("https://...")

        self._quality_combo = QComboBox()
        for quality in Quality:
            self._quality_combo.addItem(quality.value, quality)

        self._audio_only_checkbox = QCheckBox("Audio only")

        self._output_label = QLabel(str(self._output_dir))
        self._output_button = QPushButton("Choose folder...")
        self._output_button.clicked.connect(self._choose_output_dir)

        self._info_button = QPushButton("Get Info")
        self._info_button.clicked.connect(self._on_get_info)

        self._download_button = QPushButton("Download")
        self._download_button.clicked.connect(self._on_download)

        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.setEnabled(False)
        self._cancel_button.clicked.connect(self._on_cancel)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)

        layout = QVBoxLayout()
        layout.addWidget(self._url_input)

        options_row = QHBoxLayout()
        options_row.addWidget(QLabel("Quality:"))
        options_row.addWidget(self._quality_combo)
        options_row.addWidget(self._audio_only_checkbox)
        layout.addLayout(options_row)

        output_row = QHBoxLayout()
        output_row.addWidget(self._output_label, 1)
        output_row.addWidget(self._output_button)
        layout.addLayout(output_row)

        buttons_row = QHBoxLayout()
        buttons_row.addWidget(self._info_button)
        buttons_row.addWidget(self._download_button)
        buttons_row.addWidget(self._cancel_button)
        layout.addLayout(buttons_row)

        layout.addWidget(self._progress_bar)
        layout.addWidget(self._status_label)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def _choose_output_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose output folder", str(self._output_dir))
        if chosen:
            self._output_dir = Path(chosen)
            self._output_label.setText(str(self._output_dir))

    def _on_get_info(self) -> None:
        url = self._url_input.text().strip()
        if not url:
            return
        self._info_button.setEnabled(False)
        self._status_label.setText("Fetching info...")
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

    def _on_download(self) -> None:
        url = self._url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Missing URL", "Please enter a URL first.")
            return

        quality: Quality = self._quality_combo.currentData()
        request = DownloadRequest(
            url=url,
            output_dir=self._output_dir,
            quality=quality,
            audio_only=self._audio_only_checkbox.isChecked(),
            timeout_seconds=self._config.timeout_seconds,
        )

        self._download_button.setEnabled(False)
        self._cancel_button.setEnabled(True)
        self._progress_bar.setValue(0)
        self._status_label.setText("starting...")

        self._download_worker = DownloadWorker(self._service, request)
        self._download_worker.progress.connect(self._on_progress)
        self._download_worker.finished_ok.connect(self._on_download_finished)
        self._download_worker.failed.connect(self._on_download_failed)
        self._download_worker.start()

    def _on_progress(self, event) -> None:
        self._status_label.setText(event.status.value)
        if event.total_bytes:
            percent = int((event.downloaded_bytes or 0) / event.total_bytes * 100)
            self._progress_bar.setValue(percent)

    def _on_download_finished(self, result) -> None:
        self._download_button.setEnabled(True)
        self._cancel_button.setEnabled(False)
        self._progress_bar.setValue(100)
        self._status_label.setText(f"Done: {result.file_path}")

    def _on_download_failed(self, error: DownloadError) -> None:
        self._download_button.setEnabled(True)
        self._cancel_button.setEnabled(False)
        self._status_label.setText("Failed")
        QMessageBox.critical(self, "Download failed", error.user_message)

    def _on_cancel(self) -> None:
        if self._download_worker is not None:
            self._download_worker.cancel_token.cancel()
