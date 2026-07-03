# main.py
import sys
import os
import json
import signal
import platform
import zipfile
import tempfile
import shutil
import qdarktheme
import locale
from urllib.parse import urlparse

import mpv
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QGridLayout, QPushButton, QLabel, QSlider,
    QFileDialog, QSplitter, QMessageBox, QProgressDialog,
    QShortcut, QStatusBar, QFrame, QDialog)
from PyQt5.QtCore import Qt, QTimer, QSettings, QTranslator, QLibraryInfo, QLocale, QUrl
from PyQt5.QtGui import QKeySequence, QFont, QIcon, QDesktopServices

from utils import seconds_to_ts
from widgets import WaveformWidget, ColorLabel, JumpDialog, FindDialog
from editor import TranscriptEditor
from cloud_client import CloudWorker, CloudWorkerSignals
from shortcuts import DEFAULT_SHORTCUTS
from cli_connector import CliTranscribeWorker, CliTranscribeSignals

from menu_builder import build_main_menu
from exporter import export as export_segments, get_filter
from prefs_tab_deps import check_and_store_deps, DepsDialog, get_dep_path

if platform.system() == 'Linux' and 'QT_QPA_PLATFORMTHEME' not in os.environ:
    os.environ['QT_QPA_PLATFORMTHEME'] = 'qt5ct'
os.environ["QT_LOGGING_RULES"] = "qt.qpa.fonts=false"

def sigint_handler(*args): QApplication.quit()
signal.signal(signal.SIGINT, sigint_handler)

def get_app_icon():
    sys_name = platform.system()
    if sys_name == 'Windows': ext = 'ico'
    elif sys_name == 'Darwin': ext = 'icns'
    else: ext = 'png'
    return QIcon(os.path.join("icons", f"transcribeedit.{ext}"))

class AudioPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.tr("TranscribeEdit"))
        self.setWindowIcon(get_app_icon())
        self.setMinimumSize(900, 850)

        self.settings = QSettings("TranscribeEdit", "TranscribeEdit")
        
        missing_deps = check_and_store_deps(self.settings)
        if missing_deps:
            QTimer.singleShot(0, self.show_deps_dialog)

        self.speakers = []
        for i in range(6):
            self.speakers.append(self.settings.value(f"speaker_{i}", f"SPEAKER_0{i}"))

        self.audio_file = None
        self.player = None
        self.current_pos = 0
        self.duration = 0
        self.volume = 80
        self.speed = 1.0
        self.window_size = 1.0
        self.is_playing = False
        self.on_top_flag = False

        self.current_json_path = None
        self.current_project_path = None
        self.active_qshortcuts = []
        
        self._build_ui()
        self.menu_actions = build_main_menu(self)
        
        self._connect_signals()
        self._setup_shortcuts()
        self.apply_editor_config()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(50)

        self.update_status_bar()

    def show_deps_dialog(self):
        dlg = DepsDialog(self, self.settings, missing_only=True)
        dlg.exec_()

    def _build_ui(self):
        root = QWidget(); self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        splitter = QSplitter(Qt.Vertical)
        root_layout.addWidget(splitter, stretch=1)

        top = QWidget(); tv = QVBoxLayout(top)
        self.file_label = QLabel(self.tr("No file loaded"))
        self.file_label.setAlignment(Qt.AlignCenter)
        self.file_label.setStyleSheet("font: 11pt; color: gray;")
        tv.addWidget(self.file_label)

        self.time_label = ColorLabel("00:00:00.00 / 00:00:00.00")
        tv.addWidget(self.time_label)

        win_frame = QFrame()
        win_vbox = QVBoxLayout(win_frame)
        win_vbox.setContentsMargins(0,0,0,0)
        win_vbox.setSpacing(6)
        lbl = QLabel(self.tr("Waveform Window"))
        lbl.setAlignment(Qt.AlignCenter)
        win_vbox.addWidget(lbl)

        win_hbox = QHBoxLayout()
        win_hbox.setContentsMargins(0,0,0,0)
        win_hbox.setAlignment(Qt.AlignCenter)
        self.win_btns = []
        for size in [0.1, 0.5, 1.0, 2.0, 5.0]:
            btn = QPushButton(f"{size}s")
            btn.setCheckable(True)
            self.win_btns.append((btn, size))
            win_hbox.addWidget(btn)
        self.win_btns[2][0].setChecked(True)
        win_vbox.addLayout(win_hbox)
        tv.addWidget(win_frame)

        self.waveform = WaveformWidget()
        tv.addWidget(self.waveform)

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(30)

        seek_frame = QFrame()
        seek_layout = QVBoxLayout(seek_frame)
        seek_layout.setContentsMargins(0,0,0,0)
        seek_layout.setSpacing(6)
        lbl_seek = QLabel(self.tr("Seek"))
        lbl_seek.setAlignment(Qt.AlignCenter)
        seek_layout.addWidget(lbl_seek)

        seek_grid = QGridLayout()
        seek_grid.setContentsMargins(0,0,0,0)
        seek_data = [
            ("-0.1s", -0.1), ("-0.5s", -0.5), ("+0.5s", +0.5), ("+0.1s", +0.1),
            ("-1s", -1.0), ("-5s", -5.0), ("+5s", +5.0), ("+1s", +1.0)
        ]
        self.seek_btns = []
        for i, (lbl_txt, val) in enumerate(seek_data):
            btn = QPushButton(lbl_txt)
            seek_grid.addWidget(btn, i // 4, i % 4)
            self.seek_btns.append((btn, val))
        seek_layout.addLayout(seek_grid)
        controls_layout.addWidget(seek_frame, 1)

        pb_frame = QFrame()
        pb_layout = QVBoxLayout(pb_frame)
        pb_layout.setContentsMargins(0,0,0,0)
        pb_layout.setSpacing(6)
        lbl_pb = QLabel(self.tr("Playback/Speed"))
        lbl_pb.setAlignment(Qt.AlignCenter)
        pb_layout.addWidget(lbl_pb)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0,0,0,0)
        self.stop_btn = QPushButton(self.tr("■ Stop"))
        self.play_btn = QPushButton(self.tr("▶ Play"))
        self.jump_btn = QPushButton(self.tr("Jump…"))
        btn_row.addWidget(self.stop_btn); btn_row.addWidget(self.play_btn); btn_row.addWidget(self.jump_btn)
        pb_layout.addLayout(btn_row)

        spd_row = QHBoxLayout()
        spd_row.setContentsMargins(0,0,0,0)
        self.speed_btns = []
        for sp in [0.25, 0.5, 0.75, 1.0]:
            btn = QPushButton(f"{int(sp*100)}%")
            btn.setCheckable(True)
            self.speed_btns.append((btn, sp))
            spd_row.addWidget(btn)
        self.speed_btns[-1][0].setChecked(True)
        self.speed_minus = QPushButton("-")
        self.speed_plus = QPushButton("+")
        spd_row.addWidget(self.speed_minus); spd_row.addWidget(self.speed_plus)
        pb_layout.addLayout(spd_row)
        controls_layout.addWidget(pb_frame, 1)

        tv.addLayout(controls_layout)

        vol_row = QHBoxLayout()
        vol_row.addWidget(QLabel(self.tr("Volume:")))
        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100); self.vol_slider.setValue(self.volume)
        vol_row.addWidget(self.vol_slider)
        tv.addLayout(vol_row)

        splitter.addWidget(top)

        bottom = QWidget(); bv = QVBoxLayout(bottom)
        ed_toolbar = QHBoxLayout()
        self.copy_ts_btn = QPushButton(self.tr("Insert Timestamp"))
        self.jump_from_ed_btn = QPushButton(self.tr("Jump to Timestamp"))
        self.highlight_ts_btn = QPushButton(self.tr("Highlight Closest Timestamp"))
        self.highlight_ts_btn.setCheckable(True) 
        self.insert_speaker_btn = QPushButton(self.tr("Insert Speaker Tag"))

        ed_toolbar.addWidget(self.copy_ts_btn)
        ed_toolbar.addWidget(self.jump_from_ed_btn)
        ed_toolbar.addWidget(self.highlight_ts_btn)
        ed_toolbar.addWidget(self.insert_speaker_btn)
        ed_toolbar.addStretch()
        bv.addLayout(ed_toolbar)

        self.editor = TranscriptEditor()
        bv.addWidget(self.editor, stretch=1)

        splitter.addWidget(bottom)
        splitter.setSizes([450, 400])

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel()
        self.status_bar.addWidget(self.status_label)

    def update_status_bar(self):
        is_modified = getattr(self, 'editor', None) and self.editor.document().isModified()

        if self.current_project_path:
            # Project mode
            proj_name = os.path.basename(self.current_project_path)
            editor_status = self.tr("UNSAVED") if is_modified else self.tr("SAVED")
            self.status_label.setText(self.tr("Project: {0} | Editor: {1}").format(proj_name, editor_status))
        else:
            # Standard audio/json mode
            audio_name = os.path.basename(self.audio_file) if self.audio_file else self.tr("No Audio")
            
            if self.current_json_path:
                json_name = os.path.basename(self.current_json_path)
            else:
                json_name = self.tr("Unsaved data")
                
            if is_modified:
                json_name += " *"
                
            self.status_label.setText(self.tr("Audio: {0} | Editor: {1}").format(audio_name, json_name))

    def _connect_signals(self):
        self.play_btn.clicked.connect(self.play_pause)
        self.stop_btn.clicked.connect(self.stop)
        self.jump_btn.clicked.connect(self.open_jump_dialog)
        self.copy_ts_btn.clicked.connect(self.insert_timestamp)
        self.jump_from_ed_btn.clicked.connect(self.editor.jump_to_timestamp_at_cursor)
        self.insert_speaker_btn.clicked.connect(lambda: self.editor.insert_or_cycle_speaker(self.speakers))
        self.highlight_ts_btn.toggled.connect(self.on_highlight_toggled)

        self.vol_slider.valueChanged.connect(self.on_volume_change)
        self.speed_minus.clicked.connect(self.decrease_speed)
        self.speed_plus.clicked.connect(self.increase_speed)

        for btn, val in self.seek_btns:
            btn.clicked.connect(lambda checked, v=val: self.seek_rel(v))
        for btn, val in self.win_btns:
            btn.clicked.connect(lambda checked, v=val: self.set_window_size(v))
        for btn, val in self.speed_btns:
            btn.clicked.connect(lambda checked, v=val: self.set_speed(v))

        self.editor.jump_requested.connect(self.seek_to)
        self.editor.document().modificationChanged.connect(self.update_status_bar)

    def on_highlight_toggled(self, checked):
        if checked: self.editor.highlight_closest_timestamp(self.current_pos)
        else: self.editor.clear_highlight()

    def open_find_dialog(self):
        if getattr(self, 'find_dialog', None) is None:
            self.find_dialog = FindDialog(self, self.editor)
        self.find_dialog.show()
        self.find_dialog.activateWindow()
        self.find_dialog.search_input.setFocus()
        self.find_dialog.search_input.selectAll()
        
    def find_next_silent(self):
        if getattr(self, 'find_dialog', None) and self.find_dialog.search_input.text():
            self.find_dialog._do_find(False)
        else:
            self.open_find_dialog()

    def find_prev_silent(self):
        if getattr(self, 'find_dialog', None) and self.find_dialog.search_input.text():
            self.find_dialog._do_find(True)
        else:
            self.open_find_dialog()

    def _setup_shortcuts(self):
        self.shortcut_handlers = {
            "Quit": self.quit_app,
            "Open Project": self.load_project,
            "Save Project": self.save_project,
            "Save Project As": self.save_project_as,
            "Play/Pause": self.play_pause,
            "Play/Pause (Alt)": self.play_pause,
            "Stop/Play": self.stop_play,
            "Stop": self.stop,
            "Jump Dialog": self.open_jump_dialog,
            "Insert Timestamp": self.insert_timestamp,
            "Insert Speaker Tag": lambda: self.editor.insert_or_cycle_speaker(self.speakers),
            "Toggle Highlight": self.highlight_ts_btn.toggle, 
            "Find": self.open_find_dialog,
            "Find Next": self.find_next_silent,
            "Find Prev": self.find_prev_silent,
            "Fold/Unfold": self.editor.toggle_fold_current,
            "Format Bold": self.editor.format_bold,
            "Format Italic": self.editor.format_italic,
            "Format Underline": lambda: self.editor.toggle_format("<u>", "</u>"),
            "Jump to Cursor": self.editor.jump_to_timestamp_at_cursor,
            "Increase Speed": self.increase_speed,
            "Decrease Speed": self.decrease_speed,
            "Speed 25%": lambda: self.set_speed(0.25),
            "Speed 50%": lambda: self.set_speed(0.50),
            "Speed 75%": lambda: self.set_speed(0.75),
            "Speed 100%": lambda: self.set_speed(1.0),
            "Volume Up": self.increase_volume,
            "Volume Down": self.decrease_volume,
            "Seek -0.1s": lambda: self.seek_rel(-0.1),
            "Seek +0.1s": lambda: self.seek_rel(0.1),
            "Seek -0.5s": lambda: self.seek_rel(-0.5),
            "Seek +0.5s": lambda: self.seek_rel(0.5),
            "Seek -1.0s": lambda: self.seek_rel(-1.0),
            "Seek +1.0s": lambda: self.seek_rel(1.0),
            "Seek -5.0s": lambda: self.seek_rel(-5.0),
            "Seek +5.0s": lambda: self.seek_rel(5.0),
            "Waveform 0.1s": lambda: self.set_window_size(0.1),
            "Waveform 0.5s": lambda: self.set_window_size(0.5),
            "Waveform 1.0s": lambda: self.set_window_size(1.0),
            "Waveform 2.0s": lambda: self.set_window_size(2.0),
            "Waveform 5.0s": lambda: self.set_window_size(5.0),
        }
        self.current_shortcuts = {}
        for name, default_seq in DEFAULT_SHORTCUTS.items():
            self.current_shortcuts[name] = self.settings.value(f"shortcut_{name}", default_seq)
        self.apply_shortcuts()

    def apply_shortcuts(self):
        for sc in self.active_qshortcuts:
            sc.deleteLater()
        self.active_qshortcuts.clear()

        for name, seq_str in self.current_shortcuts.items():
            if not seq_str: continue

            if name in self.menu_actions:
                self.menu_actions[name].setShortcut(QKeySequence(seq_str))
            elif name in self.shortcut_handlers:
                sc = QShortcut(QKeySequence(seq_str), self)
                sc.activated.connect(self.shortcut_handlers[name])
                self.active_qshortcuts.append(sc)

    def quit_app(self):
        self.close()

    def show_about(self):
        QMessageBox.about(
            self, self.tr("About TranscribeEdit"),
            self.tr("<h3>TranscribeEdit</h3>"
                    "<p>A professional transcription editor with waveform support.</p>"
                    "<p>License: MIT</p>"
                    "<p><a href='https://github.com/kosivantsov/TranscribeEdit'>GitHub Repository</a></p>")
        )

    def open_online_help(self):
        QDesktopServices.openUrl(QUrl("https://github.com/kosivantsov/TranscribeEdit"))

    def open_cloud_config(self):
        from cloud_config_dialog import CloudConfigDialog
        dlg = CloudConfigDialog(self)
        dlg.exec_()

    def open_preferences_dialog(self):
        from preferences_dialog import PreferencesDialog
        from prefs_tab_shortcuts import ShortcutsTab
        from prefs_tab_editor import EditorTab
        from prefs_tab_speakers import SpeakersTab
        from prefs_tab_handy import HandyTab
        from prefs_tab_deps import DepsTab
        from prefs_tab_export import ExportTab

        tabs = [
            ShortcutsTab(self, self.settings, self.current_shortcuts),
            EditorTab(self, self.settings),
            SpeakersTab(self, self.settings, self.speakers),
            HandyTab(self, self.settings),
            DepsTab(self, self.settings),
            ExportTab(self, self.settings)
        ]
        
        dlg = PreferencesDialog(self, tabs)
        if dlg.exec_() == QDialog.Accepted:
            for name, default_seq in DEFAULT_SHORTCUTS.items():
                self.current_shortcuts[name] = self.settings.value(f"shortcut_{name}", default_seq)
            self.apply_shortcuts()
            self.apply_editor_config()
            self.speakers = [self.settings.value(f"speaker_{i}", f"SPEAKER_0{i}") for i in range(6)]
            self.update_dynamic_menus()
            
    def update_dynamic_menus(self):
        fmt = self.settings.value("export_default_format", "srt")
        if "Export Default" in self.menu_actions:
            self.menu_actions["Export Default"].setText(self.tr(f"Export Default ({fmt.upper()})"))

    def apply_editor_config(self):
        txt_fg = self.settings.value("editor_text_fg", "")
        txt_bg = self.settings.value("editor_text_bg", "")

        sheet = "QPlainTextEdit { "
        if txt_fg: sheet += f"color: {txt_fg}; "
        if txt_bg: sheet += f"background-color: {txt_bg}; "
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
            # new colour settings
            "md_code_bg", "md_code_fg", "md_blockquote_fg",
        ]
        font_keys = [
            "ts_font", "spk_font", "md_code_font", "md_markup_font",
        ]
        colors = {}
        for k in color_keys:
            colors[k] = self.settings.value(f"editor_{k}", "")
        for k in font_keys:
            colors[k] = self.settings.value(f"editor_{k}", "")
        self.editor.highlighter.update_formats(colors)

    # --- PROJECT PACKAGING LOGIC ---
    def load_project(self):
        last_dir = self.settings.value("last_proj_dir", "")
        path, _ = QFileDialog.getOpenFileName(self, self.tr("Open Project"), last_dir, self.tr("TranscribeEdit Projects (*.teproj)"))
        if not path: return
        self.settings.setValue("last_proj_dir", os.path.dirname(path))

        temp_dir = os.path.join(tempfile.gettempdir(), "te_active_project")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        os.makedirs(temp_dir, exist_ok=True)

        try:
            with zipfile.ZipFile(path, 'r') as zf:
                zf.extractall(temp_dir)
                
            with open(os.path.join(temp_dir, "data.json"), 'r', encoding='utf-8') as f:
                data = json.load(f)

            audio_path = os.path.join(temp_dir, data.get("audio_file"))
            self._open_audio_path(audio_path)

            if "raw_text" in data:
                self.editor.setPlainText(data["raw_text"])
                self.editor.document().setModified(False)
            else:
                self.editor.load_segments(data.get("segments", []))
            
            self.current_pos = data.get("audio_pos", 0)
            self._restore_audio_position(self.current_pos)
            
            cursor_pos = data.get("cursor_pos", 0)
            cursor = self.editor.textCursor()
            cursor.setPosition(min(cursor_pos, self.editor.document().characterCount()))
            self.editor.setTextCursor(cursor)
            
            self.editor.ensureCursorVisible()
            self.editor.setFocus()
            
            self.current_project_path = path
            self.current_json_path = None
            self.update_status_bar()

        except Exception as e:
            QMessageBox.critical(self, self.tr("Project Load Error"), str(e))

    def save_project(self):
        if getattr(self, 'current_project_path', None):
            return self._do_save_project(self.current_project_path)
        return self.save_project_as()

    def save_project_as(self):
        last_dir = self.settings.value("last_proj_dir", "")
        path, _ = QFileDialog.getSaveFileName(self, self.tr("Save Project"), last_dir, self.tr("TranscribeEdit Projects (*.teproj)"))
        if path:
            if not path.lower().endswith('.teproj'): path += '.teproj'
            return self._do_save_project(path)
        return False

    def _do_save_project(self, path):
        if not self.audio_file or not os.path.exists(self.audio_file):
            QMessageBox.warning(self, self.tr("No Audio"), self.tr("Cannot save a project without an active audio file."))
            return False
        
        try:
            data = {
                "audio_file": os.path.basename(self.audio_file),
                "audio_pos": self.current_pos,
                "cursor_pos": self.editor.textCursor().position(),
                "segments": self.editor.to_segments(),
                "raw_text": self.editor.toPlainText() # <--- ADDED: Save exact raw text
            }
            
            with zipfile.ZipFile(path, 'w', zipfile.ZIP_STORED) as zf:
                zf.writestr("data.json", json.dumps(data, indent=2, ensure_ascii=False))
                zf.write(self.audio_file, os.path.basename(self.audio_file))
                
            self.current_project_path = path
            self.settings.setValue("last_proj_dir", os.path.dirname(path))
            self.editor.document().setModified(False)
            self.update_status_bar()
            return True
        except Exception as e:
            QMessageBox.critical(self, self.tr("Project Save Error"), str(e))
            return False

    def _restore_audio_position(self, target_pos, retries=50):
        if not self.player: return
        
        # When mpv populates the 'duration' property, the media is fully loaded and ready
        if getattr(self.player, 'duration', None) is not None:
            self.seek_to(target_pos)
            self.current_pos = target_pos
            self.update_ui() # Force immediate visual update
        elif retries > 0:
            # Not ready yet, check again in 100ms
            QTimer.singleShot(100, lambda: self._restore_audio_position(target_pos, retries - 1))

    # --- STANDARD I/O LOGIC ---
    def open_file(self):
        last_dir = self.settings.value("last_audio_dir", "")
        path, _ = QFileDialog.getOpenFileName(self, self.tr("Open Audio"), last_dir, self.tr("Audio Files (*.mp3 *.wav *.flac *.ogg *.m4a *.aac)"))
        if not path: return
        self.settings.setValue("last_audio_dir", os.path.dirname(path))
        self.current_project_path = None
        self._open_audio_path(path)
        
    def _open_audio_path(self, path):
        self.audio_file = path
        self.file_label.setText(os.path.basename(path))

        try:
            ffmpeg_path = get_dep_path(self.settings, 'dep_ffmpeg')
            if not ffmpeg_path: ffmpeg_path = "ffmpeg"
            self.duration = self.waveform.load_audio_ffmpeg(path, ffmpeg_path)
            self.waveform.callback_seek = self.seek_to
        except Exception as e:
            QMessageBox.warning(self, self.tr("Audio Load Error"), self.tr(f"Could not load waveform.\n\nError: {e}"))
            self.duration = 0

        if self.player: self.player.terminate()
        
        try: locale.setlocale(locale.LC_NUMERIC, 'C')
        except locale.Error: pass

        self.player = mpv.MPV(input_default_bindings=True, osc=False)
        self.player.pause = True; self.player.volume = self.volume
        self.player.play(path)
        self.play_btn.setText(self.tr("▶ Play"))
        self.update_status_bar()

    def play_pause(self):
        if not self.player: return
        if self.player.pause:
            try: self.player.command("seek", f"{self.current_pos}", "absolute")
            except Exception: pass
            self.player.pause = False; self.play_btn.setText(self.tr("⏸ Pause"))
        else:
            self.player.pause = True; self.play_btn.setText(self.tr("▶ Play"))

    def stop_play(self):
        if not self.player: return
        if not self.player.pause: self.stop()
        else: self.play_pause()

    def stop(self):
        if self.player:
            self.player.pause = True
            try: self.player.command("seek", "0", "absolute")
            except Exception: pass
            self.play_btn.setText(self.tr("▶ Play"))

    def seek_rel(self, seconds):
        if self.player:
            try:
                new_pos = max(0, min(self.duration, self.current_pos + seconds))
                self.player.command("seek", f"{new_pos}", "absolute")
            except Exception: pass

    def seek_to(self, seconds):
        if self.player:
            try: self.player.command("seek", f"{seconds}", "absolute")
            except Exception: pass

    def open_jump_dialog(self):
        if self.audio_file: JumpDialog(self, self.duration, self.current_pos, self.seek_to).show()

    def set_window_size(self, size):
        self.window_size = size
        for btn, val in self.win_btns: btn.setChecked(val == size)
        if getattr(self, "waveform", None) and self.waveform.bars is not None:
            self.update_ui()

    def on_volume_change(self, val):
        self.volume = val
        if self.player: self.player.volume = val

    def increase_volume(self): self.vol_slider.setValue(min(100, self.volume + 10))
    def decrease_volume(self): self.vol_slider.setValue(max(0, self.volume - 10))

    def toggle_always_on_top(self, checked=None):
        if checked is not None: self.on_top_flag = checked
        else: self.on_top_flag = not self.on_top_flag
        flags = self.windowFlags()
        if self.on_top_flag: self.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
        else: self.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
        self.show()
        self.status_bar.show()
        self.update_status_bar()
        if hasattr(self, 'on_top_action'): self.on_top_action.setChecked(self.on_top_flag)

    def set_speed(self, speed):
        self.speed = speed
        if self.player: self.player.speed = speed
        for btn, val in self.speed_btns: btn.setChecked(val == speed)

    def increase_speed(self):
        speeds = [0.25, 0.5, 0.75, 1.0]
        try: idx = speeds.index(self.speed)
        except ValueError: return
        if idx < len(speeds) - 1: self.set_speed(speeds[idx + 1])

    def decrease_speed(self):
        speeds = [0.25, 0.5, 0.75, 1.0]
        try: idx = speeds.index(self.speed)
        except ValueError: return
        if idx > 0: self.set_speed(speeds[idx - 1])

    def insert_timestamp(self):
        if self.audio_file:
            self.editor.insert_timestamp(self.current_pos, self)
            QApplication.clipboard().setText(f"⟦{seconds_to_ts(self.current_pos)}⟧")

    def load_json(self):
        last_dir = self.settings.value("last_json_dir", "")
        path, _ = QFileDialog.getOpenFileName(self, self.tr("Load JSON"), last_dir, self.tr("JSON Files (*.json)"))
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                segments = data.get('segments', data) if isinstance(data, dict) else data
                self.editor.load_segments(segments)
                self.current_json_path = path
                self.current_project_path = None
                self.settings.setValue("last_json_dir", os.path.dirname(path))
                self.editor.document().setModified(False)
                self.update_status_bar()
            except Exception as e:
                QMessageBox.critical(self, self.tr("Load Error"), str(e))

    def save_json(self):
        if self.current_json_path: return self._do_save_json(self.current_json_path)
        else: return self.save_json_as()

    def save_json_as(self):
        last_dir = self.settings.value("last_json_dir", "")
        path, _ = QFileDialog.getSaveFileName(self, self.tr("Save JSON as"), last_dir, self.tr("JSON Files (*.json)"))
        if path:
            if not path.lower().endswith('.json'):
                path += '.json'
            return self._do_save_json(path)
        return False

    def _do_save_json(self, path):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.editor.to_segments(), f, indent=2, ensure_ascii=False)
            self.current_json_path = path
            self.settings.setValue("last_json_dir", os.path.dirname(path))
            self.editor.document().setModified(False)
            self.update_status_bar()
            return True
        except Exception as e:
            QMessageBox.critical(self, self.tr("Save Error"), str(e))
            return False

    def export_file(self, fmt):
        last_dir = self.settings.value("last_export_dir", "")
        path, _ = QFileDialog.getSaveFileName(self, self.tr(f"Export {fmt.upper()}"), last_dir, get_filter(fmt))
        if path:
            try:
                ext = path.split('.')[-1].lower() if '.' in path else ""
                valid_exts = [fmt]
                if fmt == "html": valid_exts.extend(["html", "htm"])
                if fmt == "ass": valid_exts.extend(["ass", "ssa"])
                
                if not ext or ext not in valid_exts:
                    path += f".{fmt}"

                opts = {
                    'md_format_string': self.settings.value("export_md_format", ""),
                    'html_format_string': self.settings.value("export_html_format", "")
                }
                content = export_segments(self.editor.to_segments(), fmt, opts)
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.settings.setValue("last_export_dir", os.path.dirname(path))
            except Exception as e:
                QMessageBox.critical(self, self.tr("Export Error"), str(e))

    def send_to_cloud(self):
        if not self.audio_file:
            QMessageBox.warning(self, self.tr("No audio"), self.tr("Please open an audio file first."))
            return

        profiles_str = self.settings.value("cloud_profiles", "{}")
        try: profiles = json.loads(profiles_str) if isinstance(profiles_str, str) else profiles_str
        except Exception: profiles = {}
            
        current_name = self.settings.value("current_cloud_profile", "")
        config = profiles.get(current_name, {})

        if not config.get("url"):
            QMessageBox.warning(self, self.tr("Configuration Missing"), self.tr("Please configure the Cloud API first."))
            self.open_cloud_config()
            return

        self.progress = QProgressDialog(self.tr("Sending to Cloud API…"), self.tr("Cancel"), 0, 100, self)
        self.progress.setWindowTitle(self.tr(f"Cloud API: {current_name}"))
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.show()

        signals = CloudWorkerSignals()
        signals.progress.connect(self._on_cloud_progress)
        signals.finished.connect(self._on_cloud_finished)
        signals.error.connect(self._on_cloud_error)

        self.cloud_worker = CloudWorker(config, self.audio_file, self.duration, signals)
        self.progress.canceled.connect(self.cloud_worker.cancel)
        self.cloud_worker.start()

    def _on_cloud_progress(self, pct, msg):
        self.progress.setValue(pct)
        self.progress.setLabelText(msg)

    def _on_cloud_finished(self, segments):
        self.progress.close()
        self.editor.load_segments(segments)

    def _on_cloud_error(self, err):
        self.progress.close()
        QMessageBox.critical(self, self.tr("Error"), err)

    def transcribe_with_handy(self):
        if not self.audio_file:
            QMessageBox.warning(self, self.tr("No audio"), self.tr("Please open an audio file first."))
            return
            
        handy_bin = get_dep_path(self.settings, 'handy_bin')
        if not handy_bin or not os.path.exists(handy_bin):
            QMessageBox.warning(
                self, self.tr("Handy Binary Missing"),
                self.tr("Please configure the Handy Tool path in Options > Preferences.")
            )
            return

        self._handy_progress = QProgressDialog(self.tr("Starting Handy Tool..."), self.tr("Cancel"), 0, 100, self)
        self._handy_progress.setWindowTitle(self.tr("Transcribing with Handy"))
        self._handy_progress.setWindowModality(Qt.WindowModal)
        self._handy_progress.show()

        self._handy_signals = CliTranscribeSignals()
        self._handy_signals.progress.connect(self._on_handy_progress)
        self._handy_signals.finished.connect(self._on_handy_finished)
        self._handy_signals.error.connect(self._on_handy_error)

        handy_model = self.settings.value("handy_model", "base")
        handy_device = self.settings.value("handy_device", "cpu")

        self._handy_worker = CliTranscribeWorker(
            handy_bin, self.audio_file, self.duration, 
            handy_model, handy_device, self._handy_signals
        )
        
        self._handy_progress.canceled.connect(self._handy_worker.cancel)
        self._handy_worker.start()

    def _on_handy_progress(self, pct, msg):
        if hasattr(self, '_handy_progress') and self._handy_progress:
            if self._handy_progress.wasCanceled(): return
            self._handy_progress.setValue(pct)
            self._handy_progress.setLabelText(msg)

    def _on_handy_finished(self, segments):
        if hasattr(self, '_handy_progress') and self._handy_progress:
            self._handy_progress.close()
        if not segments:
            QMessageBox.information(self, self.tr("No result"), self.tr("Handy returned no segments."))
            return
        self.editor.load_segments(segments)
        self.editor.document().setModified(True)
        self.update_status_bar()

    def _on_handy_error(self, msg):
        if hasattr(self, '_handy_progress') and self._handy_progress:
            self._handy_progress.close()
        QMessageBox.critical(self, self.tr("Handy Tool Error"), msg)

    def update_ui(self):
        if not self.player: return
        try: pos = float(self.player.time_pos or 0)
        except Exception: return
        
        self.current_pos = max(0, min(self.duration, pos))
        self.time_label.setText(f"{seconds_to_ts(self.current_pos)} / {seconds_to_ts(self.duration)}")
        
        if getattr(self, "waveform", None) and self.waveform.bars is not None:
            tb = len(self.waveform.bars)
            wb = max(1, int(self.window_size * 200)) 
            cb = int(self.current_pos * 200)         
            
            sb = max(0, cb - wb // 2)
            sb = min(sb, max(0, tb - wb))
            
            self.waveform.set_window(sb, wb)
            self.waveform.set_position(cb)

    def closeEvent(self, e):
        if self.editor.document().isModified():
            ans = QMessageBox.warning(
                self, self.tr("Unsaved Changes"),
                self.tr("You have unsaved changes. Do you want to save them before exiting?"),
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            if ans == QMessageBox.Save:
                # If a project is loaded, save project instead of raw json
                if self.current_project_path:
                    if not self.save_project():
                        e.ignore()
                        return
                else:
                    if not self.save_json():
                        e.ignore()
                        return
            elif ans == QMessageBox.Cancel:
                e.ignore()
                return

        if self.player: self.player.terminate()
        e.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setApplicationName("TranscribeEdit")
    app.setWindowIcon(get_app_icon())

    try: locale.setlocale(locale.LC_NUMERIC, 'C')
    except locale.Error: pass

    locale_name = QLocale.system().name()
    base_lang = locale_name.split('_')[0]

    qt_translator = QTranslator()
    qt_path = QLibraryInfo.location(QLibraryInfo.TranslationsPath)
    if qt_translator.load(f"qt_{locale_name}", qt_path) or qt_translator.load(f"qt_{base_lang}", qt_path):
        app.installTranslator(qt_translator)

    app_translator = QTranslator()
    if app_translator.load(f"transcribeedit_{locale_name}", "translations") or app_translator.load(f"transcribeedit_{base_lang}", "translations"):
        app.installTranslator(app_translator)

    try: qdarktheme.setup_theme("auto")
    except AttributeError: app.setStyleSheet(qdarktheme.load_stylesheet("dark"))

    win = AudioPlayer()
    win.show()
    sys.exit(app.exec_())
