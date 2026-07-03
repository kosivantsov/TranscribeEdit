# preferences_dialog.py
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTabWidget, QDialogButtonBox

class PreferencesDialog(QDialog):
    def __init__(self, parent, tabs):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Preferences"))
        self.setMinimumSize(600, 550)
        
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        
        self.tab_instances = tabs
        for tab in self.tab_instances:
            self.tabs.addTab(tab, tab.TAB_LABEL)
            
        layout.addWidget(self.tabs)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        # Save all tabs only when the user clicks 'Save'
        for tab in self.tab_instances:
            if hasattr(tab, 'save'):
                tab.save()
        super().accept()
