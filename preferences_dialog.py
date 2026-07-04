# preferences_dialog.py
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTabWidget, QDialogButtonBox


class PreferencesDialog(QDialog):
    def __init__(self, parent, tabs):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Preferences"))
        self.setMinimumSize(600, 550)

        layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()

        self.tab_instances = tabs
        for tab in self.tab_instances:
            self.tab_widget.addTab(tab, tab.TAB_LABEL)

        layout.addWidget(self.tab_widget)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def jump_to_tab(self, index: int):
        """Switch to the tab at *index* immediately after the dialog is shown."""
        if 0 <= index < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(index)

    def accept(self):
        for tab in self.tab_instances:
            if hasattr(tab, "save"):
                tab.save()
        super().accept()
