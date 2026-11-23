"""Tests for core.note_recording (note lists, trimming and FLAC export)."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from core import note_recording as rec


class NoteListTest(unittest.TestCase):
    def test_note_names(self):
        self.assertEqual(rec.midi_to_name(60), "C4")
        self.assertEqual(rec.midi_to_name(21), "A0")
        self.assertEqual(rec.name_to_midi("A4"), 69)
        self.assertEqual(rec.name_to_midi("c8"), 108)
        self.assertEqual(rec.name_to_midi("Bb3"), rec.name_to_midi("A#3"))
        with self.assertRaises(ValueError):
            rec.name_to_midi("H3")

    def test_piano(self):
        items = rec.piano_notes(rec.name_to_midi("A0"), rec.name_to_midi("C8"))
        self.assertEqual(len(items), 88)
        self.assertEqual(items[0].filename, "piano_A0_021.flac")
        self.assertIn("piano_A4_069.flac", [item.filename for item in items])
        self.assertEqual(items[-1].filename, "piano_C8_108.flac")

    def test_guitar(self):
        items = rec.guitar_notes()
        self.assertEqual(len(items), 78)
        self.assertEqual(items[0].filename, "guitar_string6_fret00_E2_040.flac")
        self.assertEqual(items[3].filename, "guitar_string6_fret03_G2_043.flac")
        self.assertEqual(items[-1].filename, "guitar_string1_fret12_E5_076.flac")
        self.assertEqual(len({item.filename for item in items}), 78)

    def test_custom(self):
        items = rec.custom_notes("Elbas Fender", 28, 30)
        self.assertEqual(
            [item.filename for item in items],
            ["elbas_fender_E1_028.flac", "elbas_fender_F1_029.flac", "elbas_fender_F#1_030.flac"],
        )

    def test_folder_name(self):
        self.assertEqual(rec.safe_folder_name("Eriks gitarr"), "Eriks gitarr")
        self.assertEqual(rec.safe_folder_name("  Åsas piano 2026 "), "Åsas piano 2026")
        self.assertEqual(rec.safe_folder_name("a/b:c?"), "a_b_c_")
        self.assertEqual(rec.safe_folder_name("   "), "recordings")
        self.assertEqual(rec.safe_folder_name("name..."), "name")


class ProcessingTest(unittest.TestCase):
    def test_trim_and_fade(self):
        sr = rec.SAMPLE_RATE
        t = np.arange(sr) / sr
        tone = 0.5 * np.sin(2 * np.pi * 440 * t) * np.exp(-3 * t)
        raw = np.random.default_rng(0).normal(0, 1e-4, size=len(tone) + 2 * sr)
        onset = sr // 2
        raw[onset:onset + len(tone)] += tone

        out = rec.process_take(raw.astype(np.float32), sr, threshold_db=-40)

        # Starts at most 5 ms before the attack
        first_loud = np.flatnonzero(np.abs(out) >= rec.from_db(-40))[0]
        self.assertLessEqual(first_loud, int(sr * 0.005) + 1)
        # Trailing silence removed (tone + at most 0.3 s tail + margin)
        self.assertLess(len(out), len(tone) + int(0.35 * sr))
        # Last sample faded to zero
        self.assertAlmostEqual(float(out[-1]), 0.0, places=6)

    def test_save_flac(self):
        sr = rec.SAMPLE_RATE
        signal = (0.3 * np.sin(np.linspace(0, 200, sr))).astype(np.float32)
        with tempfile.TemporaryDirectory() as directory:
            path = rec.save_flac(Path(directory) / "sub" / "x.flac", signal, sr)
            info = sf.info(str(path))
            self.assertEqual(
                (info.samplerate, info.channels, info.format, info.subtype),
                (48000, 1, "FLAC", "PCM_24"),
            )


class RecorderStateTest(unittest.TestCase):
    """Feeds synthetic audio blocks through the recorder callback without a real device."""

    def test_attack_and_silence_detection(self):
        class DummyStream:
            def __init__(self, **kwargs): pass
            def start(self): pass
            def stop(self): pass
            def close(self): pass

        original_stream = rec.sd.InputStream
        rec.sd.InputStream = DummyStream
        try:
            recorder = rec.Recorder(None)
        finally:
            rec.sd.InputStream = original_stream

        sr = rec.SAMPLE_RATE
        n = np.arange(sr)
        note = 0.3 * np.sin(2 * np.pi * 220 * n / sr) * np.exp(-2 * n / sr)
        signal = np.concatenate([np.zeros(sr), note, np.zeros(3 * sr)]).astype(np.float32)

        recorder.arm(threshold_db=-40, silence_seconds=1.0, max_seconds=15)
        states = []
        for start in range(0, len(signal), rec.BLOCK_SIZE):
            block = signal[start:start + rec.BLOCK_SIZE].reshape(-1, 1)
            recorder._callback(block, len(block), None, None)
            if not states or states[-1] != recorder.state:
                states.append(recorder.state)

        self.assertEqual(states, [rec.WAITING, rec.RECORDING, rec.DONE])
        raw = recorder.take_result()
        self.assertIsNotNone(raw)
        self.assertEqual(recorder.state, rec.IDLE)
        # Pre-buffer (0.2 s) + note (~1 s) + 1 s of silence before stopping
        self.assertAlmostEqual(len(raw) / sr, 2.2, delta=0.1)


if __name__ == "__main__":
    unittest.main()
