# dialogs_mixin.py
"""DialogsMixin — app-level dialog handlers extracted from main.py.

Covers: About, Online Help, Cloud Config, Preferences dialog,
and the apply_editor_config helper.
"""
from PyQt5.QtWidgets import QMessageBox, QDialog, QApplication
from PyQt5.QtGui import QFont, QKeySequence, QDesktopServices
from PyQt5.QtCore import QUrl


class DialogsMixin:
    """Mixin providing app-level dialog handlers for AudioPlayer."""

    # ------------------------------------------------------------------ about / help
    def show_about(self):
        QMessageBox.about(
            self,
            self.tr("About TranscribeEdit"),
            self.tr(
                "<h3>TranscribeEdit</h3>"
                "<p>A professional transcription editor with waveform support.</p>"
                "<p>License: MIT</p>"
                "<p><a href='https://github.com/kosivantsov/TranscribeEdit'>GitHub Repository</a></p>"
            ),
        )

    def open_online_help(self):
        QDesktopServices.openUrl(QUrl("https://github.com/kosivantsov/TranscribeEdit"))

    # ------------------------------------------------------------------ cloud config
    def open_cloud_config(self):
        from cloud_config_dialog import CloudConfigDialog
        dlg = CloudConfigDialog(self)
        dlg.exec_()

    # ------------------------------------------------------------------ handy config
    def open_handy_config(self):
        from handy_config_dialog import HandyConfigDialog
        dlg = HandyConfigDialog(self, self.settings)
        dlg.exec_()

    # ------------------------------------------------------------------ preferences
    def open_preferences_dialog(self, jump_to_tab=None):
        from preferences_dialog import PreferencesDialog
        from prefs_tab_shortcuts import ShortcutsTab
        from prefs_tab_editor import EditorTab
        from prefs_tab_speakers import SpeakersTab
        from prefs_tab_deps import DepsTab
        from prefs_tab_export import ExportTab

        # Tab order: Dependencies → Export Options → Speakers → Editor → Shortcuts
        tabs = [
            DepsTab(self, self.settings),
            ExportTab(self, self.settings),
            SpeakersTab(self, self.settings, self.speakers),
            EditorTab(self, self.settings),
            ShortcutsTab(self, self.settings, self.current_shortcuts),
        ]

        dlg = PreferencesDialog(self, tabs)

        if jump_to_tab is not None:
            dlg.jump_to_tab(jump_to_tab)

        if dlg.exec_() == QDialog.Accepted:
            from shortcuts import DEFAULT_SHORTCUTS
            for name, default_seq in DEFAULT_SHORTCUTS.items():
                self.current_shortcuts[name] = self.settings.value(
                    f"shortcut_{name}", default_seq
                )
            self.apply_shortcuts()
            self.apply_editor_config()
            self.speakers = [
                self.settings.value(f"speaker_{i}", f"SPEAKER_0{i}") for i in range(6)
            ]
            self.update_dynamic_menus()

    def open_editor_config(self):
        """Open Preferences jumped directly to the Editor tab (index 3)."""
        self.open_preferences_dialog(jump_to_tab=3)

    def update_dynamic_menus(self):
        fmt = self.settings.value("export_default_format", "srt")
        if "Export Default" in self.menu_actions:
            self.menu_actions["Export Default"].setText(
                self.tr(f"Export Default ({fmt.upper()})")
            )

    # ------------------------------------------------------------------ editor config
    def apply_editor_config(self):
        txt_fg = self.settings.value("editor_text_fg", "")
        txt_bg = self.settings.value("editor_text_bg", "")

        sheet = "QPlainTextEdit { "
        if txt_fg:
            sheet += f"color: {txt_fg}; "
        if txt_bg:
            sheet += f"background-color: {txt_bg}; "
        sheet += "}"
        self.editor.setStyleSheet(sheet)

        font_str = self.settings.value("editor_font", "")
        if font_str:
            font = QFont()
            font.fromString(font_str)
            self.editor.setFont(font)

        color_keys = [
            "ts_fg", "ts_bg", "spk_fg", "spk_bg",
            "md_heading_fg", "md_hr_fg",
            "md_list_bg", "md_list_marker_fg", "md_markup_fg",
            "md_code_bg", "md_code_fg", "md_blockquote_fg",
            "comment_fg", "comment_bg",
        ]
        font_keys = [
            "ts_font", "spk_font", "md_code_font", "md_markup_font", "comment_font",
        ]
        colors = {}
        for k in color_keys:
            colors[k] = self.settings.value(f"editor_{k}", "")
        for k in font_keys:
            colors[k] = self.settings.value(f"editor_{k}", "")
        self.editor.highlighter.update_formats(colors)

    # ------------------------------------------------------------------ edit menu helpers
    def clipboard_cut(self):
        w = QApplication.focusWidget()
        if hasattr(w, "cut"):
            w.cut()

    def clipboard_copy(self):
        w = QApplication.focusWidget()
        if hasattr(w, "copy"):
            w.copy()

    def clipboard_paste(self):
        w = QApplication.focusWidget()
        if hasattr(w, "paste"):
            w.paste()
