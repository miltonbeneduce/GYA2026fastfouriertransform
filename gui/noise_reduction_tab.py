"""User interface for the independent noise-reduction workflow."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.audio_io import load_audio, save_wav
from core.noise_reduction import NoiseReductionResult, reduce_stationary_noise
from gui.main_window import PlaceholderTab


class NoiseReductionTab(QWidget):
    """Controls for selecting, previewing, and saving cleaned audio."""

    def __init__(self) -> None:
        super().__init__(
        )
        self.selected_path: Path | None = None
        self.original_signal: np.ndarray | None = None
        self.sample_rate: int | None = None
        self.reduction_result: NoiseReductionResult | None = None

        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        browse_button = QPushButton("Select audio file")
        browse_button.clicked.connect(self.select_file)

        self.preview_button = QPushButton("Preview spectrum")
        self.preview_button.setEnabled(False)
        self.preview_button.clicked.connect(self.preview_spectrum)

        self.reduce_button = QPushButton("Reduce noise and save")
        self.reduce_button.setEnabled(False)
        self.reduce_button.clicked.connect(self.reduce_and_save)

        path_row = QHBoxLayout()
        path_row.addWidget(self.path_edit, stretch=1)
        path_row.addWidget(browse_button)

        self.status_label = QLabel("Select a WAV, MP3, or FLAC recording to begin.")
        self.status_label.setWordWrap(True)

        self.figure, self.axes = plt.subplots(figsize=(9, 5), constrained_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.axes.set_title("Spectrum preview")
        self.axes.set_xlabel("Frequency (Hz)")
        self.axes.set_ylabel("Amplitude (dB)")
        self.axes.grid(True, alpha=0.25)

        button_row = QHBoxLayout()
        button_row.addWidget(self.preview_button)
        button_row.addWidget(self.reduce_button)
        button_row.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Input recording"))
        layout.addLayout(path_row)
        layout.addLayout(button_row)
        layout.addWidget(self.status_label)
        layout.addWidget(self.canvas, stretch=1)

    def select_file(self) -> None:
        """Open a file picker and reset any previous processing result."""
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
        self.original_signal = signal
        self.sample_rate = sample_rate
        self.reduction_result = None
        self.path_edit.setText(str(self.selected_path))
        self.preview_button.setEnabled(True)
        self.reduce_button.setEnabled(True)
        self.status_label.setText(
            f"Loaded {self.selected_path.name} ({sample_rate} Hz, "
            f"{signal.size / sample_rate:.2f} seconds)."
        )
        self.preview_spectrum()

    def preview_spectrum(self) -> None:
        """Show original and, when available, cleaned spectra for comparison."""
        if self.original_signal is None or self.sample_rate is None:
            return

        self.reduction_result = reduce_stationary_noise(
            self.original_signal,
            self.sample_rate,
        )
        self.axes.clear()
        self._plot_spectrum(self.original_signal, self.sample_rate, "Before", "#3366cc")
        self._plot_spectrum(
            self.reduction_result.cleaned_signal,
            self.sample_rate,
            "After",
            "#cc5533",
        )
        self.axes.set_title("Before and after spectral noise reduction")
        self.axes.set_xlabel("Frequency (Hz)")
        self.axes.set_ylabel("Amplitude (dB)")
        self.axes.set_xlim(left=0)
        self.axes.grid(True, alpha=0.25)
        self.axes.legend()
        self.canvas.draw_idle()
        self.status_label.setText(
            "Preview calculated. Compare tonal peaks before saving the cleaned WAV."
        )

    def reduce_and_save(self) -> None:
        """Save the processed recording in the fixed cleaned-audio directory."""
        if self.selected_path is None or self.reduction_result is None:
            self.preview_spectrum()
        if self.selected_path is None or self.reduction_result is None:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"{self.selected_path.stem}_cleaned_{timestamp}.wav"
        output_path = save_wav(
            Path("data", "cleaned_audio", output_name),
            self.reduction_result.cleaned_signal,
            self.reduction_result.sample_rate,
        )
        self.status_label.setText(f"Saved cleaned recording to: {output_path}")
        QMessageBox.information(self, "Noise reduction complete", str(output_path))

    def _plot_spectrum(
        self,
        signal: np.ndarray,
        sample_rate: int,
        label: str,
        color: str,
    ) -> None:
        """Plot a one-sided dB FFT for visual before/after inspection."""
        windowed_signal = signal * np.hanning(signal.size)
        spectrum = np.abs(np.fft.rfft(windowed_signal))
        frequencies = np.fft.rfftfreq(signal.size, 1 / sample_rate)
        normalized = spectrum / max(1, signal.size)
        decibels = 20 * np.log10(np.maximum(normalized, 1e-12))
        self.axes.plot(frequencies, decibels, label=label, color=color, linewidth=1)
