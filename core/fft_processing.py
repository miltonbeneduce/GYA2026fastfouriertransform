"""FFT calculation and export helpers for single-tone recordings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


@dataclass(frozen=True)
class FftResult:
	"""Frequency-domain data and metadata for one audio recording."""

	frequencies: np.ndarray
	amplitude_db: np.ndarray
	sample_rate: int
	sample_count: int


def calculate_fft(
	signal: np.ndarray,
	sample_rate: int,
	*,
	max_frequency: float = 5000.0,
) -> FftResult:
	"""Calculate a one-sided, Hann-windowed amplitude spectrum.

	The result is limited to ``max_frequency`` so the FFT view focuses on the
	frequency range relevant to the project's tone comparisons. Amplitudes are
	relative to the window-corrected signal and expressed in dBFS-like units;
	this makes peaks easy to compare between recordings.
	"""
	samples = np.asarray(signal, dtype=np.float64)
	if samples.ndim != 1 or samples.size < 2:
		raise ValueError("FFT analysis requires at least two mono samples.")
	if sample_rate <= 0:
		raise ValueError("Sample rate must be positive.")
	if max_frequency <= 0:
		raise ValueError("Maximum frequency must be positive.")

	window = np.hanning(samples.size)
	windowed_signal = samples * window
	spectrum = np.abs(np.fft.rfft(windowed_signal))
	frequencies = np.fft.rfftfreq(samples.size, d=1.0 / sample_rate)

	# Correct for the window's coherent gain and convert the one-sided spectrum
	# to amplitude. DC and Nyquist bins must not be doubled.
	coherent_gain = max(np.sum(window), np.finfo(np.float64).eps)
	amplitude = spectrum / coherent_gain
	if amplitude.size > 2:
		amplitude[1:-1] *= 2.0
	frequency_limit = min(float(max_frequency), sample_rate / 2.0)
	visible = frequencies <= frequency_limit
	amplitude_db = 20.0 * np.log10(np.maximum(amplitude, 1e-12))

	return FftResult(
		frequencies=frequencies[visible],
		amplitude_db=amplitude_db[visible],
		sample_rate=sample_rate,
		sample_count=samples.size,
	)


def save_fft_csv(path: str | Path, result: FftResult) -> Path:
	"""Save frequency and amplitude pairs as a UTF-8 CSV file."""
	output_path = Path(path)
	output_path.parent.mkdir(parents=True, exist_ok=True)
	data = np.column_stack((result.frequencies, result.amplitude_db))
	np.savetxt(
		output_path,
		data,
		delimiter=",",
		header="frequency_hz,amplitude_db",
		comments="",
	)
	return output_path


def save_fft_plot(path: str | Path, result: FftResult, title: str) -> Path:
	"""Save an FFT spectrum plot as a PNG file."""
	output_path = Path(path)
	output_path.parent.mkdir(parents=True, exist_ok=True)
	figure, axes = plt.subplots(figsize=(10, 5), constrained_layout=True)
	try:
		axes.plot(result.frequencies, result.amplitude_db, color="#3366cc", linewidth=1)
		axes.set_title(title)
		axes.set_xlabel("Frequency (Hz)")
		axes.set_ylabel("Amplitude (dB)")
		axes.set_xlim(0, min(5000, result.sample_rate / 2))
		axes.grid(True, alpha=0.25)
		figure.savefig(output_path, dpi=150)
	finally:
		plt.close(figure)
	return output_path
