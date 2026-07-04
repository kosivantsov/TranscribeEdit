"""theme_manager.py — Central theme authority for TranscribeEdit.

Responsibilities
----------------
* Resolve `__default__` sentinel values against the active mode's built-in
  palette (never writing the resolved value back to QSettings).
* Propagate a Light/Dark mode change to every registered listener.
* Save / load named themes to/from JSON files in the platform AppData dir.
* Push resolved values into the editor highlighter, WaveformWidget, and
  ColorLabel (timetable) widgets.

Usage (from AudioPlayer.__init__)::

    from theme_manager import ThemeManager
    self.theme_mgr = ThemeManager(self.settings)
    self.theme_mgr.register_targets(
        editor=self.editor,
        waveform=self.waveform,
        timetable=self.time_label,
    )
    self.theme_mgr.apply_all()
"""

import json
import os

from PyQt5.QtCore import QSettings, QStandardPaths
from PyQt5.QtGui import QColor, QFont

import qdarktheme

from theme_defaults import get_defaults, ALL_KEYS

SENTINEL = "__default__"


def _effective_mode(stored_mode: str) -> str:
    """Resolve 'auto' to 'light' or 'dark' by asking qdarktheme."""
    if stored_mode in ("light", "dark"):
        return stored_mode
    try:
        resolved = qdarktheme.get_theme()
        return resolved if resolved in ("light", "dark") else "dark"
    except Exception:
        pass
    # Palette heuristic: dark if window background luma < 128
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            bg = app.palette().window().color()
            luma = 0.299 * bg.red() + 0.587 * bg.green() + 0.114 * bg.blue()
            return "dark" if luma < 128 else "light"
    except Exception:
        pass
    return "dark"


def _themes_dir() -> str:
    base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    path = os.path.join(base, "themes")
    os.makedirs(path, exist_ok=True)
    return path


class ThemeManager:
    def __init__(self, settings: QSettings):
        self._settings = settings
        self._editor = None
        self._waveform = None
        self._timetable = None

    # ------------------------------------------------------------------
    # Target registration
    # ------------------------------------------------------------------

    def register_targets(self, editor=None, waveform=None, timetable=None):
        if editor is not None:
            self._editor = editor
        if waveform is not None:
            self._waveform = waveform
        if timetable is not None:
            self._timetable = timetable

    # ------------------------------------------------------------------
    # Mode helpers
    # ------------------------------------------------------------------

    @property
    def stored_mode(self) -> str:
        return self._settings.value("theme_mode", "auto")

    @stored_mode.setter
    def stored_mode(self, value: str):
        self._settings.setValue("theme_mode", value)

    @property
    def effective_mode(self) -> str:
        return _effective_mode(self.stored_mode)

    # ------------------------------------------------------------------
    # Value resolution
    # ------------------------------------------------------------------

    def resolve(self, key: str) -> str:
        """Return the concrete value for *key*, resolving SENTINEL if needed."""
        stored = self._settings.value(f"theme_{key}", SENTINEL)
        if stored == SENTINEL or stored is None or stored == "":
            return get_defaults(self.effective_mode).get(key, "")
        return stored

    def is_custom(self, key: str) -> bool:
        stored = self._settings.value(f"theme_{key}", SENTINEL)
        return stored not in (SENTINEL, None, "")

    def set_value(self, key: str, value: str):
        """Store a concrete value; pass SENTINEL to reset to default."""
        self._settings.setValue(f"theme_{key}", value)

    def reset_to_default(self, key: str):
        self._settings.setValue(f"theme_{key}", SENTINEL)

    # ------------------------------------------------------------------
    # Apply all settings to registered widgets
    # ------------------------------------------------------------------

    def apply_all(self):
        self._apply_theme_mode()
        self._apply_editor()
        self._apply_waveform()
        self._apply_timetable()

    def _apply_theme_mode(self):
        mode = self.stored_mode
        try:
            qdarktheme.setup_theme(mode)
        except AttributeError:
            from PyQt5.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                try:
                    m = "dark" if _effective_mode(mode) == "dark" else "light"
                    app.setStyleSheet(qdarktheme.load_stylesheet(m))
                except Exception:
                    pass

    def _apply_editor(self):
        if self._editor is None:
            return

        txt_fg = self.resolve("text_fg")
        txt_bg = self.resolve("text_bg")

        sheet = "QPlainTextEdit { "
        if txt_fg:
            sheet += f"color: {txt_fg}; "
        if txt_bg:
            sheet += f"background-color: {txt_bg}; "
        sheet += "}"
        self._editor.setStyleSheet(sheet)

        font_str = self.resolve("font")
        if font_str:
            f = QFont()
            f.fromString(font_str)
            self._editor.setFont(f)

        color_keys = [
            "ts_fg", "ts_bg", "spk_fg", "spk_bg",
            "md_heading_fg", "md_hr_fg",
            "md_list_bg", "md_list_marker_fg", "md_markup_fg",
            "md_code_bg", "md_code_fg", "md_blockquote_fg",
            "comment_fg", "comment_bg",
        ]
        font_keys = ["ts_font", "spk_font", "md_code_font", "md_markup_font", "comment_font"]
        colors = {}
        for k in color_keys:
            colors[k] = self.resolve(k)
        for k in font_keys:
            colors[k] = self.resolve(k)
        self._editor.highlighter.update_formats(colors)

    def _apply_waveform(self):
        if self._waveform is None:
            return
        fg = self.resolve("waveform_fg")
        bg = self.resolve("waveform_bg")
        self._waveform.set_colors(fg, bg)

    def _apply_timetable(self):
        if self._timetable is None:
            return
        fg = self.resolve("timetable_fg")
        bg = self.resolve("timetable_bg")
        font_str = self.resolve("timetable_font")
        self._timetable.apply_theme_colors(fg, bg, font_str)

    # ------------------------------------------------------------------
    # Mode switch
    # ------------------------------------------------------------------

    def switch_mode(self, new_mode: str):
        """Change stored_mode and re-apply all defaults (customs unchanged)."""
        self.stored_mode = new_mode
        self.apply_all()

    # ------------------------------------------------------------------
    # Named theme save / load
    # ------------------------------------------------------------------

    def save_named_theme(self, name: str):
        """Resolve every key to its current concrete value and write to JSON."""
        data = {"theme_mode": self.stored_mode}
        for key in ALL_KEYS:
            data[key] = self.resolve(key)
        path = os.path.join(_themes_dir(), f"{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_named_theme(self, name: str):
        """Load a named theme: every key becomes custom (no sentinel)."""
        path = os.path.join(_themes_dir(), f"{name}.json")
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Theme file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "theme_mode" in data:
            self.stored_mode = data["theme_mode"]
        for key in ALL_KEYS:
            if key in data:
                self._settings.setValue(f"theme_{key}", data[key])
        self.apply_all()

    def list_named_themes(self) -> list:
        d = _themes_dir()
        return sorted(
            os.path.splitext(fn)[0]
            for fn in os.listdir(d)
            if fn.endswith(".json")
        )

    def delete_named_theme(self, name: str):
        path = os.path.join(_themes_dir(), f"{name}.json")
        if os.path.isfile(path):
            os.remove(path)
