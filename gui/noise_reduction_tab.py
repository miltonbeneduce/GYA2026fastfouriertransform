"""User interface for the independent noise-reduction workflow."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.audio_io import load_audio, save_wav
from core.noise_reduction import NoiseReductionResult, reduce_stationary_noise
from gui.file_list import AUDIO_EXTENSIONS, AUDIO_FILTER, FileListWidget, output_subfolder, progress_dialog


class NoiseReductionTab(QWidget):
    """Controls for selecting, previewing, and saving cleaned audio."""

    def __init__(self) -> None:
        super().__init__()
        self.selected_path: Path | None = None
        self.original_signal: np.ndarray | None = None
        self.sample_rate: int | None = None
        self.reduction_result: NoiseReductionResult | None = None

        self.file_list = FileListWidget(Path("data", "raw_audio"), AUDIO_EXTENSIONS, AUDIO_FILTER)
        self.file_list.current_path_changed.connect(self.load_file)

        self.preview_button = QPushButton("Preview spectrum")
        self.preview_button.setEnabled(False)
        self.preview_button.clicked.connect(self.preview_spectrum)

        self.reduce_button = QPushButton("Reduce noise and save")
        self.reduce_button.setEnabled(False)
        self.reduce_button.clicked.connect(self.reduce_and_save)

        self.reduce_all_button = QPushButton("Reduce noise and save all")
        self.reduce_all_button.setToolTip("Process every file in the list and save them as cleaned WAV files.")
        self.reduce_all_button.setEnabled(False)
        self.reduce_all_button.clicked.connect(self.reduce_and_save_all)

        self.status_label = QLabel("Select one or more WAV, MP3 or FLAC recordings, or a whole folder, to begin.")
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
        button_row.addWidget(self.reduce_all_button)
        button_row.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Input recordings (click a file to preview it)"))
        layout.addWidget(self.file_list)
        layout.addLayout(button_row)
        layout.addWidget(self.status_label)
        layout.addWidget(self.canvas, stretch=1)

    def load_file(self, path: Path | None) -> None:
        """Load the file selected in the list and reset any previous processing result."""
        self.reduction_result = None
        self.reduce_all_button.setEnabled(bool(self.file_list.paths()))
        if path is None:
            self.selected_path = self.original_signal = self.sample_rate = None
            self.preview_button.setEnabled(False)
            self.reduce_button.setEnabled(False)
            return

        try:
            signal, sample_rate = load_audio(path)
        except (OSError, RuntimeError, ValueError) as error:
            self.selected_path = self.original_signal = self.sample_rate = None
            self.preview_button.setEnabled(False)
            self.reduce_button.setEnabled(False)
            self.status_label.setText(f"Could not load {path.name}: {error}")
            return

        self.selected_path = path
        self.original_signal = signal
        self.sample_rate = sample_rate
        self.preview_button.setEnabled(True)
        self.reduce_button.setEnabled(True)
        self.status_label.setText(
            f"Loaded {path.name} ({sample_rate} Hz, {signal.size / sample_rate:.2f} seconds)."
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
        output_path = save_wav(
            self._output_path(self.selected_path, timestamp),
            self.reduction_result.cleaned_signal,
            self.reduction_result.sample_rate,
        )
        self.status_label.setText(f"Saved cleaned recording to: {output_path}")
        QMessageBox.information(self, "Noise reduction complete", str(output_path))

    def reduce_and_save_all(self) -> None:
        """Reduce noise in every listed file and save each one as a cleaned WAV."""
        paths = self.file_list.paths()
        if not paths:
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        progress = progress_dialog(self, "Reducing noise…", len(paths))
        saved: list[Path] = []
        failed: list[str] = []
        for index, path in enumerate(paths):
            if progress.wasCanceled():
                break
            progress.setLabelText(f"Reducing noise in {path.name} ({index + 1}/{len(paths)})…")
            QApplication.processEvents()
            try:
                signal, sample_rate = load_audio(path)
                result = reduce_stationary_noise(signal, sample_rate)
                saved.append(save_wav(self._output_path(path, timestamp), result.cleaned_signal, sample_rate))
            except (OSError, RuntimeError, ValueError) as error:
                failed.append(f"{path.name}: {error}")
            progress.setValue(index + 1)
        progress.close()

        folders = sorted({str(path.parent) for path in saved})
        message = f"Saved {len(saved)} of {len(paths)} cleaned file(s) to: {', '.join(folders) or '-'}"
        if failed:
            message += "\n\nFailed:\n" + "\n".join(failed)
        self.status_label.setText(message.splitlines()[0])
        QMessageBox.information(self, "Noise reduction complete", message)

    @staticmethod
    def _output_path(source: Path, timestamp: str) -> Path:
        """data/cleaned_audio/<source folder>/<name>_cleaned_<timestamp>.wav"""
        folder = output_subfolder(source, Path("data", "cleaned_audio"))
        return folder / f"{source.stem}_cleaned_{timestamp}.wav"

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
