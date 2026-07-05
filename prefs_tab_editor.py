"""prefs_tab_editor.py — Editor appearance tab in Preferences.

Changes from base commit
------------------------
* Color buttons show "Default" (plain, uncolored) when the stored value is
  SENTINEL; only custom values paint the button background.
* Font buttons always render with the standard UI font showing name/size as
  plain text; the actual chosen font is applied to the editor via ThemeManager.
* All reads/writes go through theme_<key> QSettings keys via ThemeManager.
* "Default" button resets the key to SENTINEL.
* All color/font pick and reset buttons share a fixed height AND fixed width
  (via setFixedSize, not just stylesheet min-height/min-width) so macOS Aqua
  rendering never collapses or varies row heights/widths when a
  background-color stylesheet is applied to a sibling button, and long font
  names don't stretch their button wider than the others.
* Font rows are now laid out in their own QGridLayout (mirroring the color
  grid) so pick/reset buttons align in straight columns regardless of each
  row's label text length.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QHBoxLayout,
    QLabel, QPushButton, QColorDialog, QFontDialog,
)
from PyQt5.QtGui import QColor, QFont, QFontMetrics
from PyQt5.QtCore import Qt

from theme_manager import SENTINEL

COLOR_LABELS = [
    ("text_fg",           "General Text Foreground"),
    ("text_bg",           "General Text Background"),
    ("ts_fg",             "Timestamp Foreground"),
    ("ts_bg",             "Timestamp Background"),
    ("spk_fg",            "Speaker Tag Foreground"),
    ("spk_bg",            "Speaker Tag Background"),
    ("md_heading_fg",     "MD Heading Foreground"),
    ("md_hr_fg",          "MD Horizontal Rule"),
    ("md_list_bg",        "MD List Background"),
    ("md_list_marker_fg", "MD List Marker"),
    ("md_markup_fg",      "MD Markup Symbols Foreground"),
    ("md_code_bg",        "MD Code Background"),
    ("md_code_fg",        "MD Code Foreground"),
    ("md_blockquote_fg",  "MD Blockquote Foreground"),
    ("comment_fg",        "Comment Foreground"),
    ("comment_bg",        "Comment Background"),
]

FONT_LABELS = [
    ("font",           "Editor Font:"),
    ("ts_font",        "Timestamp Font:"),
    ("spk_font",       "Speaker Tag Font:"),
    ("md_code_font",   "MD Code Font:"),
    ("md_markup_font", "MD Markup Symbol Font:"),
    ("comment_font",   "Comment Font:"),
]

# Fixed pixel dimensions shared by every pick/reset button in this tab.
# Using setFixedSize (not just a stylesheet min-/max-width) guarantees
# identical, stable geometry on macOS regardless of whether a sibling
# button has a background-color stylesheet applied, and regardless of
# how long the displayed font name/size text is.
PICK_BTN_WIDTH = 110
PICK_BTN_HEIGHT = 24
RESET_BTN_WIDTH = 70
RESET_BTN_HEIGHT = 24

BTN_BASE_STYLE = "padding: 2px 6px;"
RESET_BASE_STYLE = "padding: 2px 6px;"


class EditorTab(QWidget):
    TAB_LABEL = "Editor"

    def __init__(self, parent, settings):
        super().__init__(parent)
        self.settings = settings

        from theme_manager import ThemeManager
        self._tm = ThemeManager(settings)

        # Working copy: key -> stored value (may be SENTINEL)
        self._stored = {}
        for key, _ in COLOR_LABELS:
            self._stored[key] = settings.value(f"theme_{key}", SENTINEL)
        for key, _ in FONT_LABELS:
            self._stored[key] = settings.value(f"theme_{key}", SENTINEL)

        self._build_ui()

    def _max_font_label_width(self):
        fm = QFontMetrics(self.font())
        all_labels = [label for _, label in FONT_LABELS] + [label for _, label in COLOR_LABELS]
        return max(fm.horizontalAdvance(label) for label in all_labels) + 10

    def _build_ui(self):
        layout = QVBoxLayout(self)
    
        info = QLabel(self.tr(
            "Customize the visual appearance of the editor, "
            "including fonts and syntax highlighting colors."
        ))
        info.setWordWrap(True)
        info.setStyleSheet("margin-bottom: 10px;")
        layout.addWidget(info)
    
        grid = QGridLayout()
        row = 0
        self.color_btns = {}
        for key, label in COLOR_LABELS:
            grid.addWidget(QLabel(self.tr(label)), row, 0)
            btn = QPushButton()
            btn.setFixedSize(PICK_BTN_WIDTH, PICK_BTN_HEIGHT)
            self._refresh_color_btn(btn, key)
            btn.clicked.connect(lambda checked, k=key, b=btn: self._pick_color(k, b))
            grid.addWidget(btn, row, 2)
    
            clear_btn = QPushButton(self.tr("Reset"))
            clear_btn.setFixedSize(RESET_BTN_WIDTH, RESET_BTN_HEIGHT)
            clear_btn.setStyleSheet(RESET_BASE_STYLE)
            clear_btn.clicked.connect(lambda checked, k=key, b=btn: self._reset_color(k, b))
            grid.addWidget(clear_btn, row, 3)
            self.color_btns[key] = btn
            row += 1
    
        self.font_btns = {}
        for fkey, flabel in FONT_LABELS:
            grid.addWidget(QLabel(self.tr(flabel)), row, 0)
            btn = QPushButton()
            btn.setFixedSize(PICK_BTN_WIDTH, PICK_BTN_HEIGHT)
            self._refresh_font_btn(btn, fkey)
            btn.clicked.connect(lambda checked, k=fkey, b=btn: self._pick_font(k, b))
            grid.addWidget(btn, row, 2)
    
            clear_f = QPushButton(self.tr("Reset"))
            clear_f.setFixedSize(RESET_BTN_WIDTH, RESET_BTN_HEIGHT)
            clear_f.setStyleSheet(RESET_BASE_STYLE)
            clear_f.clicked.connect(lambda checked, k=fkey, b=btn: self._reset_font(k, b))
            grid.addWidget(clear_f, row, 3)
            self.font_btns[fkey] = btn
            row += 1
    
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        layout.addStretch()

    # ------------------------------------------------------------------
    def _refresh_color_btn(self, btn, key):
        stored = self._stored.get(key, SENTINEL)
        if stored == SENTINEL or stored == "" or stored is None:
            btn.setStyleSheet(BTN_BASE_STYLE)
            btn.setText(self.tr("Default Value"))
        else:
            btn.setStyleSheet(f"background-color: {stored}; {BTN_BASE_STYLE}")
            btn.setText("")

    def _reset_color(self, key, btn):
        self._stored[key] = SENTINEL
        self._refresh_color_btn(btn, key)

    def _pick_color(self, key, btn):
        stored = self._stored.get(key, SENTINEL)
        initial = QColor(stored) if stored and stored != SENTINEL else QColor(self._tm.resolve(key) or "#ffffff")
        color = QColorDialog.getColor(initial, self, self.tr("Select Color"))
        if color.isValid():
            self._stored[key] = color.name()
            self._refresh_color_btn(btn, key)

    def _refresh_font_btn(self, btn, key):
        stored = self._stored.get(key, SENTINEL)
        btn.setFont(QFont())  # always standard UI font on the button itself
        btn.setStyleSheet(BTN_BASE_STYLE)
        if stored == SENTINEL or stored == "" or stored is None:
            btn.setText(self.tr("Default Value"))
        else:
            f = QFont()
            f.fromString(stored)
            label = f"{f.family()}, {f.pointSize()}pt"
            # Elide long font names so text never forces the fixed-size
            # button to look truncated/overflowed differently across platforms.
            fm = QFontMetrics(btn.font())
            available = btn.width() - 16  # rough padding allowance
            elided = fm.elidedText(label, Qt.ElideRight, available)
            btn.setText(elided)
            btn.setToolTip(label)

    def _reset_font(self, key, btn):
        self._stored[key] = SENTINEL
        self._refresh_font_btn(btn, key)

    def _pick_font(self, key, btn):
        stored = self._stored.get(key, SENTINEL)
        f = QFont()
        if stored and stored != SENTINEL:
            f.fromString(stored)
        font, ok = QFontDialog.getFont(f, self, self.tr("Select Font"))
        if ok:
            self._stored[key] = font.toString()
            self._refresh_font_btn(btn, key)

    def save(self):
        for key, stored in self._stored.items():
            self.settings.setValue(f"theme_{key}", stored if stored is not None else SENTINEL)
