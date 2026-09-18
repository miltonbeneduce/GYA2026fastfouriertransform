"""User interface for the independent FFT-analysis workflow."""

from __future__ import annotations

from gui.main_window import PlaceholderTab


class FftAnalysisTab(PlaceholderTab):
    """Placeholder for single-tone FFT analysis and export."""

    def __init__(self) -> None:
        super().__init__(
            "FFT analysis",
            "This independent workflow will calculate and export a frequency "
            "spectrum for one recorded tone.",
        )
