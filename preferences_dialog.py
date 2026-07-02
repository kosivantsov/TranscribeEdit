from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTabWidget, QDialogButtonBox
from widgets import HandyConfigWidget, SpeakerConfigWidget, EditorConfigWidget
from shortcuts import ShortcutWidget

class PreferencesDialog(QDialog):
    def __init__(self, parent, settings_data):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Preferences"))
        self.setMinimumSize(500, 550)
        
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        
        self.shortcut_tab = ShortcutWidget(self, settings_data['shortcuts'])
        self.tabs.addTab(self.shortcut_tab, self.tr("Shortcuts"))
        
        self.editor_tab = EditorConfigWidget(self, settings_data['editor'])
        self.tabs.addTab(self.editor_tab, self.tr("Editor"))
        
        self.speaker_tab = SpeakerConfigWidget(self, settings_data['speakers'])
        self.tabs.addTab(self.speaker_tab, self.tr("Speakers"))
        
        # Cloud Whisper tab has been removed since it now has a dedicated dialog
        
        self.handy_tab = HandyConfigWidget(self, settings_data['handy_bin'], settings_data['handy_model'], settings_data['handy_device'])
        self.tabs.addTab(self.handy_tab, self.tr("Handy Tool"))
        
        layout.addWidget(self.tabs)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
