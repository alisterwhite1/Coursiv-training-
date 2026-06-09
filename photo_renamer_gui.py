#!/usr/bin/env python3
"""
Photo Renamer — Desktop GUI
Rename photos using EXIF date, sequential numbers, and custom prefix/suffix.
Requires: PyQt6  (pip install PyQt6)
"""

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from photo_renamer import apply_renames, build_new_name, get_photo_files


# ── Worker thread so renaming never freezes the UI ──────────────────────────

class RenameWorker(QThread):
    finished = pyqtSignal(int, int)   # renamed, skipped
    error = pyqtSignal(str)

    def __init__(self, photos, new_names):
        super().__init__()
        self.photos = photos
        self.new_names = new_names

    def run(self):
        try:
            renamed, skipped = apply_renames(self.photos, self.new_names, dry_run=False)
            self.finished.emit(renamed, skipped)
        except Exception as exc:
            self.error.emit(str(exc))


# ── Main Window ──────────────────────────────────────────────────────────────

class PhotoRenamerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Photo Renamer")
        self.setMinimumSize(820, 560)
        self._photos: list[Path] = []
        self._new_names: list[str] = []
        self._worker: RenameWorker | None = None
        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        layout.addWidget(self._folder_section())
        layout.addWidget(self._options_section())
        layout.addWidget(self._preview_section())
        layout.addWidget(self._action_bar())

    def _folder_section(self) -> QWidget:
        box = QHBoxLayout()
        box.setSpacing(8)

        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Select a folder containing photos…")
        self.folder_edit.setReadOnly(True)

        browse_btn = QPushButton("Browse…")
        browse_btn.setFixedWidth(90)
        browse_btn.clicked.connect(self._browse_folder)

        box.addWidget(QLabel("Folder:"))
        box.addWidget(self.folder_edit, 1)
        box.addWidget(browse_btn)

        container = QWidget()
        container.setLayout(box)
        return container

    def _options_section(self) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        grid = QVBoxLayout(frame)
        grid.setSpacing(10)

        title = QLabel("Renaming Options")
        title.setFont(QFont(title.font().family(), -1, QFont.Weight.Bold))
        grid.addWidget(title)

        # Row 1 — date & sequence checkboxes
        row1 = QHBoxLayout()
        self.cb_date = QCheckBox("Use EXIF date (falls back to file date)")
        self.cb_date.stateChanged.connect(self._refresh_preview)
        self.cb_seq = QCheckBox("Sequential numbering")
        self.cb_seq.stateChanged.connect(self._refresh_preview)
        row1.addWidget(self.cb_date)
        row1.addSpacing(24)
        row1.addWidget(self.cb_seq)
        row1.addStretch()
        grid.addLayout(row1)

        # Row 2 — prefix & suffix
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        row2.addWidget(QLabel("Prefix:"))
        self.prefix_edit = QLineEdit()
        self.prefix_edit.setPlaceholderText("e.g. holiday")
        self.prefix_edit.setMaximumWidth(180)
        self.prefix_edit.textChanged.connect(self._refresh_preview)
        row2.addWidget(self.prefix_edit)
        row2.addSpacing(24)
        row2.addWidget(QLabel("Suffix:"))
        self.suffix_edit = QLineEdit()
        self.suffix_edit.setPlaceholderText("e.g. 2024")
        self.suffix_edit.setMaximumWidth(180)
        self.suffix_edit.textChanged.connect(self._refresh_preview)
        row2.addWidget(self.suffix_edit)
        row2.addStretch()
        grid.addLayout(row2)

        return frame

    def _preview_section(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.preview_label = QLabel("Preview")
        self.preview_label.setFont(QFont(self.preview_label.font().family(), -1, QFont.Weight.Bold))
        layout.addWidget(self.preview_label)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Current Name", "New Name"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.table)

        return container

    def _action_bar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)

        self.status_label = QLabel("No folder selected.")
        self.status_label.setStyleSheet("color: grey;")
        layout.addWidget(self.status_label, 1)

        self.rename_btn = QPushButton("Rename Files")
        self.rename_btn.setFixedWidth(130)
        self.rename_btn.setEnabled(False)
        self.rename_btn.clicked.connect(self._do_rename)
        layout.addWidget(self.rename_btn)

        return bar

    # ── Logic ────────────────────────────────────────────────────────────────

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Photo Folder")
        if folder:
            self.folder_edit.setText(folder)
            self._load_photos(Path(folder))

    def _load_photos(self, directory: Path):
        self._photos = get_photo_files(directory)
        self._refresh_preview()
        if not self._photos:
            self.status_label.setText("No photo files found in this folder.")
            self.status_label.setStyleSheet("color: orange;")

    def _current_options(self) -> dict:
        return dict(
            prefix=self.prefix_edit.text().strip(),
            suffix=self.suffix_edit.text().strip(),
            use_date=self.cb_date.isChecked(),
            use_sequence=self.cb_seq.isChecked(),
        )

    def _refresh_preview(self):
        opts = self._current_options()
        photos = self._photos

        # Require at least one meaningful option
        has_option = opts['use_date'] or opts['use_sequence'] or opts['prefix'] or opts['suffix']

        self.table.setRowCount(0)
        self._new_names = []

        if not photos:
            self._set_rename_enabled(False)
            return

        if not has_option:
            self.status_label.setText(f"{len(photos)} photo(s) found — choose at least one option above.")
            self.status_label.setStyleSheet("color: grey;")
            self._set_rename_enabled(False)
            return

        new_names = [
            build_new_name(p, i + 1, len(photos), **opts)
            for i, p in enumerate(photos)
        ]
        self._new_names = new_names

        changed = 0
        self.table.setRowCount(len(photos))
        for row, (photo, new_name) in enumerate(zip(photos, new_names)):
            old_item = QTableWidgetItem(photo.name)
            new_item = QTableWidgetItem(new_name)
            if photo.name != new_name:
                new_item.setForeground(QColor("#1a7f37"))  # green
                changed += 1
            else:
                new_item.setForeground(QColor("grey"))
                old_item.setForeground(QColor("grey"))
            self.table.setItem(row, 0, old_item)
            self.table.setItem(row, 1, new_item)

        self.status_label.setText(
            f"{len(photos)} photo(s) — {changed} will be renamed, {len(photos) - changed} unchanged."
        )
        self.status_label.setStyleSheet("color: black;")
        self._set_rename_enabled(changed > 0)

    def _set_rename_enabled(self, enabled: bool):
        self.rename_btn.setEnabled(enabled)

    def _do_rename(self):
        if not self._photos or not self._new_names:
            return

        changed = sum(1 for p, n in zip(self._photos, self._new_names) if p.name != n)
        answer = QMessageBox.question(
            self,
            "Confirm Rename",
            f"Rename {changed} file(s)?\nThis cannot be undone automatically.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self.rename_btn.setEnabled(False)
        self.rename_btn.setText("Renaming…")

        self._worker = RenameWorker(list(self._photos), list(self._new_names))
        self._worker.finished.connect(self._on_rename_done)
        self._worker.error.connect(self._on_rename_error)
        self._worker.start()

    def _on_rename_done(self, renamed: int, skipped: int):
        self.rename_btn.setText("Rename Files")
        QMessageBox.information(
            self,
            "Done",
            f"{renamed} file(s) renamed successfully.\n{skipped} unchanged.",
        )
        # Reload the folder to reflect new names
        folder = self.folder_edit.text()
        if folder:
            self._load_photos(Path(folder))

    def _on_rename_error(self, message: str):
        self.rename_btn.setText("Rename Files")
        self.rename_btn.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Renaming failed:\n{message}")


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Photo Renamer")
    window = PhotoRenamerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
