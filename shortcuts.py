from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QKeySequenceEdit
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence

DEFAULT_SHORTCUTS = {
    "Quit": "Ctrl+Q",
    "Play/Pause": "Ctrl+Shift+Space",
    "Play/Pause (Alt)": "Ctrl+P",
    "Stop/Play": "Ctrl+Return",
    "Stop": "F8",
    "Jump Dialog": "Ctrl+J",
    "Insert Timestamp": "Ctrl+T",
    "Insert Speaker Tag": "Ctrl+U",
    "Toggle Highlight": "Ctrl+H",
    "Find": "Ctrl+F",
    "Jump to Cursor": "F5",
    "Increase Speed": "Ctrl++",
    "Decrease Speed": "Ctrl+-",
    "Volume Up": "Ctrl+Up",
    "Volume Down": "Ctrl+Down",
    "Seek -0.1s": "Ctrl+Left",
    "Seek +0.1s": "Ctrl+Right",
    "Seek -0.5s": "Ctrl+Shift+Left",
    "Seek +0.5s": "Ctrl+Shift+Right",
    "Seek -1.0s": "Ctrl+Alt+Left",
    "Seek +1.0s": "Ctrl+Alt+Right",
    "Seek -5.0s": "Ctrl+Alt+Shift+Left",
    "Seek +5.0s": "Ctrl+Alt+Shift+Right",
    "Waveform 0.1s": "Ctrl+1",
    "Waveform 0.5s": "Ctrl+2",
    "Waveform 1.0s": "Ctrl+3",
    "Waveform 2.0s": "Ctrl+4",
    "Waveform 5.0s": "Ctrl+5",
    "Open Audio": "Ctrl+O",
    "Load JSON": "Ctrl+L",
    "Save JSON": "Ctrl+S",
    "Export SRT": "Ctrl+E"
}

class ShortcutWidget(QWidget):
    def __init__(self, parent, current_shortcuts):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.table = QTableWidget(len(current_shortcuts), 2)
        self.table.setHorizontalHeaderLabels([self.tr("Action"), self.tr("Shortcut")])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        self.edits = {}
        for i, (action, seq_str) in enumerate(current_shortcuts.items()):
            item = QTableWidgetItem(self.tr(action))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, 0, item)

            edit = QKeySequenceEdit(QKeySequence(seq_str))
            self.table.setCellWidget(i, 1, edit)
            self.edits[action] = edit

        btn_layout = QHBoxLayout()
        default_btn = QPushButton(self.tr("Restore Defaults"))
        default_btn.clicked.connect(self.restore_defaults)

        btn_layout.addWidget(default_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def restore_defaults(self):
        for action, edit in self.edits.items():
            if action in DEFAULT_SHORTCUTS:
                edit.setKeySequence(QKeySequence(DEFAULT_SHORTCUTS[action]))

    @property
    def result_shortcuts(self):
        return {action: edit.keySequence().toString() for action, edit in self.edits.items()}
