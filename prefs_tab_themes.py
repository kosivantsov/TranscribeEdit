"""prefs_tab_themes.py — "Themes and Colors" Preferences tab.

Tab order in Preferences: Dependencies → Export → Speakers → Editor →
                           [THIS TAB] → Shortcuts

Contains:
  * Theme mode selector (Auto / Light / Dark)
  * Waveform color pickers (fg + bg)
  * Timetable color pickers + font picker (fg + bg + font)
  * Named theme save / load / delete
"""

import os

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QPushButton, QComboBox, QColorDialog,
    QFontDialog, QInputDialog, QMessageBox, QSizePolicy,
)
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtCore import Qt

from theme_manager import SENTINEL, ThemeManager


class ThemesTab(QWidget):
    TAB_LABEL = "Themes and Colors"

    def __init__(self, parent, settings, theme_manager: ThemeManager):
        super().__init__(parent)
        self.settings = settings
        self._tm = theme_manager

        _wt_keys = ["waveform_fg", "waveform_bg", "timetable_fg", "timetable_bg", "timetable_font"]
        self._stored = {k: settings.value(f"theme_{k}", SENTINEL) for k in _wt_keys}
        self._mode = settings.value("theme_mode", "auto")

        self._color_btns = {}
        self._font_btns = {}

        self._build_ui()
        self._refresh_theme_list()

    # ------------------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ---- Mode selector ----
        mode_box = QGroupBox(self.tr("Theme Mode"))
        mode_layout = QHBoxLayout(mode_box)
        mode_layout.addWidget(QLabel(self.tr("Mode:")))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Auto", "Light", "Dark"])
        self.mode_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        ideal_width = self.mode_combo.minimumSizeHint().width() + 30
        self.mode_combo.view().setMinimumWidth(ideal_width)
        mode_map = {"auto": 0, "light": 1, "dark": 2}
        self.mode_combo.setCurrentIndex(mode_map.get(self._mode, 0))
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addStretch()
        layout.addWidget(mode_box)

        # ---- Waveform ----
        wf_box = QGroupBox(self.tr("Waveform Colors"))
        wf_layout = QHBoxLayout(wf_box)
        self._add_color_row(wf_layout, "waveform_fg", self.tr("Foreground"))
        self._add_color_row(wf_layout, "waveform_bg", self.tr("Background"))
        layout.addWidget(wf_box)

        # ---- Timetable ----
        tt_box = QGroupBox(self.tr("Timetable (Position Display) Colors & Font"))
        tt_layout = QHBoxLayout(tt_box)
        self._add_color_row(tt_layout, "timetable_fg", self.tr("Foreground"))
        self._add_color_row(tt_layout, "timetable_bg", self.tr("Background"))
        self._add_font_row(tt_layout, "timetable_font", self.tr("Font"))
        layout.addWidget(tt_box)

        # ---- Named themes ----
        nt_box = QGroupBox(self.tr("Named Themes"))
        nt_layout = QVBoxLayout(nt_box)

        save_row = QHBoxLayout()
        save_row.addWidget(QLabel(self.tr("Save current config as:")))
        self.save_btn = QPushButton(self.tr("Save Theme…"))
        self.save_btn.clicked.connect(self._save_theme)
        save_row.addWidget(self.save_btn)
        save_row.addStretch()
        nt_layout.addLayout(save_row)

        load_row = QHBoxLayout()
        load_row.addWidget(QLabel(self.tr("Saved themes:")))
        self.theme_combo = QComboBox()
        self.theme_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        load_row.addWidget(self.theme_combo)
        self.load_btn = QPushButton(self.tr("Load"))
        self.load_btn.clicked.connect(self._load_theme)
        load_row.addWidget(self.load_btn)
        self.del_btn = QPushButton(self.tr("Delete"))
        self.del_btn.clicked.connect(self._delete_theme)
        load_row.addWidget(self.del_btn)
        nt_layout.addLayout(load_row)

        layout.addWidget(nt_box)
        layout.addStretch()

    # ------------------------------------------------------------------
    def _add_color_row(self, parent_layout, key, label_text):
        col = QVBoxLayout()
        col.addWidget(QLabel(label_text))
        btn = QPushButton()
        btn.setMinimumWidth(80)
        self._stored.setdefault(key, SENTINEL)
        self._refresh_color_btn(btn, key)
        btn.clicked.connect(lambda _checked=False, k=key, b=btn: self._pick_color(k, b))
        col.addWidget(btn)
        reset = QPushButton(self.tr("Reset"))
        reset.clicked.connect(lambda _checked=False, k=key, b=btn: self._reset_color(k, b))
        col.addWidget(reset)
        parent_layout.addLayout(col)
        self._color_btns[key] = btn

    def _add_font_row(self, parent_layout, key, label_text):
        col = QVBoxLayout()
        col.addWidget(QLabel(label_text))
        btn = QPushButton()
        btn.setMinimumWidth(80)
        self._stored.setdefault(key, SENTINEL)
        self._refresh_font_btn(btn, key)
        btn.clicked.connect(lambda _checked=False, k=key, b=btn: self._pick_font(k, b))
        col.addWidget(btn)
        reset = QPushButton(self.tr("Reset"))
        reset.clicked.connect(lambda _checked=False, k=key, b=btn: self._reset_font(k, b))
        col.addWidget(reset)
        parent_layout.addLayout(col)
        self._font_btns[key] = btn

    # ------------------------------------------------------------------
    def _refresh_color_btn(self, btn, key):
        stored = self._stored.get(key, SENTINEL)
        if stored == SENTINEL or stored == "" or stored is None:
            btn.setStyleSheet("")
            btn.setText(self.tr("Default Value"))
        else:
            btn.setStyleSheet(f"background-color: {stored};")
            btn.setText("")

    def _refresh_font_btn(self, btn, key):
        stored = self._stored.get(key, SENTINEL)
        btn.setFont(QFont())
        if stored == SENTINEL or stored == "" or stored is None:
            btn.setText(self.tr("Default Value"))
        else:
            f = QFont()
            f.fromString(stored)
            btn.setText(f"{f.family()}, {f.pointSize()}pt")

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

    def _on_mode_changed(self, idx):
        self._mode = ["auto", "light", "dark"][idx]

    # ------------------------------------------------------------------
    def _refresh_theme_list(self):
        self.theme_combo.clear()
        for name in self._tm.list_named_themes():
            self.theme_combo.addItem(name)

    def _save_theme(self):
        name, ok = QInputDialog.getText(self, self.tr("Save Theme"), self.tr("Theme name:"))
        if not ok or not name.strip():
            return
        name = name.strip()
        self._commit_to_settings()
        self._tm.save_named_theme(name)
        self._refresh_theme_list()
        idx = self.theme_combo.findText(name)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)

    def _load_theme(self):
        name = self.theme_combo.currentText()
        if not name:
            return
        try:
            self._tm.load_named_theme(name)
        except FileNotFoundError:
            QMessageBox.warning(self, self.tr("Error"), self.tr(f"Theme '{name}' not found."))
            return
        for key in list(self._stored.keys()):
            self._stored[key] = self.settings.value(f"theme_{key}", SENTINEL)
        self._mode = self.settings.value("theme_mode", "auto")
        mode_map = {"auto": 0, "light": 1, "dark": 2}
        self.mode_combo.setCurrentIndex(mode_map.get(self._mode, 0))
        for key, btn in self._color_btns.items():
            self._refresh_color_btn(btn, key)
        for key, btn in self._font_btns.items():
            self._refresh_font_btn(btn, key)

    def _delete_theme(self):
        name = self.theme_combo.currentText()
        if not name:
            return
        ans = QMessageBox.question(
            self, self.tr("Delete Theme"),
            self.tr(f"Delete theme '{name}'?"),
            QMessageBox.Yes | QMessageBox.No,
        )
        if ans == QMessageBox.Yes:
            self._tm.delete_named_theme(name)
            self._refresh_theme_list()

    # ------------------------------------------------------------------
    def _commit_to_settings(self):
        self.settings.setValue("theme_mode", self._mode)
        for key, stored in self._stored.items():
            self.settings.setValue(f"theme_{key}", stored if stored is not None else SENTINEL)

    def save(self):
        self._commit_to_settings()
        self._tm.stored_mode = self._mode
        self._tm.apply_all()
