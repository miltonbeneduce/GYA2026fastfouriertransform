"""User interface for recording single notes one at a time.

The tab shows which note to play, starts recording automatically at the attack,
stops when the note has decayed and saves a trimmed FLAC file in
``data/raw_audio/<folder name>/``. The files can then be opened directly in the
FFT analysis tab.

Before each note a short countdown runs, so that the click from pressing a
button (mouse or keyboard) is not picked up as the attack of the note.

Keyboard: Space = next note, R = retake, L = listen to the last take.
"""

from __future__ import annotations

from pathlib import Path
import math
import time

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from core import note_recording as rec

RECORDINGS_ROOT = Path("data", "raw_audio")
INSTRUMENTS = ["Piano", "Guitar (standard tuning, frets 0–12)", "Custom instrument"]
DEFAULT_FOLDERS = {INSTRUMENTS[0]: "piano", INSTRUMENTS[1]: "guitar"}
METER_MIN_DB = -80.0
POLL_MS = 30

# Session modes
OFF, WAITING, RECORDING, SAVED, FINISHED, MEASURING, COUNTDOWN = range(7)
SESSION_MODES = (COUNTDOWN, WAITING, RECORDING, SAVED, FINISHED)


class LevelMeter(QWidget):
    """Horizontal input level meter with a peak marker and a threshold line."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(26)
        self.level_db = rec.DB_FLOOR
        self.peak = 0.0
        self.threshold_db = -40.0
        self.active = False

    def set_values(self, level_db: float, peak: float, threshold_db: float, active: bool) -> None:
        self.level_db, self.peak, self.threshold_db, self.active = level_db, peak, threshold_db, active
        self.update()

    def _x(self, db: float) -> int:
        clamped = max(METER_MIN_DB, min(0.0, db))
        return int(self.width() * (clamped - METER_MIN_DB) / -METER_MIN_DB)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#222222"))
        if self.active:
            peak_db = rec.to_db(self.peak)
            if self.peak >= 0.99:
                color = "#c01c28"
            elif peak_db > -6:
                color = "#e5a50a"
            else:
                color = "#2ec27e"
            painter.fillRect(0, 0, self._x(self.level_db), self.height(), QColor(color))
            painter.setPen(QPen(QColor("white"), 1))
            painter.drawLine(self._x(peak_db), 0, self._x(peak_db), self.height())
        painter.setPen(QPen(QColor("#ff4d4d"), 2))
        threshold_x = self._x(self.threshold_db)
        painter.drawLine(threshold_x, 0, threshold_x, self.height())
        painter.end()


class NoteRecorderTab(QWidget):
    """Guided recording of every note on an instrument, one FLAC file per note."""

    def __init__(self) -> None:
        super().__init__()
        self.recorder: rec.Recorder | None = None
        self.items: list[rec.NoteItem] = []
        self.index = 0
        self.mode = OFF
        self.mode_before_measure = OFF
        self.measure_owns_stream = False
        self.last_take: np.ndarray | None = None
        self.output_dir = RECORDINGS_ROOT
        self.countdown_end = 0.0
        self._auto_folder = DEFAULT_FOLDERS[INSTRUMENTS[0]]

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout = QVBoxLayout(self)
        layout.addWidget(self._build_settings())
        layout.addLayout(self._build_session())

        for key, handler in (("Space", self.next_note), ("R", self.retake), ("L", self.listen)):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(handler)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll)
        self.timer.start(POLL_MS)

        application = QApplication.instance()
        if application is not None:
            application.aboutToQuit.connect(self._close_stream)

        self._update_instrument_fields()
        self._update_buttons()

    # ------------------------------------------------------------------ layout

    def _build_settings(self) -> QGroupBox:
        self.settings_box = QGroupBox("Settings")
        form = QFormLayout(self.settings_box)

        self.instrument_combo = QComboBox()
        self.instrument_combo.addItems(INSTRUMENTS)
        self.instrument_combo.currentTextChanged.connect(self._update_instrument_fields)
        form.addRow("Instrument:", self.instrument_combo)

        self.custom_name_edit = QLineEdit("bass")
        self.custom_name_edit.textChanged.connect(self._update_folder_default)
        form.addRow("Instrument name (custom):", self.custom_name_edit)

        self.low_edit = QLineEdit("A0")
        self.high_edit = QLineEdit("C8")
        for edit in (self.low_edit, self.high_edit):
            edit.setMaximumWidth(70)
        range_row = QHBoxLayout()
        range_row.addWidget(self.low_edit)
        range_row.addWidget(QLabel("–"))
        range_row.addWidget(self.high_edit)
        hint = QLabel("e.g. A0–C8 = 88 piano keys, E1–G3 for a bass")
        hint.setStyleSheet("color: gray;")
        range_row.addWidget(hint)
        range_row.addStretch()
        form.addRow("Lowest / highest note:", range_row)

        self.device_combo = QComboBox()
        self.devices = rec.list_input_devices()
        default_device = rec.default_input_device()
        for device_index, name in self.devices:
            self.device_combo.addItem(name, device_index)
            if device_index == default_device:
                self.device_combo.setCurrentIndex(self.device_combo.count() - 1)
        form.addRow("Microphone:", self.device_combo)

        self.folder_edit = QLineEdit(self._auto_folder)
        self.folder_edit.setPlaceholderText("e.g. Eriks gitarr")
        self.folder_edit.textChanged.connect(self._update_folder_hint)
        self.folder_hint = QLabel()
        self.folder_hint.setStyleSheet("color: gray;")
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder_edit, stretch=1)
        folder_row.addWidget(self.folder_hint)
        form.addRow("Folder name:", folder_row)
        self._update_folder_hint()

        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(-70, -10)
        self.threshold_slider.setValue(-40)
        self.threshold_label = QLabel()
        self.threshold_slider.valueChanged.connect(
            lambda value: self.threshold_label.setText(f"{value} dBFS"))
        self.threshold_label.setText("-40 dBFS")
        self.threshold_label.setMinimumWidth(70)
        self.measure_button = QPushButton("Measure noise (stay quiet 2 s)")
        self.measure_button.clicked.connect(self.measure_noise)
        threshold_row = QHBoxLayout()
        threshold_row.addWidget(self.threshold_slider, stretch=1)
        threshold_row.addWidget(self.threshold_label)
        threshold_row.addWidget(self.measure_button)
        form.addRow("Attack threshold:", threshold_row)

        self.silence_spin = QDoubleSpinBox()
        self.silence_spin.setRange(0.2, 5.0)
        self.silence_spin.setSingleStep(0.1)
        self.silence_spin.setValue(1.0)
        self.silence_spin.setSuffix(" s")
        self.max_length_spin = QDoubleSpinBox()
        self.max_length_spin.setRange(1.0, 60.0)
        self.max_length_spin.setSingleStep(1.0)
        self.max_length_spin.setValue(15.0)
        self.max_length_spin.setSuffix(" s")
        timing_row = QHBoxLayout()
        timing_row.addWidget(self.silence_spin)
        timing_row.addWidget(QLabel("   Max length per note:"))
        timing_row.addWidget(self.max_length_spin)
        timing_row.addStretch()
        form.addRow("Silence before stop:", timing_row)

        self.countdown_spin = QDoubleSpinBox()
        self.countdown_spin.setRange(0.0, 10.0)
        self.countdown_spin.setSingleStep(0.5)
        self.countdown_spin.setDecimals(1)
        self.countdown_spin.setValue(3.0)
        self.countdown_spin.setSuffix(" s")
        countdown_hint = QLabel("before each note, so the click of the button is not recorded (0 = off)")
        countdown_hint.setStyleSheet("color: gray;")
        countdown_row = QHBoxLayout()
        countdown_row.addWidget(self.countdown_spin)
        countdown_row.addWidget(countdown_hint)
        countdown_row.addStretch()
        form.addRow("Countdown:", countdown_row)
        return self.settings_box

    def _build_session(self) -> QVBoxLayout:
        layout = QVBoxLayout()

        top_row = QHBoxLayout()
        self.start_button = QPushButton()
        self.start_button.clicked.connect(self.start_or_stop)
        self.progress_label = QLabel()
        top_row.addWidget(self.start_button)
        top_row.addStretch()
        top_row.addWidget(self.progress_label)
        layout.addLayout(top_row)

        self.note_label = QLabel("—")
        self.note_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_note_font(large=True)
        self.file_label = QLabel()
        self.file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_label.setStyleSheet("color: gray;")
        self.status_label = QLabel("Choose the settings and press Start session.")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.note_label)
        layout.addWidget(self.file_label)
        layout.addWidget(self.status_label)

        self.meter = LevelMeter()
        self.meter_text = QLabel()
        self.meter_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.meter_text.setStyleSheet("color: gray;")
        layout.addWidget(self.meter)
        layout.addWidget(self.meter_text)

        button_row = QHBoxLayout()
        self.listen_button = QPushButton("Listen (L)")
        self.retake_button = QPushButton("Retake (R)")
        self.skip_button = QPushButton("Skip")
        self.next_button = QPushButton("Next (Space)")
        self.listen_button.clicked.connect(self.listen)
        self.retake_button.clicked.connect(self.retake)
        self.skip_button.clicked.connect(self.skip)
        self.next_button.clicked.connect(self.next_note)
        button_row.addStretch()
        for button in (self.listen_button, self.retake_button, self.skip_button, self.next_button):
            # Buttons must not take focus, otherwise Space would also "click" them.
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button_row.addWidget(button)
        button_row.addStretch()
        self.start_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.measure_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addLayout(button_row)
        layout.addStretch()
        return layout

    def _set_note_font(self, large: bool) -> None:
        size = 56 if large else 28
        self.note_label.setStyleSheet(f"font-size: {size}px; font-weight: 700; margin-top: 12px;")

    def _status(self, text: str, color: str = "palette(text)") -> None:
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"font-size: 16px; color: {color}; margin: 10px;")

    # ------------------------------------------------------------- settings logic

    def _update_instrument_fields(self) -> None:
        instrument = self.instrument_combo.currentText()
        self.custom_name_edit.setEnabled(instrument == INSTRUMENTS[2])
        is_guitar = instrument == INSTRUMENTS[1]
        self.low_edit.setEnabled(not is_guitar)
        self.high_edit.setEnabled(not is_guitar)
        self._update_folder_default()

    def _update_folder_default(self) -> None:
        """Suggest a folder name from the instrument until the user types their own."""
        instrument = self.instrument_combo.currentText()
        default = DEFAULT_FOLDERS.get(instrument, self.custom_name_edit.text().strip() or "instrument")
        if self.folder_edit.text() == self._auto_folder:
            self.folder_edit.setText(default)
        self._auto_folder = default

    def _update_folder_hint(self) -> None:
        folder = RECORDINGS_ROOT / rec.safe_folder_name(self.folder_edit.text())
        self.folder_hint.setText(f"→ {folder}")

    def _build_items(self) -> list[rec.NoteItem]:
        instrument = self.instrument_combo.currentText()
        if instrument == INSTRUMENTS[1]:
            return rec.guitar_notes()
        low = rec.name_to_midi(self.low_edit.text())
        high = rec.name_to_midi(self.high_edit.text())
        if instrument == INSTRUMENTS[0]:
            return rec.piano_notes(low, high)
        return rec.custom_notes(self.custom_name_edit.text(), low, high)

    # ---------------------------------------------------------------- stream

    def _open_stream(self) -> bool:
        if self.recorder is not None:
            return True
        try:
            self.recorder = rec.Recorder(self.device_combo.currentData())
            return True
        except Exception as error:  # PortAudio raises several exception types
            QMessageBox.critical(
                self,
                "Could not open the microphone",
                f"{error}\n\nTip: try the same microphone with another driver in the list "
                "(e.g. [MME] or [Windows DirectSound]), or set the microphone to 48 kHz "
                "in the Windows sound settings.",
            )
            self.recorder = None
            return False

    def _close_stream(self) -> None:
        if self.recorder is not None:
            self.recorder.close()
            self.recorder = None

    # --------------------------------------------------------------- session

    def start_or_stop(self) -> None:
        if self.mode in SESSION_MODES:
            self._end_session()
            return
        if self.mode != OFF:
            return
        try:
            self.items = self._build_items()
        except ValueError as error:
            QMessageBox.critical(self, "Invalid note name", f"{error}\n\nUse e.g. A0, C4, F#3 or Bb2.")
            return

        self.output_dir = RECORDINGS_ROOT / rec.safe_folder_name(self.folder_edit.text())
        existing = [item for item in self.items if (self.output_dir / item.filename).exists()]
        if existing:
            answer = QMessageBox.question(
                self,
                "Folder already in use",
                f"{self.output_dir} already contains {len(existing)} of these recordings.\n\n"
                "If you continue they are overwritten when you record the same note again "
                "(you can use Skip to keep them).\n\nContinue?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            QMessageBox.critical(self, "Could not create the folder", str(error))
            return
        if not self._open_stream():
            return

        self.settings_box.setEnabled(False)
        self.index = 0
        self.last_take = None
        self.setFocus()
        self._arm_current()

    def _end_session(self) -> None:
        rec.stop_playback()
        self._close_stream()
        self.mode = OFF
        self.settings_box.setEnabled(True)
        self.note_label.setText("—")
        self._set_note_font(large=True)
        self.file_label.setText("")
        self.progress_label.setText("")
        self._status(f"Session ended. The files are in {self.output_dir}")
        self._update_buttons()

    def _arm_current(self) -> None:
        if self.index >= len(self.items):
            self.mode = FINISHED
            self.recorder.disarm()
            self.note_label.setText("Done!")
            self._set_note_font(large=True)
            self.file_label.setText("")
            self.progress_label.setText(f"{len(self.items)} / {len(self.items)}")
            self._status(f"All notes are recorded and saved in:\n{self.output_dir}", "#26a269")
            self._update_buttons()
            return

        item = self.items[self.index]
        self.note_label.setText(item.display)
        self._set_note_font(large=len(item.display) <= 6)
        self.file_label.setText(item.filename)
        self.progress_label.setText(f"Note {self.index + 1} / {len(self.items)}")
        # Do not listen yet: the click of the button that got us here would otherwise
        # be detected as the attack. _poll arms the recorder when the countdown ends.
        self.recorder.disarm()
        self.countdown_end = time.monotonic() + self.countdown_spin.value()
        self.mode = COUNTDOWN
        self._update_countdown()
        self._update_buttons()

    def _update_countdown(self) -> None:
        remaining = self.countdown_end - time.monotonic()
        if remaining > 0:
            self._status(f"Get ready…  {math.ceil(remaining)}", "#e5a50a")
            return
        self.recorder.arm(
            float(self.threshold_slider.value()),
            self.silence_spin.value(),
            self.max_length_spin.value(),
        )
        self.mode = WAITING
        self._status("Waiting for the attack… play the note.", "#1a5fb4")
        self._update_buttons()

    def _finish_take(self, raw: np.ndarray) -> None:
        item = self.items[self.index]
        take = rec.process_take(raw, rec.SAMPLE_RATE, float(self.threshold_slider.value()))
        self.mode = SAVED
        try:
            rec.save_flac(self.output_dir / item.filename, take, rec.SAMPLE_RATE)
        except Exception as error:
            self._status(f"Could not save the file: {error}\nPress R to retake.", "#c01c28")
            self._update_buttons()
            return

        self.last_take = take
        length = len(take) / rec.SAMPLE_RATE
        peak = float(np.max(np.abs(take))) if len(take) else 0.0
        message = (f"Saved ✓  ({length:.1f} s, peak {rec.to_db(peak):.1f} dBFS)\n"
                   "Space = next note   ·   R = retake   ·   L = listen")
        if peak >= 0.99:
            self._status("⚠ Clipping! The signal was too loud – lower the microphone gain and "
                         "press R to retake.\n" + message, "#c01c28")
        elif len(raw) >= int(self.max_length_spin.value() * rec.SAMPLE_RATE):
            self._status("The maximum length was reached before the note had decayed.\n" + message,
                         "#b5835a")
        else:
            self._status(message, "#26a269")
        self._update_buttons()

    def _update_buttons(self) -> None:
        self.listen_button.setEnabled(self.mode in (SAVED, FINISHED) and self.last_take is not None)
        self.retake_button.setEnabled(
            self.mode in (SAVED, FINISHED) or (self.mode in (COUNTDOWN, WAITING) and self.index > 0))
        self.skip_button.setEnabled(self.mode in (COUNTDOWN, WAITING, SAVED))
        self.next_button.setEnabled(self.mode == SAVED)
        self.measure_button.setEnabled(self.mode in (OFF, FINISHED))
        running = self.mode in SESSION_MODES
        self.start_button.setText("■  End session" if running else "▶  Start session")
        self.start_button.setEnabled(self.mode != MEASURING)

    # --------------------------------------------------------------- actions

    def next_note(self) -> None:
        if self.mode == SAVED:
            self.index += 1
            self._arm_current()

    def skip(self) -> None:
        if self.mode in (COUNTDOWN, WAITING, SAVED):
            self.index += 1
            self._arm_current()

    def retake(self) -> None:
        """Retake the current note, or the previous one if the next note is already armed."""
        if self.mode in (SAVED, FINISHED):
            if self.mode == FINISHED:
                self.index = len(self.items) - 1
            rec.stop_playback()
            self._arm_current()
        elif self.mode in (COUNTDOWN, WAITING) and self.index > 0:
            self.index -= 1
            self._arm_current()

    def listen(self) -> None:
        if self.mode in (SAVED, FINISHED) and self.last_take is not None:
            rec.play(self.last_take, rec.SAMPLE_RATE)

    def measure_noise(self) -> None:
        if self.mode not in (OFF, FINISHED):
            return
        self.measure_owns_stream = self.recorder is None
        if not self._open_stream():
            return
        self.mode_before_measure = self.mode
        self.mode = MEASURING
        self.recorder.start_measure(2.0)
        self._status("Measuring room noise… stay completely quiet for 2 seconds.", "#1a5fb4")
        self._update_buttons()

    # ------------------------------------------------------------------ poll

    def _poll(self) -> None:
        recorder = self.recorder
        if recorder is not None:
            self.meter.set_values(recorder.level_db, recorder.peak, self.threshold_slider.value(), True)
            self.meter_text.setText(
                f"Level {recorder.level_db:.0f} dBFS   ·   peak {rec.to_db(recorder.peak):.0f} dBFS"
                "   ·   red line = threshold")

            if self.mode == COUNTDOWN:
                self._update_countdown()
            elif self.mode == WAITING and recorder.state == rec.RECORDING:
                self.mode = RECORDING
                self._status("● Recording… let the note ring out.", "#c01c28")
                self._update_buttons()
            elif self.mode in (WAITING, RECORDING) and recorder.state == rec.DONE:
                raw = recorder.take_result()
                if raw is not None:
                    self._finish_take(raw)
            elif self.mode == MEASURING and recorder.state == rec.DONE:
                noise = recorder.measure_result()
                self.mode = self.mode_before_measure
                if self.measure_owns_stream:
                    self._close_stream()
                if noise is not None:
                    threshold = int(round(float(np.clip(noise + 12.0, -70.0, -10.0))))
                    self.threshold_slider.setValue(threshold)
                    self._status(f"Noise level {noise:.0f} dBFS → threshold set to {threshold} dBFS.",
                                 "#26a269")
                self._update_buttons()
        else:
            self.meter.set_values(rec.DB_FLOOR, 0.0, self.threshold_slider.value(), False)
            self.meter_text.setText("The level meter is active during a session.")
