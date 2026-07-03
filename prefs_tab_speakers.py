# prefs_tab_speakers.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit

class SpeakersTab(QWidget):
    TAB_LABEL = "Speakers"
    
    def __init__(self, parent, settings, current_speakers):
        super().__init__(parent)
        self.settings = settings
        layout = QVBoxLayout(self)
        
        info = QLabel(self.tr("Define default speaker tags for quick insertion. You can cycle through them using the 'Insert Speaker Tag' shortcut."))
        info.setWordWrap(True)
        info.setStyleSheet("margin-bottom: 10px;")
        layout.addWidget(info)
        
        self.edits = []
        for i in range(6):
            row = QHBoxLayout()
            row.addWidget(QLabel(self.tr("Speaker {0}:").format(i+1)))
            edit = QLineEdit(current_speakers[i] if i < len(current_speakers) else f"SPEAKER_0{i}")
            self.edits.append(edit)
            row.addWidget(edit)
            layout.addLayout(row)
        layout.addStretch()

    def save(self):
        for i, e in enumerate(self.edits):
            self.settings.setValue(f"speaker_{i}", e.text().strip())
