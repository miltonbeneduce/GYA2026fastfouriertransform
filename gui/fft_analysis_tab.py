"""User interface for the independent FFT-analysis workflow."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from PySide6.QtWidgets import (
    QApplication,
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
from gui.file_list import AUDIO_EXTENSIONS, AUDIO_FILTER, FileListWidget, output_subfolder, progress_dialog


def safe_name(text: str) -> str:
    return "".join(character if character.isalnum() or character in "-_" else "_" for character in text)


class FftAnalysisTab(QWidget):
    """Controls for calculating, previewing, and exporting a tone spectrum."""

    def __init__(self) -> None:
        super().__init__()
        self.selected_path: Path | None = None
        self.signal: np.ndarray | None = None
        self.sample_rate: int | None = None
        self.fft_result: FftResult | None = None
        self.selected_points: list[tuple[int, float, float]] = []
        self.selected_points_artist = None
        self.spectrum_line = None

        self.file_list = FileListWidget(Path("data", "raw_audio"), AUDIO_EXTENSIONS, AUDIO_FILTER)
        self.file_list.current_path_changed.connect(self.load_file)

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
        self.save_all_button = QPushButton("Analyze and save all")
        self.save_all_button.setToolTip(
            "Calculate the FFT of every file in the list and save one PNG and one CSV per file."
        )
        self.save_all_button.setEnabled(False)
        self.save_all_button.clicked.connect(self.save_all_results)
        self.save_points_button = QPushButton("Save selected points")
        self.save_points_button.setEnabled(False)
        self.save_points_button.clicked.connect(self.save_selected_points)
        self.clear_points_button = QPushButton("Clear selection")
        self.clear_points_button.setEnabled(False)
        self.clear_points_button.clicked.connect(self.clear_selected_points)

        metadata_form = QFormLayout()
        metadata_form.addRow("Tone name", self.tone_edit)
        metadata_form.addRow("Instrument", self.instrument_edit)

        button_row = QHBoxLayout()
        button_row.addWidget(self.analyze_button)
        button_row.addWidget(self.save_button)
        button_row.addWidget(self.save_all_button)
        button_row.addWidget(self.save_points_button)
        button_row.addWidget(self.clear_points_button)
        button_row.addStretch()

        self.status_label = QLabel("Select one or more recordings of single tones, or a whole folder, to begin.")
        self.status_label.setWordWrap(True)
        self.figure, self.axes = plt.subplots(figsize=(9, 5), constrained_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.canvas.mpl_connect("pick_event", self._on_pick)
        self.axes.set_title("FFT spectrum")
        self.axes.set_xlabel("Frequency (Hz)")
        self.axes.set_ylabel("Amplitude (dB)")
        self.axes.set_xlim(0, 5000)
        self.axes.grid(True, alpha=0.25)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Input recordings (click a file to analyze it)"))
        layout.addWidget(self.file_list)
        layout.addLayout(metadata_form)
        layout.addLayout(button_row)
        layout.addWidget(self.status_label)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, stretch=1)

    def load_file(self, path: Path | None) -> None:
        """Load the file selected in the list (without resampling) and analyze it."""
        previous_stem = self.selected_path.stem if self.selected_path else ""
        self.fft_result = None
        self.clear_selected_points()
        self.spectrum_line = None
        self.save_button.setEnabled(False)
        self.save_all_button.setEnabled(bool(self.file_list.paths()))
        if path is None:
            self.selected_path = self.signal = self.sample_rate = None
            self.analyze_button.setEnabled(False)
            return

        try:
            signal, sample_rate = load_audio(path)
        except (OSError, RuntimeError, ValueError) as error:
            self.selected_path = self.signal = self.sample_rate = None
            self.analyze_button.setEnabled(False)
            self.status_label.setText(f"Could not load {path.name}: {error}")
            return

        self.selected_path = path
        self.signal = signal
        self.sample_rate = sample_rate
        # Follow the file name unless the user has typed their own tone name.
        if not self.tone_edit.text() or self.tone_edit.text() == previous_stem:
            self.tone_edit.setText(path.stem)
        self.analyze_button.setEnabled(True)
        self.status_label.setText(
            f"Loaded {path.name} ({sample_rate} Hz, {signal.size / sample_rate:.2f} seconds)."
        )
        self.analyze()

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
        self.selected_points.clear()
        self.selected_points_artist = None
        (self.spectrum_line,) = self.axes.plot(
            self.fft_result.frequencies,
            self.fft_result.amplitude_db,
            color="#3366cc",
            linewidth=1,
            picker=5,
        )
        self.axes.set_title("FFT spectrum (0-5000 Hz)")
        self.axes.set_xlabel("Frequency (Hz)")
        self.axes.set_ylabel("Amplitude (dB)")
        self.axes.set_xlim(0, min(5000, self.sample_rate / 2))
        self.axes.grid(True, alpha=0.25)
        self.canvas.draw_idle()
        self._update_selection_controls()
        self.save_button.setEnabled(True)
        self.status_label.setText(
            f"FFT calculated using {self.fft_result.sample_count:,} samples."
        )

    def _on_pick(self, event) -> None:
        """Select the nearest FFT bin clicked on the spectrum line."""
        if event.artist is not self.spectrum_line or not len(event.ind):
            return
        indices = np.asarray(event.ind, dtype=int)
        points = np.column_stack((
            self.spectrum_line.get_xdata()[indices],
            self.spectrum_line.get_ydata()[indices],
        ))
        screen_points = self.axes.transData.transform(points)
        mouse_position = np.array([event.mouseevent.x, event.mouseevent.y])
        selected_index = int(indices[np.argmin(np.sum((screen_points - mouse_position) ** 2, axis=1))])
        if any(index == selected_index for index, _, _ in self.selected_points):
            return
        self.selected_points.append((
            selected_index,
            float(self.spectrum_line.get_xdata()[selected_index]),
            float(self.spectrum_line.get_ydata()[selected_index]),
        ))
        self._draw_selected_points()
        self._update_selection_controls()

    def _draw_selected_points(self) -> None:
        if self.selected_points_artist is not None:
            self.selected_points_artist.remove()
            self.selected_points_artist = None
        if self.selected_points:
            self.selected_points_artist = self.axes.scatter(
                [frequency for _, frequency, _ in self.selected_points],
                [amplitude for _, _, amplitude in self.selected_points],
                s=38,
                facecolors="none",
                edgecolors="#d62728",
                linewidths=1.5,
                zorder=4,
            )
        self.canvas.draw_idle()

    def _update_selection_controls(self) -> None:
        has_selection = bool(self.selected_points)
        self.save_points_button.setEnabled(has_selection)
        self.clear_points_button.setEnabled(has_selection)

    def clear_selected_points(self) -> None:
        self.selected_points.clear()
        self._draw_selected_points()
        self._update_selection_controls()

    def save_selected_points(self) -> None:
        if not self.selected_points:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save selected FFT points",
            str(Path("data", "fft_results", "selected_points.csv")),
            "CSV files (*.csv)",
        )
        if not path:
            return
        points = np.asarray([(frequency, amplitude) for _, frequency, amplitude in self.selected_points])
        np.savetxt(
            path,
            points,
            delimiter=",",
            header="frequency_hz,amplitude_db",
            comments="",
        )
        self.status_label.setText(f"Saved {len(points)} selected point(s) to {path}.")

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
        base_name = safe_name(base_name)
        folder = output_subfolder(self.selected_path, Path("data", "fft_results")) if self.selected_path else Path("data", "fft_results")
        base_path = folder / f"{base_name}_{timestamp}"
        title = f"FFT spectrum: {base_name}"
        png_path = save_fft_plot(base_path.with_suffix(".png"), self.fft_result, title)
        csv_path = save_fft_csv(base_path.with_suffix(".csv"), self.fft_result)
        self.status_label.setText(f"Saved PNG and CSV to {folder}.")
        QMessageBox.information(
            self,
            "FFT export complete",
            f"PNG: {png_path}\nCSV: {csv_path}",
        )

    def save_all_results(self) -> None:
        """Analyze every listed file and save one PNG and one CSV for each."""
        paths = self.file_list.paths()
        if not paths:
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        instrument = self.instrument_edit.text().strip()
        progress = progress_dialog(self, "Calculating FFTs…", len(paths))
        saved_folders: set[str] = set()
        saved = 0
        failed: list[str] = []
        for index, path in enumerate(paths):
            if progress.wasCanceled():
                break
            progress.setLabelText(f"Analyzing {path.name} ({index + 1}/{len(paths)})…")
            QApplication.processEvents()
            try:
                signal, sample_rate = load_audio(path)
                result = calculate_fft(signal, sample_rate)
                base_name = safe_name("_".join(part for part in (path.stem, instrument) if part))
                folder = output_subfolder(path, Path("data", "fft_results"))
                base_path = folder / f"{base_name}_{timestamp}"
                save_fft_plot(base_path.with_suffix(".png"), result, f"FFT spectrum: {base_name}")
                save_fft_csv(base_path.with_suffix(".csv"), result)
                saved += 1
                saved_folders.add(str(folder))
            except (OSError, RuntimeError, ValueError) as error:
                failed.append(f"{path.name}: {error}")
            progress.setValue(index + 1)
        progress.close()

        message = f"Saved PNG and CSV for {saved} of {len(paths)} file(s) to: {', '.join(sorted(saved_folders)) or '-'}"
        if failed:
            message += "\n\nFailed:\n" + "\n".join(failed)
        self.status_label.setText(message.splitlines()[0])
        QMessageBox.information(self, "FFT export complete", message)
