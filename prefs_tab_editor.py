# prefs_tab_editor.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QHBoxLayout,
    QLabel, QPushButton, QColorDialog, QFontDialog
)
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtCore import Qt

DEFAULT_COLORS = {
    "text_fg": "", "text_bg": "",
    "ts_fg": "", "ts_bg": "",
    "spk_fg": "", "spk_bg": "",
    "md_heading_fg": "#ffaa00",
    "md_hr_fg": "#888888",
    "md_list_bg": "#2a2a2a",
    "md_list_marker_fg": "#00ff00",
    "md_markup_fg": "#787878",
    "md_code_bg": "",
    "md_code_fg": "",
    "md_blockquote_fg": "",
    # Comment colours
    "comment_fg": "#888888",
    "comment_bg": "#1a1a2e",
}

# Font settings stored separately (serialised QFont strings).
DEFAULT_FONTS = {
    "font": "",
    "ts_font": "",
    "spk_font": "",
    "md_code_font": "",
    "md_markup_font": "",
    "comment_font": "",
}


class EditorTab(QWidget):
    TAB_LABEL = "Editor"

    def __init__(self, parent, settings):
        super().__init__(parent)
        self.settings = settings

        self.config = {k: settings.value(f"editor_{k}", v) for k, v in DEFAULT_COLORS.items()}
        for k, v in DEFAULT_FONTS.items():
            self.config[k] = settings.value(f"editor_{k}", v)

        layout = QVBoxLayout(self)

        info = QLabel(self.tr(
            "Customize the visual appearance of the editor, "
            "including fonts and syntax highlighting colors."
        ))
        info.setWordWrap(True)
        info.setStyleSheet("margin-bottom: 10px;")
        layout.addWidget(info)

        grid = QGridLayout()

        color_labels = [
            ("text_fg",           self.tr("General Text Foreground")),
            ("text_bg",           self.tr("General Text Background")),
            ("ts_fg",             self.tr("Timestamp Foreground")),
            ("ts_bg",             self.tr("Timestamp Background")),
            ("spk_fg",            self.tr("Speaker Tag Foreground")),
            ("spk_bg",            self.tr("Speaker Tag Background")),
            ("md_heading_fg",     self.tr("MD Heading Foreground")),
            ("md_hr_fg",          self.tr("MD Horizontal Rule")),
            ("md_list_bg",        self.tr("MD List Background")),
            ("md_list_marker_fg", self.tr("MD List Marker")),
            ("md_markup_fg",      self.tr("MD Markup Symbols Foreground")),
            ("md_code_bg",        self.tr("MD Code Background")),
            ("md_code_fg",        self.tr("MD Code Foreground")),
            ("md_blockquote_fg",  self.tr("MD Blockquote Foreground")),
            ("comment_fg",        self.tr("Comment Foreground")),
            ("comment_bg",        self.tr("Comment Background")),
        ]

        self.color_btns = {}
        for i, (key, label) in enumerate(color_labels):
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

        font_labels = [
            ("font",           self.tr("Editor Font:")),
            ("ts_font",        self.tr("Timestamp Font:")),
            ("spk_font",       self.tr("Speaker Tag Font:")),
            ("md_code_font",   self.tr("MD Code Font:")),
            ("md_markup_font", self.tr("MD Markup Symbol Font:")),
            ("comment_font",   self.tr("Comment Font:")),
        ]

        self.font_btns = {}
        for fkey, flabel in font_labels:
            row = QHBoxLayout()
            row.addWidget(QLabel(flabel))
            btn = QPushButton(self.tr("Select Font..."))
            self._update_font_btn(btn, self.config.get(fkey, ""))
            btn.clicked.connect(lambda checked, k=fkey, b=btn: self._pick_font(k, b))
            row.addWidget(btn)
            clear_f = QPushButton(self.tr("Clear / Default"))
            clear_f.clicked.connect(lambda checked, k=fkey, b=btn: self._clear_font(k, b))
            row.addWidget(clear_f)
            layout.addLayout(row)
            self.font_btns[fkey] = btn

        layout.addStretch()

    # ------------------------------------------------------------------ helpers

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

    def _update_font_btn(self, btn, font_str):
        if font_str:
            f = QFont()
            f.fromString(font_str)
            btn.setText(f"{f.family()}, {f.pointSize()}pt")
            btn.setFont(f)
        else:
            btn.setText(self.tr("Select Font..."))
            btn.setFont(QFont())

    def _clear_font(self, key, btn):
        self.config[key] = DEFAULT_FONTS.get(key, "")
        self._update_font_btn(btn, self.config[key])

    def _pick_font(self, key, btn):
        font = QFont()
        if self.config.get(key):
            font.fromString(self.config[key])
        font, ok = QFontDialog.getFont(font, self, self.tr("Select Font"))
        if ok:
            self.config[key] = font.toString()
            self._update_font_btn(btn, self.config[key])

    # ------------------------------------------------------------------ save

    def save(self):
        for k, v in self.config.items():
            self.settings.setValue(f"editor_{k}", v)
