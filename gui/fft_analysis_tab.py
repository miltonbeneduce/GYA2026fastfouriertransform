"""User interface for the independent FFT-analysis workflow."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.audio_io import load_audio
from core.fft_processing import FftResult, calculate_fft, save_fft_csv, save_fft_plot


class FftAnalysisTab(QWidget):
    """Controls for calculating, previewing, and exporting a tone spectrum."""

    def __init__(self) -> None:
        super().__init__()
        self.selected_path: Path | None = None
        self.signal: np.ndarray | None = None
        self.sample_rate: int | None = None
        self.fft_result: FftResult | None = None

        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        browse_button = QPushButton("Select audio file")
        browse_button.clicked.connect(self.select_file)

        self.tone_edit = QLineEdit()
        self.tone_edit.setPlaceholderText("e.g. A4")
        self.instrument_edit = QLineEdit()
        self.instrument_edit.setPlaceholderText("e.g. guitar")

        self.analyze_button = QPushButton("Analyze FFT")
        self.analyze_button.setEnabled(False)
        self.analyze_button.clicked.connect(self.analyze)
        self.save_button = QPushButton("Save PNG and CSV")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_result)

        path_row = QHBoxLayout()
        path_row.addWidget(self.path_edit, stretch=1)
        path_row.addWidget(browse_button)

        metadata_form = QFormLayout()
        metadata_form.addRow("Tone name", self.tone_edit)
        metadata_form.addRow("Instrument", self.instrument_edit)

        button_row = QHBoxLayout()
        button_row.addWidget(self.analyze_button)
        button_row.addWidget(self.save_button)
        button_row.addStretch()

        self.status_label = QLabel("Select a recording of one tone to begin.")
        self.status_label.setWordWrap(True)
        self.figure, self.axes = plt.subplots(figsize=(9, 5), constrained_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.axes.set_title("FFT spectrum")
        self.axes.set_xlabel("Frequency (Hz)")
        self.axes.set_ylabel("Amplitude (dB)")
        self.axes.set_xlim(0, 5000)
        self.axes.grid(True, alpha=0.25)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Input recording"))
        layout.addLayout(path_row)
        layout.addLayout(metadata_form)
        layout.addLayout(button_row)
        layout.addWidget(self.status_label)
        layout.addWidget(self.canvas, stretch=1)

    def select_file(self) -> None:
        """Open a file picker and load the selected audio without resampling."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select audio recording",
            str(Path("data", "raw_audio")),
            "Audio files (*.wav *.mp3 *.flac)",
        )
        if not path:
            return

        try:
            signal, sample_rate = load_audio(path)
        except (OSError, RuntimeError, ValueError) as error:
            QMessageBox.critical(self, "Could not load audio", str(error))
            return

        self.selected_path = Path(path)
        self.signal = signal
        self.sample_rate = sample_rate
        self.fft_result = None
        self.path_edit.setText(str(self.selected_path))
        if not self.tone_edit.text():
            self.tone_edit.setText(self.selected_path.stem)
        self.analyze_button.setEnabled(True)
        self.save_button.setEnabled(False)
        self.status_label.setText(
            f"Loaded {self.selected_path.name} ({sample_rate} Hz, "
            f"{signal.size / sample_rate:.2f} seconds)."
        )

    def analyze(self) -> None:
        """Calculate and display the selected recording's 0-5000 Hz spectrum."""
        if self.signal is None or self.sample_rate is None:
            return

        try:
            self.fft_result = calculate_fft(self.signal, self.sample_rate)
        except ValueError as error:
            QMessageBox.critical(self, "Could not analyze audio", str(error))
            return

        self.axes.clear()
        self.axes.plot(
            self.fft_result.frequencies,
            self.fft_result.amplitude_db,
            color="#3366cc",
            linewidth=1,
        )
        self.axes.set_title("FFT spectrum (0-5000 Hz)")
        self.axes.set_xlabel("Frequency (Hz)")
        self.axes.set_ylabel("Amplitude (dB)")
        self.axes.set_xlim(0, min(5000, self.sample_rate / 2))
        self.axes.grid(True, alpha=0.25)
        self.canvas.draw_idle()
        self.save_button.setEnabled(True)
        self.status_label.setText(
            f"FFT calculated using {self.fft_result.sample_count:,} samples."
        )

    def save_result(self) -> None:
        """Save the current spectrum as one PNG and one CSV file."""
        if self.fft_result is None:
            self.analyze()
        if self.fft_result is None:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name_parts = [self.tone_edit.text().strip(), self.instrument_edit.text().strip()]
        name_parts = [part for part in name_parts if part]
        base_name = "_".join(name_parts) or (self.selected_path.stem if self.selected_path else "fft")
        base_name = "".join(character if character.isalnum() or character in "-_" else "_" for character in base_name)
        base_path = Path("data", "fft_results", f"{base_name}_{timestamp}")
        title = f"FFT spectrum: {base_name}"
        png_path = save_fft_plot(base_path.with_suffix(".png"), self.fft_result, title)
        csv_path = save_fft_csv(base_path.with_suffix(".csv"), self.fft_result)
        self.status_label.setText(f"Saved PNG and CSV to data/fft_results/.")
        QMessageBox.information(
            self,
            "FFT export complete",
            f"PNG: {png_path}\nCSV: {csv_path}",
        )
