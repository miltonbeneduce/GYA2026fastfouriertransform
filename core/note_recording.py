"""Single-note recording: note lists, onset/silence detection, trimming and FLAC export.

The recorder keeps one input stream open. For each note it waits until the
signal level crosses a threshold (the attack), records until the note has
decayed below the threshold for a while, and then trims the take so that the
file starts at the attack and ends with a short fade-out. No normalisation is
applied, so the natural dynamics between notes are kept for later analysis.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
import re
import threading

import numpy as np
import sounddevice as sd
import soundfile as sf

SAMPLE_RATE = 48000
BLOCK_SIZE = 480            # 10 ms at 48 kHz
PREBUFFER_SECONDS = 0.2     # Audio kept from before the attack is detected
STOP_HYSTERESIS_DB = 6.0    # "Silence" means level below threshold minus this
DB_FLOOR = -100.0

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Standard guitar tuning from the low E string (string 6) to the high E string (string 1).
GUITAR_STANDARD_TUNING = [(6, "E", 40), (5, "A", 45), (4, "D", 50), (3, "G", 55), (2, "B", 59), (1, "E", 64)]
GUITAR_FRETS = range(0, 13)

# Recorder states
IDLE, WAITING, RECORDING, DONE, MEASURING = "idle", "waiting", "recording", "done", "measuring"


# --------------------------------------------------------------------------- notes

@dataclass(frozen=True)
class NoteItem:
    midi: int
    display: str   # Large text shown to the player
    filename: str  # File name without directory


def midi_to_name(midi: int) -> str:
    """60 -> 'C4', 69 -> 'A4', 21 -> 'A0'."""
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


def name_to_midi(name: str) -> int:
    """'C4' -> 60, 'A#3' -> 58, 'Bb3' -> 58. Raises ValueError for invalid names."""
    match = re.fullmatch(r"\s*([A-Ga-g])([#b]?)(-?\d+)\s*", name)
    if not match:
        raise ValueError(f"Invalid note name: {name!r}")
    letter, accidental, octave = match.groups()
    midi = NOTE_NAMES.index(letter.upper()) + (int(octave) + 1) * 12
    if accidental == "#":
        midi += 1
    elif accidental == "b":
        midi -= 1
    if not 0 <= midi <= 127:
        raise ValueError(f"The note {name!r} is outside the MIDI range")
    return midi


def safe_prefix(name: str) -> str:
    """Make an instrument name safe to use as a file name prefix."""
    cleaned = re.sub(r"[^\w\-]+", "_", name.strip().lower(), flags=re.UNICODE).strip("_")
    return cleaned or "instrument"


def safe_folder_name(name: str) -> str:
    """Keep the folder name as typed (spaces, å/ä/ö) but remove characters Windows forbids."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", name).strip().rstrip(". ")
    return cleaned or "recordings"


def range_notes(prefix: str, low: int, high: int) -> list[NoteItem]:
    if low > high:
        low, high = high, low
    return [
        NoteItem(midi, midi_to_name(midi), f"{prefix}_{midi_to_name(midi)}_{midi:03d}.flac")
        for midi in range(low, high + 1)
    ]


def piano_notes(low: int = 21, high: int = 108) -> list[NoteItem]:
    return range_notes("piano", low, high)


def guitar_notes() -> list[NoteItem]:
    """Every string in standard tuning, frets 0-12, string by string from the low E."""
    items = []
    for string_number, string_name, open_midi in GUITAR_STANDARD_TUNING:
        for fret in GUITAR_FRETS:
            midi = open_midi + fret
            name = midi_to_name(midi)
            items.append(NoteItem(
                midi,
                f"String {string_number} ({string_name}) – Fret {fret}  →  {name}",
                f"guitar_string{string_number}_fret{fret:02d}_{name}_{midi:03d}.flac",
            ))
    return items


def custom_notes(instrument_name: str, low: int, high: int) -> list[NoteItem]:
    return range_notes(safe_prefix(instrument_name), low, high)


# --------------------------------------------------------------------------- processing

def to_db(value: float) -> float:
    return 20.0 * float(np.log10(value)) if value > 1e-10 else DB_FLOOR


def from_db(db: float) -> float:
    return 10.0 ** (db / 20.0)


def block_rms_db(audio: np.ndarray, block: int = BLOCK_SIZE) -> np.ndarray:
    """RMS level in dBFS for each block (the last partial block is zero-padded)."""
    block_count = int(np.ceil(len(audio) / block))
    padded = np.zeros(block_count * block, dtype=np.float64)
    padded[: len(audio)] = audio
    rms = np.sqrt(np.mean(padded.reshape(block_count, block) ** 2, axis=1))
    return 20.0 * np.log10(np.maximum(rms, 1e-10))


def process_take(
    audio: np.ndarray,
    sample_rate: int,
    threshold_db: float,
    pre_ms: float = 5.0,
    tail_keep_seconds: float = 0.3,
    fade_ms: float = 50.0,
) -> np.ndarray:
    """Trim silence before the attack and after the decay, then apply a fade-out."""
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    if len(audio) == 0:
        return audio

    # Start: first sample whose amplitude reaches the threshold, minus a small margin.
    above = np.flatnonzero(np.abs(audio) >= from_db(threshold_db))
    onset = int(above[0]) if len(above) else 0
    start = max(0, onset - int(sample_rate * pre_ms / 1000))

    # End: the last block that is still audible, plus a little of the decay.
    levels = block_rms_db(audio)
    loud = np.flatnonzero(levels >= threshold_db - STOP_HYSTERESIS_DB)
    last_loud_end = (int(loud[-1]) + 1) * BLOCK_SIZE if len(loud) else len(audio)
    end = min(len(audio), last_loud_end + int(sample_rate * tail_keep_seconds))
    end = max(end, start + 1)

    trimmed = audio[start:end].copy()

    fade_length = min(len(trimmed), int(sample_rate * fade_ms / 1000))
    if fade_length > 0:
        fade = 0.5 * (1.0 + np.cos(np.linspace(0.0, np.pi, fade_length)))  # cosine 1 -> 0
        trimmed[-fade_length:] *= fade.astype(np.float32)
    return trimmed


def save_flac(path: str | Path, audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> Path:
    """Write a mono 24-bit FLAC file and return its path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), np.clip(audio, -1.0, 1.0), sample_rate, subtype="PCM_24", format="FLAC")
    return output_path


# --------------------------------------------------------------------------- devices

def list_input_devices() -> list[tuple[int, str]]:
    """Return [(device index, display name)] for every input device."""
    host_apis = sd.query_hostapis()
    devices = []
    for index, device in enumerate(sd.query_devices()):
        if device["max_input_channels"] > 0:
            api_name = host_apis[device["hostapi"]]["name"]
            devices.append((index, f"{device['name']}  [{api_name}]"))
    return devices


def default_input_device() -> int | None:
    try:
        device = sd.default.device[0]
        return int(device) if device is not None and device >= 0 else None
    except Exception:
        return None


def play(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> None:
    sd.stop()
    sd.play(audio, sample_rate)


def stop_playback() -> None:
    sd.stop()


# --------------------------------------------------------------------------- recorder

class Recorder:
    """Keeps an input stream open and detects attacks and silence in the audio thread."""

    def __init__(self, device: int | None, sample_rate: int = SAMPLE_RATE) -> None:
        self.sample_rate = sample_rate
        self._lock = threading.Lock()
        self.state = IDLE
        self.level_db = DB_FLOOR
        self.peak = 0.0
        self._prebuffer: deque[np.ndarray] = deque(maxlen=int(PREBUFFER_SECONDS * sample_rate / BLOCK_SIZE))
        self._chunks: list[np.ndarray] = []
        self._recorded = 0
        self._silent = 0
        self._threshold_db = -40.0
        self._silence_samples = sample_rate
        self._max_samples = 15 * sample_rate
        self._measure_levels: list[float] = []
        self._measure_samples = 0
        self.stream = sd.InputStream(
            device=device,
            channels=1,
            samplerate=sample_rate,
            blocksize=BLOCK_SIZE,
            dtype="float32",
            callback=self._callback,
        )
        self.stream.start()

    def close(self) -> None:
        try:
            self.stream.stop()
            self.stream.close()
        except Exception:
            pass

    # Control from the GUI thread -------------------------------------------

    def arm(self, threshold_db: float, silence_seconds: float, max_seconds: float) -> None:
        """Wait for the next attack and record one note."""
        with self._lock:
            self._threshold_db = threshold_db
            self._silence_samples = int(silence_seconds * self.sample_rate)
            self._max_samples = int(max_seconds * self.sample_rate)
            self._prebuffer.clear()
            self._chunks = []
            self._recorded = 0
            self._silent = 0
            self.state = WAITING

    def disarm(self) -> None:
        with self._lock:
            self.state = IDLE
            self._chunks = []

    def start_measure(self, seconds: float = 2.0) -> None:
        """Measure the room noise level for a few seconds."""
        with self._lock:
            self._measure_levels = []
            self._measure_samples = int(seconds * self.sample_rate)
            self.state = MEASURING

    def take_result(self) -> np.ndarray | None:
        """Return the finished take (when state is DONE) and go back to IDLE."""
        with self._lock:
            if self.state != DONE:
                return None
            audio = np.concatenate(self._chunks) if self._chunks else np.zeros(0, np.float32)
            self._chunks = []
            self.state = IDLE
            return audio

    def measure_result(self) -> float | None:
        """Noise level in dBFS (median of block RMS levels) once measuring is done."""
        with self._lock:
            if self.state != DONE or not self._measure_levels:
                return None
            value = float(np.median(self._measure_levels))
            self._measure_levels = []
            self.state = IDLE
            return value

    # Audio thread -----------------------------------------------------------

    def _callback(self, indata, frames, time_info, status) -> None:
        block = indata[:, 0].copy()
        rms = float(np.sqrt(np.mean(block.astype(np.float64) ** 2)))
        level = to_db(rms)
        self.level_db = level
        self.peak = max(self.peak * 0.95, float(np.max(np.abs(block))) if len(block) else 0.0)

        with self._lock:
            if self.state == WAITING:
                if level >= self._threshold_db:
                    self._chunks = list(self._prebuffer)
                    self._chunks.append(block)
                    self._recorded = len(block)
                    self._silent = 0
                    self.state = RECORDING
                else:
                    self._prebuffer.append(block)
            elif self.state == RECORDING:
                self._chunks.append(block)
                self._recorded += len(block)
                if level < self._threshold_db - STOP_HYSTERESIS_DB:
                    self._silent += len(block)
                else:
                    self._silent = 0
                if self._silent >= self._silence_samples or self._recorded >= self._max_samples:
                    self.state = DONE
            elif self.state == MEASURING:
                self._measure_levels.append(level)
                self._measure_samples -= len(block)
                if self._measure_samples <= 0:
                    self.state = DONE
