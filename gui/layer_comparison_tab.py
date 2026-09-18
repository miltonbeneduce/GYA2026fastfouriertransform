"""User interface for the independent layer-comparison workflow."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
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

        select_button = QPushButton("Select FFT CSV files")
        select_button.clicked.connect(self.select_files)
        self.export_button = QPushButton("Export layered PNG")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export_plot)
        clear_button = QPushButton("Clear layers")
        clear_button.clicked.connect(self.clear_layers)

        button_row = QHBoxLayout()
        button_row.addWidget(select_button)
        button_row.addWidget(self.export_button)
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
        self.axes.set_title("Layered FFT comparison")
        self.axes.set_xlabel("Frequency (Hz)")
        self.axes.set_ylabel("Amplitude (dB)")
        self.axes.set_xlim(0, 5000)
        self.axes.grid(True, alpha=0.25)

        layout = QVBoxLayout(self)
        layout.addLayout(button_row)
        layout.addWidget(scroll_area)
        layout.addWidget(self.status_label)
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
        self._rebuild_layer_controls()
        self._redraw_plot()

    def clear_layers(self) -> None:
        """Remove all loaded layers and clear the comparison plot."""
        self.layers = []
        self._rebuild_layer_controls()
        self.axes.clear()
        self.axes.set_title("Layered FFT comparison")
        self.axes.set_xlabel("Frequency (Hz)")
        self.axes.set_ylabel("Amplitude (dB)")
        self.axes.set_xlim(0, 5000)
        self.axes.grid(True, alpha=0.25)
        self.canvas.draw_idle()
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
        colors = plt.get_cmap("tab10")
        for index, layer in enumerate(self.layers):
            if layer.label not in visible_layers:
                continue
            self.axes.plot(
                layer.frequencies,
                layer.amplitude_db,
                label=layer.label,
                color=colors(index / max(len(self.layers) - 1, 1)),
                linewidth=1,
            )
        self.axes.set_title("Layered FFT comparison")
        self.axes.set_xlabel("Frequency (Hz)")
        self.axes.set_ylabel("Amplitude (dB)")
        self.axes.set_xlim(0, 5000)
        self.axes.grid(True, alpha=0.25)
        if visible_layers:
            self.axes.legend()
        self.canvas.draw_idle()
        self.status_label.setText(f"{len(self.layers)} layer(s) loaded; {len(visible_layers)} visible.")
