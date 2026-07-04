"""DialogsMixin — app-level dialog handlers extracted from main.py."""
from PyQt5.QtWidgets import QMessageBox, QDialog, QApplication
from PyQt5.QtGui import QFont, QKeySequence, QDesktopServices
from PyQt5.QtCore import QUrl


class DialogsMixin:

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

    def open_cloud_config(self):
        from cloud_config_dialog import CloudConfigDialog
        dlg = CloudConfigDialog(self)
        dlg.exec_()

    def open_handy_config(self):
        from handy_config_dialog import HandyConfigDialog
        dlg = HandyConfigDialog(self, self.settings)
        dlg.exec_()

    def open_preferences_dialog(self, jump_to_tab=None):
        from preferences_dialog import PreferencesDialog
        from prefs_tab_shortcuts import ShortcutsTab
        from prefs_tab_editor import EditorTab
        from prefs_tab_speakers import SpeakersTab
        from prefs_tab_deps import DepsTab
        from prefs_tab_export import ExportTab
        from prefs_tab_themes import ThemesTab

        # Safely fetch theme_mgr (defaults to None if missing in the host class)
        theme_mgr = getattr(self, "theme_mgr", None)

        # Tab order: Dependencies → Export → Speakers → Editor → Themes and Colors → Shortcuts
        tabs = [
            DepsTab(self, self.settings),
            ExportTab(self, self.settings),
            SpeakersTab(self, self.settings, self.speakers),
            EditorTab(self, self.settings),
            ThemesTab(self, self.settings, theme_mgr),  # <-- Use the safe variable here
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
            
            # <-- Add safety check before applying themes
            if hasattr(self, "theme_mgr"):
                self.theme_mgr.apply_all()
                
            self.speakers = [
                self.settings.value(f"speaker_{i}", f"SPEAKER_0{i}") for i in range(6)
            ]
            self.update_dynamic_menus()

    def open_editor_config(self):
        """Open Preferences jumped directly to the Editor tab (index 3)."""
        self.open_preferences_dialog(jump_to_tab=3)

    def open_themes_config(self):
        """Open Preferences jumped directly to the Themes and Colors tab (index 4)."""
        self.open_preferences_dialog(jump_to_tab=4)

    def update_dynamic_menus(self):
        fmt = self.settings.value("export_default_format", "srt")
        if "Export Default" in self.menu_actions:
            self.menu_actions["Export Default"].setText(
                self.tr(f"Export Default ({fmt.upper()})")
            )

    def apply_editor_config(self):
        """Shim: delegate everything to ThemeManager."""
        if hasattr(self, "theme_mgr"):
            self.theme_mgr.apply_all()

    def clipboard_cut(self):
        w = QApplication.focusWidget()
        if hasattr(w, "cut"): w.cut()

    def clipboard_copy(self):
        w = QApplication.focusWidget()
        if hasattr(w, "copy"): w.copy()

    def clipboard_paste(self):
        w = QApplication.focusWidget()
        if hasattr(w, "paste"): w.paste()
