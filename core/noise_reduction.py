"""Spectral noise-reduction algorithms that preserve tonal structure."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import gaussian_filter, maximum_filter
from scipy.signal import istft, stft


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
	frequencies, times, spectrum = stft(
		samples,
		fs=sample_rate,
		window="hann",
		nperseg=nperseg,
		noverlap=noverlap,
		boundary="zeros",
		padded=True,
	)
	del frequencies, times

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
	local_frequency_peak = maximum_filter(magnitudes, size=(5, 1), mode="nearest")
	frame_noise_baseline = np.median(magnitudes, axis=0, keepdims=True)
	tonal_peak = (
		(magnitudes >= local_frequency_peak * 0.55)
		& (magnitudes > frame_noise_baseline * 3.0)
	)
	mask = np.where(tonal_peak, 1.0, mask)
	# A small smoothing radius avoids musical-noise speckles without erasing
	# narrow tonal peaks, which is why the mask is not aggressively blurred.
	mask = gaussian_filter(mask, sigma=(0.75, 0.75), mode="nearest")
	mask = np.clip(mask, mask_floor, 1.0)

	_, cleaned = istft(
		spectrum * mask,
		fs=sample_rate,
		window="hann",
		nperseg=nperseg,
		noverlap=noverlap,
		input_onesided=True,
	)
	cleaned_signal = np.asarray(cleaned[: samples.size], dtype=np.float64)
	if cleaned_signal.size < samples.size:
		cleaned_signal = np.pad(cleaned_signal, (0, samples.size - cleaned_signal.size))

	return NoiseReductionResult(
		cleaned_signal=cleaned_signal,
		sample_rate=sample_rate,
		noise_profile=noise_profile,
		nperseg=nperseg,
	)
