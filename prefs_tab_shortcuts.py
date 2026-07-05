# prefs_tab_shortcuts.py
import platform

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel,
    QPushButton, QKeySequenceEdit, QScrollArea,
)
from PyQt5.QtGui import QKeySequence
from PyQt5.QtCore import Qt

from shortcuts import DEFAULT_SHORTCUTS


ACTION_COL_MIN_WIDTH = 180
EDIT_COL_MIN_WIDTH = 120
BUTTON_WIDTH = 70
BUTTON_HEIGHT = 24


class ShortcutsTab(QWidget):
    TAB_LABEL = "Shortcuts"

    def __init__(self, parent, settings, current_shortcuts):
        super().__init__(parent)
        self.settings = settings
        self.current_shortcuts = current_shortcuts
        self.edits = {}

        is_macos = platform.system() == "Darwin"
        visible_shortcuts = {
            k: v for k, v in DEFAULT_SHORTCUTS.items()
            if not (is_macos and k == "Preferences")
        }
        self.visible_shortcuts = visible_shortcuts

        outer = QVBoxLayout(self)

        info = QLabel(self.tr(
            "Configure keyboard shortcuts for the application. "
            "Click a shortcut field and press the new key combination to rebind it."
        ))
        info.setWordWrap(True)
        info.setStyleSheet("margin-bottom: 10px;")
        outer.addWidget(info)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        layout = QVBoxLayout(content)

        grid = QGridLayout()
        grid.setColumnMinimumWidth(0, ACTION_COL_MIN_WIDTH)
        grid.setColumnStretch(1, 1)
        grid.setColumnMinimumWidth(1, EDIT_COL_MIN_WIDTH)

        row = 0
        for name, default_seq in visible_shortcuts.items():
            label = QLabel(self.tr(name))
            grid.addWidget(label, row, 0)

            edit = QKeySequenceEdit()
            edit.setMinimumWidth(EDIT_COL_MIN_WIDTH)
            seq_str = self.current_shortcuts.get(name, default_seq)
            if seq_str:
                edit.setKeySequence(QKeySequence(seq_str))
            self.edits[name] = edit
            grid.addWidget(edit, row, 1)

            clear_btn = QPushButton(self.tr("Clear"))
            clear_btn.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
            clear_btn.setAutoDefault(False)
            clear_btn.setDefault(False)
            clear_btn.clicked.connect(lambda checked, n=name: self._clear_shortcut(n))
            grid.addWidget(clear_btn, row, 2)

            reset_btn = QPushButton(self.tr("Reset"))
            reset_btn.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
            reset_btn.setAutoDefault(False)
            reset_btn.setDefault(False)
            reset_btn.clicked.connect(lambda checked, n=name: self._reset_shortcut(n))
            grid.addWidget(reset_btn, row, 3)

            row += 1

        layout.addLayout(grid)
        layout.addStretch()

    def _clear_shortcut(self, name):
        self.edits[name].setKeySequence(QKeySequence())

    def _reset_shortcut(self, name):
        default_seq = DEFAULT_SHORTCUTS.get(name, "")
        self.edits[name].setKeySequence(QKeySequence(default_seq))

    def save(self):
        for name, edit in self.edits.items():
            seq_str = edit.keySequence().toString()
            self.settings.setValue(f"shortcut_{name}", seq_str)
