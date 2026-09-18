"""Loading and exporting overlaid FFT spectrum layers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


@dataclass(frozen=True)
class FftLayer:
	"""One saved FFT CSV with a display label."""

	label: str
	frequencies: np.ndarray
	amplitude_db: np.ndarray


def load_fft_csv(path: str | Path) -> FftLayer:
	"""Load a saved FFT CSV containing frequency and dB amplitude columns."""
	input_path = Path(path)
	if not input_path.is_file():
		raise FileNotFoundError(f"FFT result not found: {input_path}")

	try:
		data = np.loadtxt(input_path, delimiter=",", skiprows=1)
	except (OSError, ValueError) as error:
		raise ValueError(f"Could not read FFT CSV '{input_path.name}': {error}") from error

	if data.ndim == 1:
		data = data.reshape(1, -1)
	if data.shape[1] != 2 or data.shape[0] == 0:
		raise ValueError("FFT CSV must contain frequency_hz and amplitude_db columns.")
	if not np.isfinite(data).all():
		raise ValueError(f"FFT CSV contains invalid numeric values: {input_path.name}")

	return FftLayer(
		label=input_path.stem,
		frequencies=data[:, 0],
		amplitude_db=data[:, 1],
	)


def save_layered_plot(
	path: str | Path,
	layers: list[FftLayer],
	visible_layers: set[str] | None = None,
	*,
	title: str = "Layered FFT comparison",
) -> Path:
	"""Save visible FFT layers as one labelled PNG plot."""
	if not layers:
		raise ValueError("At least one FFT layer is required for export.")

	output_path = Path(path)
	output_path.parent.mkdir(parents=True, exist_ok=True)
	figure, axes = plt.subplots(figsize=(10, 5), constrained_layout=True)
	try:
		colors = plt.get_cmap("tab10")(np.linspace(0, 1, max(len(layers), 2)))
		plotted = 0
		for index, layer in enumerate(layers):
			if visible_layers is not None and layer.label not in visible_layers:
				continue
			axes.plot(
				layer.frequencies,
				layer.amplitude_db,
				label=layer.label,
				color=colors[index],
				linewidth=1,
			)
			plotted += 1
		if plotted == 0:
			raise ValueError("At least one FFT layer must be visible for export.")
		axes.set_title(title)
		axes.set_xlabel("Frequency (Hz)")
		axes.set_ylabel("Amplitude (dB)")
		axes.set_xlim(0, 5000)
		axes.grid(True, alpha=0.25)
		axes.legend()
		figure.savefig(output_path, dpi=150)
	finally:
		plt.close(figure)
	return output_path