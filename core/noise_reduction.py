"""Spectral noise-reduction algorithms that preserve tonal structure."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

# scipy is deliberately not used: Windows Smart App Control can block its
# unsigned DLLs (e.g. scipy/linalg/_flapack.pyd). The helpers below are
# numpy-only versions of the scipy functions this module used to call and
# give the same results (see tests/test_noise_reduction.py).


def _hann(nperseg: int) -> np.ndarray:
	"""Periodic Hann window, identical to scipy.signal.get_window("hann", n)."""
	return 0.5 - 0.5 * np.cos(2.0 * np.pi * np.arange(nperseg) / nperseg)


def _stft(samples: np.ndarray, nperseg: int, noverlap: int) -> np.ndarray:
	"""Like scipy.signal.stft(window="hann", boundary="zeros", padded=True)."""
	window = _hann(nperseg)
	step = nperseg - noverlap
	half = nperseg // 2
	padded = np.concatenate([np.zeros(half), samples, np.zeros(half)])
	extra = (-(padded.size - nperseg) % step) % nperseg
	padded = np.concatenate([padded, np.zeros(extra)])
	frames = sliding_window_view(padded, nperseg)[::step]
	return (np.fft.rfft(frames * window, axis=1) / window.sum()).T


def _istft(spectrum: np.ndarray, nperseg: int, noverlap: int) -> np.ndarray:
	"""Like scipy.signal.istft(window="hann", input_onesided=True, boundary=True)."""
	window = _hann(nperseg)
	step = nperseg - noverlap
	frames = np.fft.irfft(spectrum.T, n=nperseg, axis=1) * window.sum()
	length = nperseg + (frames.shape[0] - 1) * step
	output = np.zeros(length)
	norm = np.zeros(length)
	for index, frame in enumerate(frames):
		start = index * step
		output[start:start + nperseg] += frame * window
		norm[start:start + nperseg] += window**2
	half = nperseg // 2
	output, norm = output[half:length - half], norm[half:length - half]
	nonzero = norm > 1e-10
	output[nonzero] /= norm[nonzero]
	return output


def _maximum_filter_frequency(values: np.ndarray, size: int) -> np.ndarray:
	"""Like scipy.ndimage.maximum_filter(values, size=(size, 1), mode="nearest")."""
	before = size // 2
	after = size - 1 - before
	padded = np.pad(values, ((before, after), (0, 0)), mode="edge")
	return sliding_window_view(padded, size, axis=0).max(axis=-1)


def _gaussian_filter(values: np.ndarray, sigma: float) -> np.ndarray:
	"""Like scipy.ndimage.gaussian_filter(values, sigma, mode="nearest") for 2-D input."""
	radius = int(4.0 * sigma + 0.5)
	offsets = np.arange(-radius, radius + 1)
	kernel = np.exp(-0.5 * (offsets / sigma) ** 2)
	kernel /= kernel.sum()
	result = np.asarray(values, dtype=np.float64)
	for axis in range(result.ndim):
		pad = [(0, 0)] * result.ndim
		pad[axis] = (radius, radius)
		windows = sliding_window_view(np.pad(result, pad, mode="edge"), kernel.size, axis=axis)
		result = windows @ kernel
	return result


@dataclass(frozen=True)
class NoiseReductionResult:
	"""Processed signal and the parameters useful for an explanatory UI."""

	cleaned_signal: np.ndarray
	sample_rate: int
	noise_profile: np.ndarray
	nperseg: int


def reduce_stationary_noise(
	signal: np.ndarray,
	sample_rate: int,
	*,
	noise_fraction: float = 0.20,
	reduction_strength: float = 1.15,
	mask_floor: float = 0.20,
) -> NoiseReductionResult:
	"""Reduce background noise with a conservative spectral gate.

	The quietest STFT frames estimate the noise floor. Each frequency bin is
	then attenuated only when its magnitude is close to that floor. This is
	intentionally not a low-pass filter: all frequency bins remain available,
	and the soft mask floor prevents weak fundamentals, overtones, and
	undertones from being hard-cut from the recording.

	Args:
		signal: Mono floating-point samples.
		sample_rate: Samples per second.
		noise_fraction: Fraction of quietest frames used for noise estimation.
		reduction_strength: Multiplier for the estimated noise threshold.
		mask_floor: Minimum gain applied to any time-frequency bin.
	"""
	samples = np.asarray(signal, dtype=np.float64)
	if samples.ndim != 1 or samples.size == 0:
		raise ValueError("Noise reduction requires a non-empty mono signal.")
	if sample_rate <= 0:
		raise ValueError("Sample rate must be positive.")
	if not 0 < noise_fraction <= 1:
		raise ValueError("noise_fraction must be between 0 and 1.")
	if reduction_strength < 1:
		raise ValueError("reduction_strength must be at least 1.")
	if not 0 < mask_floor <= 1:
		raise ValueError("mask_floor must be between 0 and 1.")

	nperseg = min(2048, samples.size)
	noverlap = min(int(nperseg * 0.75), nperseg - 1)
	spectrum = _stft(samples, nperseg, noverlap)

	magnitudes = np.abs(spectrum)
	frame_energy = np.mean(magnitudes**2, axis=0)
	quiet_count = max(1, int(np.ceil(frame_energy.size * noise_fraction)))
	quiet_frames = np.argsort(frame_energy)[:quiet_count]
	noise_profile = np.median(magnitudes[:, quiet_frames], axis=1)

	threshold = reduction_strength * noise_profile[:, np.newaxis]
	excess = np.maximum(magnitudes - threshold, 0.0)
	mask = excess / (magnitudes + np.finfo(np.float64).eps)
	mask = np.maximum(mask, mask_floor)
	# A sustained note can be present in every frame, so it may also appear
	# in the quiet-frame estimate. Protect narrow, locally prominent peaks
	# before smoothing; this is the key safeguard for harmonics and undertones.
	local_frequency_peak = _maximum_filter_frequency(magnitudes, 5)
	frame_noise_baseline = np.median(magnitudes, axis=0, keepdims=True)
	tonal_peak = (
		(magnitudes >= local_frequency_peak * 0.55)
		& (magnitudes > frame_noise_baseline * 3.0)
	)
	mask = np.where(tonal_peak, 1.0, mask)
	# A small smoothing radius avoids musical-noise speckles without erasing
	# narrow tonal peaks, which is why the mask is not aggressively blurred.
	mask = _gaussian_filter(mask, 0.75)
	mask = np.clip(mask, mask_floor, 1.0)

	cleaned = _istft(spectrum * mask, nperseg, noverlap)
	cleaned_signal = np.asarray(cleaned[: samples.size], dtype=np.float64)
	if cleaned_signal.size < samples.size:
		cleaned_signal = np.pad(cleaned_signal, (0, samples.size - cleaned_signal.size))

	return NoiseReductionResult(
		cleaned_signal=cleaned_signal,
		sample_rate=sample_rate,
		noise_profile=noise_profile,
		nperseg=nperseg,
	)
