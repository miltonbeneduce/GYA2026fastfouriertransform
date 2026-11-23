"""Shared widget and helpers for choosing several files, or every file in a folder."""

from __future__ import annotations

from pathlib import Path
import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

AUDIO_EXTENSIONS = (".wav", ".mp3", ".flac")
AUDIO_FILTER = "Audio files (*.wav *.mp3 *.flac)"


def natural_key(path: Path) -> list:
    """Sort 'note_2' before 'note_10' (numbers are compared as numbers)."""
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.name)]


def files_in_folder(folder: str | Path, extensions: tuple[str, ...]) -> list[Path]:
    """All files directly inside the folder with one of the extensions, naturally sorted."""
    return sorted(
        (path for path in Path(folder).iterdir() if path.is_file() and path.suffix.lower() in extensions),
        key=natural_key,
    )


def output_subfolder(source: Path, output_root: Path) -> Path:
    """Mirror the source file's folder under output_root.

    data/raw_audio/Piano take 1/piano_A0_021.flac -> <output_root>/Piano take 1/.
    Files directly in a data/ folder (e.g. data/raw_audio/) go straight to output_root.
    """
    parent = source.parent
    if parent.parent.name == "data" or not parent.name:
        return output_root
    return output_root / parent.name


def progress_dialog(parent: QWidget, text: str, count: int) -> QProgressDialog:
    dialog = QProgressDialog(text, "Cancel", 0, count, parent)
    dialog.setWindowModality(Qt.WindowModality.WindowModal)
    dialog.setMinimumDuration(300)
    dialog.setValue(0)
    return dialog


class FileListWidget(QWidget):
    """Buttons for 'Select files' / 'Select folder' / 'Clear' plus a list of chosen files.

    Emits ``current_path_changed`` with the selected Path (or None when the list is empty).
    """

    current_path_changed = Signal(object)

    def __init__(self, start_dir: Path, extensions: tuple[str, ...], file_filter: str) -> None:
        super().__init__()
        self.start_dir = start_dir
        self.extensions = extensions
        self.file_filter = file_filter

        files_button = QPushButton("Select files…")
        files_button.setToolTip("Choose one or more files (Ctrl/Shift-click to select several).")
        files_button.clicked.connect(self.select_files)
        folder_button = QPushButton("Select folder…")
        folder_button.setToolTip("Load every supported file in a folder.")
        folder_button.clicked.connect(self.select_folder)
        clear_button = QPushButton("Clear list")
        clear_button.clicked.connect(self.clear)
        self.count_label = QLabel("No files selected.")

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.setMaximumHeight(140)
        self.list_widget.currentItemChanged.connect(self._on_current_changed)

        button_row = QHBoxLayout()
        button_row.addWidget(files_button)
        button_row.addWidget(folder_button)
        button_row.addWidget(clear_button)
        button_row.addWidget(self.count_label, stretch=1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(button_row)
        layout.addWidget(self.list_widget)

    # ------------------------------------------------------------------ public

    def paths(self) -> list[Path]:
        return [self.list_widget.item(row).data(Qt.ItemDataRole.UserRole) for row in range(self.list_widget.count())]

    def current_path(self) -> Path | None:
        item = self.list_widget.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def set_paths(self, paths: list[Path]) -> None:
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for path in paths:
            item = QListWidgetItem(f"{path.parent.name}/{path.name}")
            item.setToolTip(str(path))
            item.setData(Qt.ItemDataRole.UserRole, path)
            self.list_widget.addItem(item)
        self.list_widget.blockSignals(False)
        self.count_label.setText(f"{len(paths)} file(s)." if paths else "No files selected.")
        if paths:
            self.list_widget.setCurrentRow(0)  # emits current_path_changed
        else:
            self.current_path_changed.emit(None)

    def clear(self) -> None:
        self.set_paths([])

    def select_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Select files", str(self._dialog_dir()), self.file_filter)
        if paths:
            self.set_paths(sorted((Path(path) for path in paths), key=natural_key))

    def select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select folder", str(self._dialog_dir()))
        if not folder:
            return
        paths = files_in_folder(folder, self.extensions)
        if not paths:
            self.count_label.setText(f"No {', '.join(self.extensions)} files in {Path(folder).name}.")
            return
        self.set_paths(paths)

    # ----------------------------------------------------------------- private

    def _dialog_dir(self) -> Path:
        current = self.current_path()
        return current.parent if current is not None else self.start_dir

    def _on_current_changed(self, current: QListWidgetItem | None, _previous) -> None:
        self.current_path_changed.emit(current.data(Qt.ItemDataRole.UserRole) if current is not None else None)
