"""Audio file loading and writing helpers."""

from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np
import soundfile as sf


def load_audio(path: str | Path) -> tuple[np.ndarray, int]:
	"""Load an audio file as a mono floating-point signal and sample rate.

	``librosa`` is used here because it can decode the WAV, FLAC, and MP3
	formats accepted by the application. Keeping the original sample rate is
	important: resampling would change the frequency positions shown later.
	"""
	audio_path = Path(path)
	if not audio_path.is_file():
		raise FileNotFoundError(f"Audio file not found: {audio_path}")

	signal, sample_rate = librosa.load(audio_path, sr=None, mono=True)
	if signal.size == 0:
		raise ValueError("The selected audio file contains no samples.")
	return signal.astype(np.float64, copy=False), int(sample_rate)


def save_wav(path: str | Path, signal: np.ndarray, sample_rate: int) -> Path:
	"""Write a floating-point signal to a WAV file and return its path."""
	output_path = Path(path)
	output_path.parent.mkdir(parents=True, exist_ok=True)
	sf.write(output_path, np.asarray(signal, dtype=np.float32), sample_rate)
	return output_path
