"""User interface for the independent layer-comparison workflow."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.layer_export import FftLayer, load_fft_csv, save_layered_plot


class LayerComparisonTab(QWidget):
    """Load saved FFT CSV files and compare them as independent layers."""

    def __init__(self) -> None:
        super().__init__()
        self.layers: list[FftLayer] = []
        self.layer_checks: dict[str, QCheckBox] = {}
        self.selected_points: list[tuple[str, int, float, float]] = []
        self.selected_points_artist = None

        select_button = QPushButton("Select FFT CSV files")
        select_button.clicked.connect(self.select_files)
        self.export_button = QPushButton("Export layered PNG")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export_plot)
        self.save_points_button = QPushButton("Save selected points")
        self.save_points_button.setEnabled(False)
        self.save_points_button.clicked.connect(self.save_selected_points)
        self.clear_points_button = QPushButton("Clear selection")
        self.clear_points_button.setEnabled(False)
        self.clear_points_button.clicked.connect(self.clear_selected_points)
        clear_button = QPushButton("Clear layers")
        clear_button.clicked.connect(self.clear_layers)

        button_row = QHBoxLayout()
        button_row.addWidget(select_button)
        button_row.addWidget(self.export_button)
        button_row.addWidget(self.save_points_button)
        button_row.addWidget(self.clear_points_button)
        button_row.addWidget(clear_button)
        button_row.addStretch()

        self.layer_container = QWidget()
        self.layer_layout = QVBoxLayout(self.layer_container)
        self.layer_layout.setContentsMargins(4, 4, 4, 4)
        self.layer_layout.addWidget(QLabel("No FFT layers selected."))
        self.layer_layout.addStretch()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.layer_container)
        scroll_area.setMaximumHeight(130)

        self.status_label = QLabel("Select one or more CSV files from data/fft_results/.")
        self.status_label.setWordWrap(True)
        self.figure, self.axes = plt.subplots(figsize=(9, 5), constrained_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.canvas.mpl_connect("pick_event", self._on_pick)
        self.axes.set_title("Layered FFT comparison")
        self.axes.set_xlabel("Frequency (Hz)")
        self.axes.set_ylabel("Amplitude (dB)")
        self.axes.set_xlim(0, 5000)
        self.axes.grid(True, alpha=0.25)

        layout = QVBoxLayout(self)
        layout.addLayout(button_row)
        layout.addWidget(scroll_area)
        layout.addWidget(self.status_label)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, stretch=1)

    def select_files(self) -> None:
        """Load several saved FFT CSV files and replace the current layers."""
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select FFT result files",
            str(Path("data", "fft_results")),
            "FFT CSV files (*.csv)",
        )
        if not paths:
            return

        loaded_layers: list[FftLayer] = []
        try:
            for path in paths:
                loaded_layers.append(load_fft_csv(path))
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Could not load FFT data", str(error))
            return

        self.layers = loaded_layers
        self.selected_points.clear()
        self._rebuild_layer_controls()
        self._redraw_plot()

    def clear_layers(self) -> None:
        """Remove all loaded layers and clear the comparison plot."""
        self.layers = []
        self.selected_points.clear()
        self.selected_points_artist = None
        self._rebuild_layer_controls()
        self.axes.clear()
        self.axes.set_title("Layered FFT comparison")
        self.axes.set_xlabel("Frequency (Hz)")
        self.axes.set_ylabel("Amplitude (dB)")
        self.axes.set_xlim(0, 5000)
        self.axes.grid(True, alpha=0.25)
        self.canvas.draw_idle()
        self._update_selection_controls()
        self.export_button.setEnabled(False)
        self.status_label.setText("Select one or more CSV files from data/fft_results/.")

    def export_plot(self) -> None:
        """Export the currently visible layers with a timestamped filename."""
        visible_layers = self._visible_layer_names()
        if not visible_layers:
            QMessageBox.warning(self, "No visible layers", "Enable at least one layer first.")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = save_layered_plot(
            Path("data", "layered_exports", f"layered_comparison_{timestamp}.png"),
            self.layers,
            visible_layers,
        )
        self.status_label.setText(f"Saved layered comparison to: {output_path}")
        QMessageBox.information(self, "Layer export complete", str(output_path))

    def _on_pick(self, event) -> None:
        """Select the nearest point from a picked CSV layer."""
        if event.artist.get_label() not in self._visible_layer_names() or not len(event.ind):
            return
        indices = np.asarray(event.ind, dtype=int)
        points = np.column_stack((
            event.artist.get_xdata()[indices],
            event.artist.get_ydata()[indices],
        ))
        screen_points = self.axes.transData.transform(points)
        mouse_position = np.array([event.mouseevent.x, event.mouseevent.y])
        selected_index = int(indices[np.argmin(np.sum((screen_points - mouse_position) ** 2, axis=1))])
        label = event.artist.get_label()
        if any(layer == label and index == selected_index for layer, index, _, _ in self.selected_points):
            return
        self.selected_points.append((
            label,
            selected_index,
            float(event.artist.get_xdata()[selected_index]),
            float(event.artist.get_ydata()[selected_index]),
        ))
        self._draw_selected_points()
        self._update_selection_controls()

    def _draw_selected_points(self) -> None:
        if self.selected_points_artist is not None:
            self.selected_points_artist.remove()
            self.selected_points_artist = None
        if self.selected_points:
            self.selected_points_artist = self.axes.scatter(
                [frequency for _, _, frequency, _ in self.selected_points],
                [amplitude for _, _, _, amplitude in self.selected_points],
                s=38,
                facecolors="none",
                edgecolors="#111111",
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
            "Save selected CSV points",
            "selected_fft_points.csv",
            "CSV files (*.csv)",
        )
        if not path:
            return
        with Path(path).open("w", newline="", encoding="utf-8") as output_file:
            writer = csv.writer(output_file)
            writer.writerow(("layer", "frequency_hz", "amplitude_db"))
            writer.writerows(
                (label, frequency, amplitude)
                for label, _, frequency, amplitude in self.selected_points
            )
        self.status_label.setText(f"Saved {len(self.selected_points)} selected point(s) to {path}.")

    def _rebuild_layer_controls(self) -> None:
        """Recreate one checkbox for every loaded CSV layer."""
        while self.layer_layout.count():
            item = self.layer_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.layer_checks = {}
        for layer in self.layers:
            check = QCheckBox(layer.label)
            check.setChecked(True)
            check.toggled.connect(self._redraw_plot)
            self.layer_checks[layer.label] = check
            self.layer_layout.addWidget(check)
        self.layer_layout.addStretch()
        self.export_button.setEnabled(bool(self.layers))

    def _visible_layer_names(self) -> set[str]:
        return {label for label, check in self.layer_checks.items() if check.isChecked()}

    def _redraw_plot(self) -> None:
        """Redraw only the layers whose checkboxes are enabled."""
        self.axes.clear()
        visible_layers = self._visible_layer_names()
        self.selected_points = [
            point for point in self.selected_points if point[0] in visible_layers
        ]
        self.selected_points_artist = None
        colors = plt.get_cmap("tab10").colors
        for index, layer in enumerate(self.layers):
            if layer.label not in visible_layers:
                continue
            self.axes.plot(
                layer.frequencies,
                layer.amplitude_db,
                label=layer.label,
                color=colors[index % len(colors)],
                alpha=0.72,
                linewidth=1.2,
                picker=5,
            )
        self.axes.set_title("Layered FFT comparison")
        self.axes.set_xlabel("Frequency (Hz)")
        self.axes.set_ylabel("Amplitude (dB)")
        self.axes.set_xlim(0, 5000)
        self.axes.grid(True, alpha=0.25)
        if visible_layers:
            self.axes.legend()
        self._draw_selected_points()
        self._update_selection_controls()
        self.canvas.draw_idle()
        self.status_label.setText(f"{len(self.layers)} layer(s) loaded; {len(visible_layers)} visible.")
