import sys
import os
import json
import signal
import platform
import qdarktheme

# Fix: Only force numeric locale to 'C' (for safe float/mpv/ffmpeg math).
# Do NOT override LANG/LC_ALL, otherwise PyQt5 translations will fail!
import locale
try:
    locale.setlocale(locale.LC_NUMERIC, 'C')
except locale.Error:
    pass

import mpv
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QGridLayout, QPushButton, QLabel, QSlider,
    QFileDialog, QSplitter, QMessageBox, QProgressDialog,
    QShortcut, QStatusBar, QFrame, QDialog, QAction, QMenuBar, QFontDialog)
from PyQt5.QtCore import Qt, QTimer, QSettings, QTranslator, QLibraryInfo, QLocale
from PyQt5.QtGui import QKeySequence, QFont, QIcon

from utils import seconds_to_ts
from widgets import WaveformWidget, ColorLabel, JumpDialog, FindDialog
from editor import TranscriptEditor
from cloud_client import CloudWorker, CloudWorkerSignals
from shortcuts import DEFAULT_SHORTCUTS
from cli_connector import CliTranscribeWorker, CliTranscribeSignals

if platform.system() == 'Linux' and 'QT_QPA_PLATFORMTHEME' not in os.environ:
    os.environ['QT_QPA_PLATFORMTHEME'] = 'qt5ct'
os.environ["QT_LOGGING_RULES"] = "qt.qpa.fonts=false"

def sigint_handler(*args): QApplication.quit()
signal.signal(signal.SIGINT, sigint_handler)

def get_app_icon():
    """Dynamically loads the correct icon format based on the OS."""
    sys_name = platform.system()
    if sys_name == 'Windows':
        ext = 'ico'
    elif sys_name == 'Darwin':
        ext = 'icns'
    else:
        ext = 'png'
    return QIcon(os.path.join("icons", f"transcribeedit.{ext}"))

class AudioPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        # 1. New App Name and Dynamic Icon
        self.setWindowTitle(self.tr("TranscribeEdit"))
        self.setWindowIcon(get_app_icon())
        self.setMinimumSize(900, 850)

        # 2. Update QSettings to use the new app name
        self.settings = QSettings("TranscribeEdit", "TranscribeEdit")
        
        self.handy_bin = self.settings.value("handy_bin", "")
        self.handy_model = self.settings.value("handy_model", "base")
        self.handy_device = self.settings.value("handy_device", "cpu")

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
        self.active_qshortcuts = []
        self.menu_actions = {}

        self._build_ui()
        self._build_menu()
        self._connect_signals()
        self._setup_shortcuts()

        self.apply_editor_config()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(50)

        self.update_status_bar()

    def _build_menu(self):
        menubar = self.menuBar()
        menubar.setNativeMenuBar(True)

        file_menu = menubar.addMenu(self.tr("File"))

        self.open_action = QAction(self.tr("Open Audio..."), self)
        self.open_action.triggered.connect(self.open_file)
        file_menu.addAction(self.open_action)

        self.load_json_action = QAction(self.tr("Load JSON..."), self)
        self.load_json_action.triggered.connect(self.load_json)
        file_menu.addAction(self.load_json_action)

        self.save_json_action = QAction(self.tr("Save JSON"), self)
        self.save_json_action.triggered.connect(self.save_json)
        file_menu.addAction(self.save_json_action)

        self.save_json_as_action = QAction(self.tr("Save JSON As..."), self)
        self.save_json_as_action.triggered.connect(self.save_json_as)
        file_menu.addAction(self.save_json_as_action)

        self.export_srt_action = QAction(self.tr("Export SRT..."), self)
        self.export_srt_action.triggered.connect(self.export_srt)
        file_menu.addAction(self.export_srt_action)

        file_menu.addSeparator()

        get_transcription_action = QAction(self.tr("Transcribe (Cloud API)"), self)
        get_transcription_action.triggered.connect(self.send_to_cloud)
        file_menu.addAction(get_transcription_action)
        
        self.handy_transcribe_action = QAction(self.tr("Transcribe with Handy Text to Speech Tool"), self)
        self.handy_transcribe_action.triggered.connect(self.transcribe_with_handy)
        file_menu.addAction(self.handy_transcribe_action)

        self.menu_actions = {
            "Open Audio": self.open_action,
            "Load JSON": self.load_json_action,
            "Save JSON": self.save_json_action,
            "Export SRT": self.export_srt_action
        }

        view_menu = menubar.addMenu(self.tr("View"))
        self.on_top_action = QAction(self.tr("Always on Top"), self, checkable=True)
        self.on_top_action.triggered.connect(self.toggle_always_on_top)
        view_menu.addAction(self.on_top_action)

        options_menu = menubar.addMenu(self.tr("Options"))
        
        self.cloud_config_action = QAction(self.tr("Cloud API Configuration..."), self)
        self.cloud_config_action.triggered.connect(self.open_cloud_config)
        options_menu.addAction(self.cloud_config_action)
        
        self.preferences_action = QAction(self.tr("Preferences..."), self)
        self.preferences_action.setMenuRole(QAction.PreferencesRole)
        self.preferences_action.triggered.connect(self.open_preferences_dialog)
        options_menu.addAction(self.preferences_action)

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
        for sp in [0.25, 0.5, 0.7, 1.0]:
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
        audio_name = os.path.basename(self.audio_file) if self.audio_file else self.tr("No Audio")
        json_name = os.path.basename(self.current_json_path) if self.current_json_path else self.tr("Unsaved JSON")

        if getattr(self, 'editor', None) and self.editor.document().isModified():
            json_name += " *"

        self.status_label.setText(self.tr("Audio: {0} | JSON: {1}").format(audio_name, json_name))

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
        if checked:
            self.editor.highlight_closest_timestamp(self.current_pos)
        else:
            self.editor.clear_highlight()

    def open_find_dialog(self):
        if getattr(self, 'find_dialog', None) is None:
            self.find_dialog = FindDialog(self, self.editor)
        self.find_dialog.show()
        self.find_dialog.activateWindow()
        self.find_dialog.search_input.setFocus()
        self.find_dialog.search_input.selectAll()

    def _setup_shortcuts(self):
        self.shortcut_handlers = {
            "Quit": self.close,
            "Play/Pause": self.play_pause,
            "Play/Pause (Alt)": self.play_pause,
            "Stop/Play": self.stop_play,
            "Stop": self.stop,
            "Jump Dialog": self.open_jump_dialog,
            "Insert Timestamp": self.insert_timestamp,
            "Insert Speaker Tag": lambda: self.editor.insert_or_cycle_speaker(self.speakers),
            "Toggle Highlight": self.highlight_ts_btn.toggle, 
            "Find": self.open_find_dialog,
            "Jump to Cursor": self.editor.jump_to_timestamp_at_cursor,
            "Increase Speed": self.increase_speed,
            "Decrease Speed": self.decrease_speed,
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

    def open_cloud_config(self):
        from config_dialogs import CloudConfigDialog
        dlg = CloudConfigDialog(self)
        dlg.exec_()

    def open_preferences_dialog(self):
        from preferences_dialog import PreferencesDialog
        
        settings_data = {
            'shortcuts': self.current_shortcuts,
            'editor': {
                "text_fg": self.settings.value("editor_text_fg", ""),
                "text_bg": self.settings.value("editor_text_bg", ""),
                "ts_fg": self.settings.value("editor_ts_fg", ""),
                "ts_bg": self.settings.value("editor_ts_bg", ""),
                "spk_fg": self.settings.value("editor_spk_fg", ""),
                "spk_bg": self.settings.value("editor_spk_bg", ""),
                "font": self.settings.value("editor_font", "")
            },
            'speakers': self.speakers,
            'handy_bin': self.handy_bin,
            'handy_model': self.handy_model,
            'handy_device': self.handy_device
        }
        
        dlg = PreferencesDialog(self, settings_data)
        if dlg.exec_() == QDialog.Accepted:
            self.current_shortcuts = dlg.shortcut_tab.result_shortcuts
            for name, seq_str in self.current_shortcuts.items():
                self.settings.setValue(f"shortcut_{name}", seq_str)
            self.apply_shortcuts()
            
            for k, v in dlg.editor_tab.config.items():
                self.settings.setValue(f"editor_{k}", v)
            self.apply_editor_config()
            
            self.speakers = dlg.speaker_tab.result_speakers
            for i, s in enumerate(self.speakers):
                self.settings.setValue(f"speaker_{i}", s)
                
            self.handy_bin = dlg.handy_tab.bin_path
            self.handy_model = dlg.handy_tab.model
            self.handy_device = dlg.handy_tab.device
            self.settings.setValue("handy_bin", self.handy_bin)
            self.settings.setValue("handy_model", self.handy_model)
            self.settings.setValue("handy_device", self.handy_device)

    def apply_editor_config(self):
        txt_fg = self.settings.value("editor_text_fg", "")
        txt_bg = self.settings.value("editor_text_bg", "")

        sheet = "QTextEdit { "
        if txt_fg: sheet += f"color: {txt_fg}; "
        if txt_bg: sheet += f"background-color: {txt_bg}; "
        sheet += "}"
        self.editor.setStyleSheet(sheet)

        font_str = self.settings.value("editor_font", "")
        if font_str:
            font = QFont()
            font.fromString(font_str)
            self.editor.setFont(font)

        ts_fg = self.settings.value("editor_ts_fg", "")
        ts_bg = self.settings.value("editor_ts_bg", "")
        spk_fg = self.settings.value("editor_spk_fg", "")
        spk_bg = self.settings.value("editor_spk_bg", "")

        self.editor.highlighter.update_formats(ts_fg, ts_bg, spk_fg, spk_bg)

    def open_file(self):
        last_dir = self.settings.value("last_dir", "")
        path, _ = QFileDialog.getOpenFileName(self, self.tr("Open Audio"), last_dir, self.tr("Audio Files (*.mp3 *.wav *.flac *.ogg *.m4a *.aac)"))
        if not path: return
        self.audio_file = path
        self.file_label.setText(os.path.basename(path))
        self.settings.setValue("last_dir", os.path.dirname(path))

        try:
            self.duration = self.waveform.load_audio_ffmpeg(path)
            self.waveform.callback_seek = self.seek_to
        except Exception as e:
            QMessageBox.warning(self, self.tr("Audio Load Error"), self.tr(f"Could not load waveform for {os.path.basename(path)}.\n\nError: {e}"))
            self.duration = 0

        if self.player: self.player.terminate()
        self.player = mpv.MPV(input_default_bindings=True, osc=False)
        self.player.pause = True; self.player.volume = self.volume
        self.player.play(path)
        self.play_btn.setText(self.tr("▶ Play"))
        self.update_status_bar()

    def play_pause(self):
        if not self.player: return
        if self.player.pause:
            try:
                self.player.command("seek", f"{self.current_pos}", "absolute")
            except Exception as e:
                pass
            self.player.pause = False; self.play_btn.setText(self.tr("⏸ Pause"))
        else:
            self.player.pause = True; self.play_btn.setText(self.tr("▶ Play"))

    def stop_play(self):
        if not self.player: return
        if not self.player.pause:
            self.stop()
        else:
            self.play_pause()

    def stop(self):
        if self.player:
            self.player.pause = True
            try:
                self.player.command("seek", "0", "absolute")
            except Exception as e:
                pass
            self.play_btn.setText(self.tr("▶ Play"))

    def seek_rel(self, seconds):
        if self.player:
            try:
                new_pos = max(0, min(self.duration, self.current_pos + seconds))
                self.player.command("seek", f"{new_pos}", "absolute")
            except Exception as e:
                pass

    def seek_to(self, seconds):
        if self.player:
            try:
                self.player.command("seek", f"{seconds}", "absolute")
            except Exception as e:
                pass

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

    def increase_volume(self):
        self.vol_slider.setValue(min(100, self.volume + 10))

    def decrease_volume(self):
        self.vol_slider.setValue(max(0, self.volume - 10))

    def toggle_always_on_top(self, checked=None):
        if checked is not None:
            self.on_top_flag = checked
        else:
            self.on_top_flag = not self.on_top_flag

        flags = self.windowFlags()
        if self.on_top_flag:
            self.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)

        self.show()
        self.status_bar.show()
        self.update_status_bar()
        if hasattr(self, 'on_top_action'):
            self.on_top_action.setChecked(self.on_top_flag)

    def set_speed(self, speed):
        self.speed = speed
        if self.player: self.player.speed = speed
        for btn, val in self.speed_btns: btn.setChecked(val == speed)

    def increase_speed(self):
        speeds = [0.25, 0.5, 0.7, 1.0]
        try:
            idx = speeds.index(self.speed)
        except ValueError:
            return
        if idx < len(speeds) - 1:
            self.set_speed(speeds[idx + 1])

    def decrease_speed(self):
        speeds = [0.25, 0.5, 0.7, 1.0]
        try:
            idx = speeds.index(self.speed)
        except ValueError:
            return
        if idx > 0:
            self.set_speed(speeds[idx - 1])

    def insert_timestamp(self):
        if self.audio_file:
            self.editor.insert_timestamp(self.current_pos, self)
            QApplication.clipboard().setText(f"[{seconds_to_ts(self.current_pos)}]")

    def load_json(self):
        last_dir = self.settings.value("last_dir", "")
        path, _ = QFileDialog.getOpenFileName(self, self.tr("Load JSON"), last_dir, self.tr("JSON Files (*.json)"))
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if isinstance(data, dict):
                    segments = data.get('segments', data)
                else:
                    segments = data
                
                self.editor.load_segments(segments)
                self.current_json_path = path
                self.settings.setValue("last_dir", os.path.dirname(path))
                self.editor.document().setModified(False)
                self.update_status_bar()
            except Exception as e:
                QMessageBox.critical(self, self.tr("Load Error"), str(e))

    def save_json(self):
        if self.current_json_path:
            return self._do_save_json(self.current_json_path)
        else:
            return self.save_json_as()

    def save_json_as(self):
        last_dir = self.settings.value("last_dir", "")
        path, _ = QFileDialog.getSaveFileName(self, self.tr("Save JSON as"), last_dir, self.tr("JSON Files (*.json)"))
        if path:
            return self._do_save_json(path)
        return False

    def _do_save_json(self, path):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.editor.to_segments(), f, indent=2, ensure_ascii=False)
            self.current_json_path = path
            self.settings.setValue("last_dir", os.path.dirname(path))
            self.editor.document().setModified(False)
            self.update_status_bar()
            return True
        except Exception as e:
            QMessageBox.critical(self, self.tr("Save Error"), str(e))
            return False

    def export_srt(self):
        last_dir = self.settings.value("last_dir", "")
        path, _ = QFileDialog.getSaveFileName(self, self.tr("Export SRT"), last_dir, self.tr("SRT Files (*.srt)"))
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(self.editor.to_srt())
                self.settings.setValue("last_dir", os.path.dirname(path))
            except Exception as e:
                QMessageBox.critical(self, self.tr("Export Error"), str(e))

    def send_to_cloud(self):
        if not self.audio_file:
            QMessageBox.warning(self, self.tr("No audio"), self.tr("Please open an audio file first."))
            return

        profiles_str = self.settings.value("cloud_profiles", "{}")
        try:
            profiles = json.loads(profiles_str) if isinstance(profiles_str, str) else profiles_str
        except Exception:
            profiles = {}
            
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
            
        if not self.handy_bin or not os.path.exists(self.handy_bin):
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

        self._handy_worker = CliTranscribeWorker(
            self.handy_bin, self.audio_file, self.duration, 
            self.handy_model, self.handy_device, self._handy_signals
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
                if not self.save_json():
                    e.ignore()
                    return
            elif ans == QMessageBox.Cancel:
                e.ignore()
                return

        if self.player: self.player.terminate()
        e.accept()

if __name__ == '__main__':
    # Initialize the app with the new name
    app = QApplication(sys.argv)
    app.setApplicationName("TranscribeEdit")
    
    # 3. Apply the dynamic icon to the application process
    app.setWindowIcon(get_app_icon())

    locale_name = QLocale.system().name()
    base_lang = locale_name.split('_')[0]

    qt_translator = QTranslator()
    qt_path = QLibraryInfo.location(QLibraryInfo.TranslationsPath)
    if qt_translator.load(f"qt_{locale_name}", qt_path) or qt_translator.load(f"qt_{base_lang}", qt_path):
        app.installTranslator(qt_translator)

    app_translator = QTranslator()
    # 4. Use the new application name for translation files as well
    if app_translator.load(f"transcribeedit_{locale_name}", "translations") or app_translator.load(f"transcribeedit_{base_lang}", "translations"):
        app.installTranslator(app_translator)

    try:
        qdarktheme.setup_theme("auto")
    except AttributeError:
        app.setStyleSheet(qdarktheme.load_stylesheet("dark"))

    win = AudioPlayer()
    win.show()
    sys.exit(app.exec_())
