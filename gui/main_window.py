"""Main application window and shared directory initialization."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget


class MainWindow(QMainWindow):
    """Top-level window containing one independent tab per analysis feature."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Tone Spectrum Analyzer")
        self.resize(1100, 750)
        self._create_data_directories()
        self._build_ui()

    @staticmethod
    def _create_data_directories() -> None:
        """Create the fixed project data layout when the application starts."""
        data_directories = (
            "raw_audio",
            "cleaned_audio",
            "fft_results",
            "layered_exports",
        )
        for directory_name in data_directories:
            Path("data", directory_name).mkdir(parents=True, exist_ok=True)

    def _build_ui(self) -> None:
        """Build the tabbed shell; feature-specific controls come later."""
        from gui.fft_analysis_tab import FftAnalysisTab
        from gui.layer_comparison_tab import LayerComparisonTab
        from gui.noise_reduction_tab import NoiseReductionTab

        tabs = QTabWidget()
        tabs.addTab(NoiseReductionTab(), "Noise reduction")
        tabs.addTab(FftAnalysisTab(), "FFT analysis")
        tabs.addTab(LayerComparisonTab(), "Layer comparison")
        self.setCentralWidget(tabs)


class PlaceholderTab(QWidget):
    """Temporary tab content used until its feature is implemented."""

    def __init__(self, title: str, description: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        heading = QLabel(title)
        heading.setStyleSheet("font-size: 22px; font-weight: 600;")
        message = QLabel(description)
        message.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(message)
        layout.addStretch()
