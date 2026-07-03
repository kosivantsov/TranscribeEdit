# prefs_tab_export.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QFormLayout, QComboBox
from PyQt5.QtCore import Qt
from exporter import DEFAULT_MD_TEMPLATE, DEFAULT_HTML_TEMPLATE

class ExportTab(QWidget):
    TAB_LABEL = "Export Options"
    
    def __init__(self, parent, settings):
        super().__init__(parent)
        self.settings = settings
        layout = QVBoxLayout(self)

        info = QLabel(self.tr(
            "Configure how Markdown and HTML files are exported.<br><br>"
            "Format strings support the following variables:<br>"
            "<b>${timestamp_start}</b>, <b>${timestamp_end}</b>, <b>${speaker}</b>, <b>${text}</b><br><br>"
            "Use <b>\\n</b> for newlines and <b>\\t</b> for tabs. "
            "Simply omit a variable from the string if you do not want it included in the output."
        ))
        info.setTextFormat(Qt.RichText)
        info.setWordWrap(True)
        info.setStyleSheet("margin-bottom: 15px;")
        layout.addWidget(info)

        form = QFormLayout()
        
        self.default_fmt_combo = QComboBox()
        for fmt in ["srt", "vtt", "ass", "ttml", "md", "html"]:
            self.default_fmt_combo.addItem(fmt.upper(), fmt)
        idx = self.default_fmt_combo.findData(settings.value("export_default_format", "srt"))
        if idx >= 0: self.default_fmt_combo.setCurrentIndex(idx)
        form.addRow(self.tr("Default Export Format (Ctrl+E):"), self.default_fmt_combo)
        
        self.md_format = QLineEdit()
        self.md_format.setText(settings.value("export_md_format", DEFAULT_MD_TEMPLATE))
        form.addRow(self.tr("MD Format:"), self.md_format)

        self.html_format = QLineEdit()
        self.html_format.setText(settings.value("export_html_format", DEFAULT_HTML_TEMPLATE))
        form.addRow(self.tr("HTML Format:"), self.html_format)

        layout.addLayout(form)
        layout.addStretch()

    def save(self):
        self.settings.setValue("export_default_format", self.default_fmt_combo.currentData())
        self.settings.setValue("export_md_format", self.md_format.text())
        self.settings.setValue("export_html_format", self.html_format.text())
