"""Main application window and shared directory initialization."""

from __future__ import annotations

import importlib
from pathlib import Path
import traceback

from PySide6.QtWidgets import QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget


class MainWindow(QMainWindow):
    """Top-level window containing one independent tab per analysis feature."""

    # (tab title, module, class). Tabs are loaded one by one so that a tab whose
    # dependencies fail to load (for example a DLL blocked by Windows Smart App
    # Control) shows an error message instead of stopping the whole program.
    TABS = (
        ("Note recorder", "gui.note_recorder_tab", "NoteRecorderTab"),
        ("Noise reduction", "gui.noise_reduction_tab", "NoiseReductionTab"),
        ("FFT analysis", "gui.fft_analysis_tab", "FftAnalysisTab"),
        ("Layer comparison", "gui.layer_comparison_tab", "LayerComparisonTab"),
    )

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
        tabs = QTabWidget()
        for title, module_name, class_name in self.TABS:
            tabs.addTab(self._load_tab(title, module_name, class_name), title)
        self.setCentralWidget(tabs)

    @staticmethod
    def _load_tab(title: str, module_name: str, class_name: str) -> QWidget:
        """Create one tab, or an error tab if it cannot be imported or created."""
        try:
            module = importlib.import_module(module_name)
            return getattr(module, class_name)()
        except Exception as error:  # noqa: BLE001 - any failure should only affect this tab
            traceback.print_exc()
            return PlaceholderTab(
                f"{title} could not be loaded",
                f"{type(error).__name__}: {error}\n\n"
                "If Windows reports that a file (DLL/.pyd) was blocked, Smart App Control "
                "stopped one of this tab's Python packages. The other tabs still work.",
            )


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
