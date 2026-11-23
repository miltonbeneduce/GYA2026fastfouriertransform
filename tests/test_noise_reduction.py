"""Tests for the numpy-only signal helpers in core.noise_reduction and for core.audio_io.

The comparisons against scipy are skipped when scipy is not installed (it is
no longer a dependency, because Smart App Control can block its DLLs).
"""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from core import noise_reduction as nr
from core.audio_io import load_audio

try:
    import scipy.ndimage
    import scipy.signal
except Exception:  # not installed, or blocked by Smart App Control
    scipy = None


def test_signal(n=48000, sr=48000):
    rng = np.random.default_rng(1)
    t = np.arange(n) / sr
    return np.sin(2 * np.pi * 220 * t) + 0.3 * np.sin(2 * np.pi * 660 * t) + 0.05 * rng.standard_normal(n)


class NumpyHelpersTest(unittest.TestCase):
    def test_stft_istft_round_trip(self):
        x = test_signal(10007)
        for nperseg in (2048, 1000, 7):
            noverlap = min(int(nperseg * 0.75), nperseg - 1)
            y = nr._istft(nr._stft(x, nperseg, noverlap), nperseg, noverlap)
            np.testing.assert_allclose(y[: x.size], x, atol=1e-9)

    def test_reduce_noise_keeps_length(self):
        x = test_signal(30000)
        result = nr.reduce_stationary_noise(x, 48000)
        self.assertEqual(result.cleaned_signal.shape, x.shape)
        self.assertTrue(np.all(np.isfinite(result.cleaned_signal)))


@unittest.skipIf(scipy is None, "scipy is not available")
class MatchesScipyTest(unittest.TestCase):
    def test_stft_and_istft(self):
        x = test_signal(10007)
        for nperseg in (2048, 1000, 7):
            noverlap = min(int(nperseg * 0.75), nperseg - 1)
            _, _, expected = scipy.signal.stft(
                x, window="hann", nperseg=nperseg, noverlap=noverlap, boundary="zeros", padded=True
            )
            spectrum = nr._stft(x, nperseg, noverlap)
            np.testing.assert_allclose(spectrum, expected, atol=1e-12)

            modified = spectrum * np.linspace(0.2, 1.0, spectrum.shape[0])[:, None]
            _, expected_signal = scipy.signal.istft(
                modified, window="hann", nperseg=nperseg, noverlap=noverlap, input_onesided=True
            )
            np.testing.assert_allclose(nr._istft(modified, nperseg, noverlap), expected_signal, atol=1e-10)

    def test_filters(self):
        values = np.random.default_rng(2).random((40, 30))
        np.testing.assert_allclose(
            nr._maximum_filter_frequency(values, 5),
            scipy.ndimage.maximum_filter(values, size=(5, 1), mode="nearest"),
        )
        np.testing.assert_allclose(
            nr._gaussian_filter(values, 0.75),
            scipy.ndimage.gaussian_filter(values, sigma=(0.75, 0.75), mode="nearest"),
            atol=1e-12,
        )


class LoadAudioTest(unittest.TestCase):
    def test_stereo_flac_becomes_mono(self):
        left = test_signal(4800)
        right = np.zeros_like(left)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "stereo.flac"
            sf.write(path, np.column_stack([left, right]) * 0.5, 44100, subtype="PCM_24")
            signal, sample_rate = load_audio(path)
        self.assertEqual(sample_rate, 44100)
        self.assertEqual(signal.ndim, 1)
        np.testing.assert_allclose(signal, left * 0.25, atol=1e-5)


if __name__ == "__main__":
    unittest.main()
