"""User interface for the independent layer-comparison workflow."""

from __future__ import annotations

from gui.main_window import PlaceholderTab


class LayerComparisonTab(PlaceholderTab):
    """Placeholder for loading, toggling, and exporting FFT layers."""

    def __init__(self) -> None:
        super().__init__(
            "Layer comparison",
            "This independent workflow will overlay saved FFT result files and "
            "export the combined view.",
        )
