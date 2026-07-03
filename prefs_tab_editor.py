# prefs_tab_editor.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QHBoxLayout, QLabel, QPushButton, QColorDialog, QFontDialog
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtCore import Qt

DEFAULT_COLORS = {
    "text_fg": "", "text_bg": "", "ts_fg": "", "ts_bg": "", "spk_fg": "", "spk_bg": "",
    "md_heading_fg": "#ffaa00",
    "md_hr_fg": "#888888",
    "md_list_bg": "#2a2a2a",
    "md_list_marker_fg": "#00ff00",
    "md_markup_fg": "#787878"
}

class EditorTab(QWidget):
    TAB_LABEL = "Editor"
    
    def __init__(self, parent, settings):
        super().__init__(parent)
        self.settings = settings
        
        self.config = {k: settings.value(f"editor_{k}", v) for k, v in DEFAULT_COLORS.items()}
        self.config["font"] = settings.value("editor_font", "")

        layout = QVBoxLayout(self)
        
        info = QLabel(self.tr("Customize the visual appearance of the editor, including fonts and syntax highlighting colors."))
        info.setWordWrap(True)
        info.setStyleSheet("margin-bottom: 10px;")
        layout.addWidget(info)
        
        grid = QGridLayout()

        labels = [
            ("text_fg", self.tr("General Text Foreground")),
            ("text_bg", self.tr("General Text Background")),
            ("ts_fg", self.tr("Timestamp Foreground")),
            ("ts_bg", self.tr("Timestamp Background")),
            ("spk_fg", self.tr("Speaker Tag Foreground")),
            ("spk_bg", self.tr("Speaker Tag Background")),
            ("md_heading_fg", self.tr("MD Heading Foreground")),
            ("md_hr_fg", self.tr("MD Horizontal Rule")),
            ("md_list_bg", self.tr("MD List Background")),
            ("md_list_marker_fg", self.tr("MD List Marker")),
            ("md_markup_fg", self.tr("MD Markup Symbols Foreground")),
        ]
        
        self.color_btns = {}
        for i, (key, label) in enumerate(labels):
            grid.addWidget(QLabel(label), i, 0)
            btn = QPushButton()
            self._update_btn_color(btn, self.config.get(key, ""))
            btn.clicked.connect(lambda checked, k=key, b=btn: self._pick_color(k, b))
            grid.addWidget(btn, i, 1)

            clear_btn = QPushButton(self.tr("Clear / Default"))
            clear_btn.clicked.connect(lambda checked, k=key, b=btn: self._clear_color(k, b))
            grid.addWidget(clear_btn, i, 2)
            self.color_btns[key] = btn

        layout.addLayout(grid)

        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel(self.tr("Editor Font:")))
        self.font_btn = QPushButton(self.tr("Select Font..."))
        self.font_btn.clicked.connect(self._pick_font)
        font_layout.addWidget(self.font_btn)
        layout.addLayout(font_layout)
        layout.addStretch()

    def _update_btn_color(self, btn, color_str):
        if color_str:
            btn.setStyleSheet(f"background-color: {color_str};")
            btn.setText("")
        else:
            btn.setStyleSheet("")
            btn.setText(self.tr("Unset"))

    def _clear_color(self, key, btn):
        self.config[key] = DEFAULT_COLORS.get(key, "")
        self._update_btn_color(btn, self.config[key])

    def _pick_color(self, key, btn):
        initial = QColor(self.config.get(key, "#ffffff")) if self.config.get(key) else Qt.white
        color = QColorDialog.getColor(initial, self, self.tr("Select Color"))
        if color.isValid():
            hex_color = color.name()
            self.config[key] = hex_color
            self._update_btn_color(btn, hex_color)

    def _pick_font(self):
        font = QFont()
        if self.config.get("font"): font.fromString(self.config["font"])
        font, ok = QFontDialog.getFont(font, self, self.tr("Select Editor Font"))
        if ok: self.config["font"] = font.toString()

    def save(self):
        for k, v in self.config.items():
            self.settings.setValue(f"editor_{k}", v)
