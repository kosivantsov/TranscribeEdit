# prefs_tab_shortcuts.py
import platform
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QKeySequenceEdit, QLabel,
)
from PyQt5.QtCore import Qt
from shortcuts import DEFAULT_SHORTCUTS


class ShortcutsTab(QWidget):
    TAB_LABEL = "Shortcuts"

    def __init__(self, parent, settings, current_shortcuts):
        super().__init__(parent)
        self.settings = settings
        self.current_shortcuts = current_shortcuts
        self.edits = {}

        # On macOS, "Preferences" uses the native Cmd+, role and must not
        # appear in the configurable shortcuts table.
        is_macos = platform.system() == "Darwin"
        visible_shortcuts = {
            k: v for k, v in DEFAULT_SHORTCUTS.items()
            if not (is_macos and k == "Preferences")
        }

        layout = QVBoxLayout(self)

        info = QLabel(self.tr(
            "Configure keyboard shortcuts for the application. "
            "Click a shortcut cell and press the new key combination to rebind it."
        ))
        info.setWordWrap(True)
        info.setStyleSheet("margin-bottom: 10px;")
        layout.addWidget(info)

        self.table = QTableWidget(len(visible_shortcuts), 2)
        self.table.setHorizontalHeaderLabels([self.tr("Action"), self.tr("Shortcut")])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.NoSelection)

        for i, (name, default_seq) in enumerate(visible_shortcuts.items()):
            item = QTableWidgetItem(name)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, 0, item)

            edit = QKeySequenceEdit()
            seq_str = self.current_shortcuts.get(name, default_seq)
            if seq_str:
                from PyQt5.QtGui import QKeySequence
                edit.setKeySequence(QKeySequence(seq_str))

            self.edits[name] = edit
            self.table.setCellWidget(i, 1, edit)

        layout.addWidget(self.table)

    def save(self):
        for name, edit in self.edits.items():
            seq_str = edit.keySequence().toString()
            self.settings.setValue(f"shortcut_{name}", seq_str)
