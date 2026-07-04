# main.py
import sys
import os
import signal
import platform
import locale

import qdarktheme
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QGridLayout, QPushButton, QLabel, QSlider,
    QSplitter, QMessageBox, QShortcut, QStatusBar, QFrame, QDialog,
)
from PyQt5.QtCore import Qt, QTimer, QSettings, QTranslator, QLibraryInfo, QLocale
from PyQt5.QtGui import QKeySequence, QIcon

from utils import seconds_to_ts
from widgets import WaveformWidget, ColorLabel, FindDialog
from editor import TranscriptEditor
from shortcuts import DEFAULT_SHORTCUTS
from menu_builder import build_main_menu
from prefs_tab_deps import check_and_store_deps, DepsDialog

from playback_mixin import PlaybackMixin
from io_mixin import IOMixin
from dialogs_mixin import DialogsMixin

from theme_manager import ThemeManager

if platform.system() == "Linux" and "QT_QPA_PLATFORMTHEME" not in os.environ:
    os.environ["QT_QPA_PLATFORMTHEME"] = "qt5ct"
os.environ["QT_LOGGING_RULES"] = "qt.qpa.fonts=false"


def sigint_handler(*args):
    QApplication.quit()


signal.signal(signal.SIGINT, sigint_handler)


def get_app_icon():
    sys_name = platform.system()
    if sys_name == "Windows":
        ext = "ico"
    elif sys_name == "Darwin":
        ext = "icns"
    else:
        ext = "png"
    return QIcon(os.path.join("icons", f"transcribeedit.{ext}"))


class AudioPlayer(PlaybackMixin, IOMixin, DialogsMixin, QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.tr("TranscribeEdit"))
        self.setWindowIcon(get_app_icon())
        self.setMinimumSize(900, 850)

        self.settings = QSettings("TranscribeEdit", "TranscribeEdit")

        self.theme_mgr = ThemeManager(self.settings)

        missing_deps = check_and_store_deps(self.settings)
        if missing_deps:
            QTimer.singleShot(0, self.show_deps_dialog)

        self.speakers = []
        for i in range(6):
            self.speakers.append(self.settings.value(f"speaker_{i}", f"SPEAKER_0{i}"))

        # Initialise playback state (defined in PlaybackMixin)
        self._init_playback_state()

        self.current_json_path = None
        self.current_project_path = None
        self.active_qshortcuts = []

        self._build_ui()
        self.menu_actions = build_main_menu(self)

        # Wire up the UI widgets to the theme manager now that they exist
        self.theme_mgr.register_targets(
            editor=self.editor,
            waveform=self.waveform,
            timetable=self.time_label,
        )

        self._connect_signals()
        self._setup_shortcuts()
        
        # This function (from DialogsMixin) will now successfully apply the theme
        self.apply_editor_config()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(50)

        self.update_status_bar()

    # ------------------------------------------------------------------ deps
    def show_deps_dialog(self):
        dlg = DepsDialog(self, self.settings, missing_only=True)
        dlg.exec_()

    # ------------------------------------------------------------------ UI construction
    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        splitter = QSplitter(Qt.Vertical)
        root_layout.addWidget(splitter, stretch=1)

        top = QWidget()
        tv = QVBoxLayout(top)
        self.file_label = QLabel(self.tr("No file loaded"))
        self.file_label.setAlignment(Qt.AlignCenter)
        self.file_label.setStyleSheet("font: 11pt; color: gray;")
        tv.addWidget(self.file_label)

        self.time_label = ColorLabel("00:00:00.00 / 00:00:00.00")
        tv.addWidget(self.time_label)

        win_frame = QFrame()
        win_vbox = QVBoxLayout(win_frame)
        win_vbox.setContentsMargins(0, 0, 0, 0)
        win_vbox.setSpacing(6)
        lbl = QLabel(self.tr("Waveform Window"))
        lbl.setAlignment(Qt.AlignCenter)
        win_vbox.addWidget(lbl)

        win_hbox = QHBoxLayout()
        win_hbox.setContentsMargins(0, 0, 0, 0)
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
        controls_layout.setSpacing(14)
        BTN_H = 32
        LBL_H = 20

        # Seek
        seek_frame = QFrame()
        seek_layout = QVBoxLayout(seek_frame)
        seek_layout.setContentsMargins(0, 0, 0, 0)
        seek_layout.setSpacing(6)
        lbl_seek = QLabel(self.tr("Seek"))
        lbl_seek.setAlignment(Qt.AlignCenter)
        lbl_seek.setFixedHeight(LBL_H)
        seek_layout.addWidget(lbl_seek)
        seek_grid = QGridLayout()
        seek_grid.setContentsMargins(0, 0, 0, 0)
        seek_grid.setSpacing(4)
        seek_data = [
            ("-0.1s", -0.1), ("-0.5s", -0.5), ("+0.5s", +0.5), ("+0.1s", +0.1),
            ("-1s", -1.0), ("-5s", -5.0), ("+5s", +5.0), ("+1s", +1.0),
        ]
        self.seek_btns = []
        for i, (lbl_txt, val) in enumerate(seek_data):
            btn = QPushButton(lbl_txt)
            btn.setFixedHeight(BTN_H)
            seek_grid.addWidget(btn, i // 4, i % 4)
            self.seek_btns.append((btn, val))
        seek_layout.addLayout(seek_grid)
        seek_layout.addStretch()
        controls_layout.addWidget(seek_frame, 35)

        # Playback / Speed
        pb_frame = QFrame()
        pb_layout = QVBoxLayout(pb_frame)
        pb_layout.setContentsMargins(0, 0, 0, 0)
        pb_layout.setSpacing(6)
        lbl_pb = QLabel(self.tr("Playback/Speed"))
        lbl_pb.setAlignment(Qt.AlignCenter)
        lbl_pb.setFixedHeight(LBL_H)
        pb_layout.addWidget(lbl_pb)
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(4)
        self.stop_btn = QPushButton(self.tr("■ Stop"))
        self.play_btn = QPushButton(self.tr("▶ Play"))
        self.jump_btn = QPushButton(self.tr("Jump…"))
        for b in (self.stop_btn, self.play_btn, self.jump_btn):
            b.setFixedHeight(BTN_H)
        btn_row.addWidget(self.stop_btn)
        btn_row.addWidget(self.play_btn)
        btn_row.addWidget(self.jump_btn)
        pb_layout.addLayout(btn_row)
        spd_row = QHBoxLayout()
        spd_row.setContentsMargins(0, 0, 0, 0)
        spd_row.setSpacing(4)
        self.speed_btns = []
        for sp in [0.25, 0.5, 0.75, 1.0]:
            btn = QPushButton(f"{int(sp * 100)}%")
            btn.setCheckable(True)
            btn.setFixedHeight(BTN_H)
            self.speed_btns.append((btn, sp))
            spd_row.addWidget(btn)
        self.speed_btns[-1][0].setChecked(True)
        self.speed_minus = QPushButton("-")
        self.speed_plus = QPushButton("+")
        self.speed_minus.setFixedHeight(BTN_H)
        self.speed_plus.setFixedHeight(BTN_H)
        spd_row.addWidget(self.speed_minus)
        spd_row.addWidget(self.speed_plus)
        pb_layout.addLayout(spd_row)
        pb_layout.addStretch()
        controls_layout.addWidget(pb_frame, 40)

        # Loop
        loop_frame = QFrame()
        loop_layout = QVBoxLayout(loop_frame)
        loop_layout.setContentsMargins(0, 0, 0, 0)
        loop_layout.setSpacing(6)
        lbl_loop = QLabel(self.tr("Loop"))
        lbl_loop.setAlignment(Qt.AlignCenter)
        lbl_loop.setFixedHeight(LBL_H)
        loop_layout.addWidget(lbl_loop)
        loop_row = QHBoxLayout()
        loop_row.setContentsMargins(0, 0, 0, 0)
        loop_row.setSpacing(4)
        self.mark_a_btn = QPushButton(self.tr("A"))
        self.mark_b_btn = QPushButton(self.tr("B"))
        self.loop_btn = QPushButton(self.tr("Loop"))
        self.loop_btn.setCheckable(True)
        for b in (self.mark_a_btn, self.mark_b_btn, self.loop_btn):
            b.setFixedHeight(BTN_H)
        loop_row.addWidget(self.mark_a_btn)
        loop_row.addWidget(self.mark_b_btn)
        loop_row.addWidget(self.loop_btn)
        loop_layout.addLayout(loop_row)
        loop_layout.addStretch()
        controls_layout.addWidget(loop_frame, 25)

        tv.addLayout(controls_layout)

        vol_row = QHBoxLayout()
        vol_row.addWidget(QLabel(self.tr("Volume:")))
        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(self.volume)
        vol_row.addWidget(self.vol_slider)
        tv.addLayout(vol_row)

        splitter.addWidget(top)

        # Editor pane
        bottom = QWidget()
        bv = QVBoxLayout(bottom)
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

    # ------------------------------------------------------------------ status bar
    def update_status_bar(self):
        is_modified = getattr(self, "editor", None) and self.editor.document().isModified()

        if self.current_project_path:
            proj_name = os.path.basename(self.current_project_path)
            editor_status = self.tr("UNSAVED") if is_modified else self.tr("SAVED")
            self.status_label.setText(
                self.tr("Project: {0} | Editor: {1}").format(proj_name, editor_status)
            )
        else:
            audio_name = (
                os.path.basename(self.audio_file) if self.audio_file else self.tr("No Audio")
            )
            if self.current_json_path:
                json_name = os.path.basename(self.current_json_path)
            else:
                json_name = self.tr("Unsaved data")
            if is_modified:
                json_name += " *"
            self.status_label.setText(
                self.tr("Audio: {0} | Editor: {1}").format(audio_name, json_name)
            )

    # ------------------------------------------------------------------ signal wiring
    def _connect_signals(self):
        self.play_btn.clicked.connect(self.play_pause)
        self.stop_btn.clicked.connect(self.stop)
        self.jump_btn.clicked.connect(self.open_jump_dialog)
        self.copy_ts_btn.clicked.connect(self.insert_timestamp)
        self.jump_from_ed_btn.clicked.connect(self.editor.jump_to_timestamp_at_cursor)
        self.insert_speaker_btn.clicked.connect(
            lambda: self.editor.insert_or_cycle_speaker(self.speakers)
        )
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

        self.mark_a_btn.clicked.connect(self.toggle_mark_a)
        self.mark_b_btn.clicked.connect(self.toggle_mark_b)
        self.loop_btn.toggled.connect(self.set_loop_on)

        self.editor.jump_requested.connect(self.seek_to)
        self.editor.document().modificationChanged.connect(self.update_status_bar)

    def on_highlight_toggled(self, checked):
        if checked:
            self.editor.highlight_closest_timestamp(self.current_pos)
        else:
            self.editor.clear_highlight()

    # ------------------------------------------------------------------ find dialog
    def open_find_dialog(self):
        if getattr(self, "find_dialog", None) is None:
            self.find_dialog = FindDialog(self, self.editor)
        self.find_dialog.show()
        self.find_dialog.activateWindow()
        self.find_dialog.search_input.setFocus()
        self.find_dialog.search_input.selectAll()

    def find_next_silent(self):
        if getattr(self, "find_dialog", None) and self.find_dialog.search_input.text():
            self.find_dialog._do_find(False)
        else:
            self.open_find_dialog()

    def find_prev_silent(self):
        if getattr(self, "find_dialog", None) and self.find_dialog.search_input.text():
            self.find_dialog._do_find(True)
        else:
            self.open_find_dialog()

    # ------------------------------------------------------------------ shortcuts
    def _setup_shortcuts(self):
        self.shortcut_handlers = {
            "Quit":                self.quit_app,
            "Open Project":        self.load_project,
            "Save Project":        self.save_project,
            "Save Project As":     self.save_project_as,
            "Play/Pause":          self.play_pause,
            "Play/Pause (Alt)":    self.play_pause,
            "Stop/Play":           self.stop_play,
            "Stop":                self.stop,
            "Jump Dialog":         self.open_jump_dialog,
            "Insert Timestamp":    self.insert_timestamp,
            "Insert Speaker Tag":  lambda: self.editor.insert_or_cycle_speaker(self.speakers),
            "Toggle Highlight":    self.highlight_ts_btn.toggle,
            "Find":                self.open_find_dialog,
            "Find Next":           self.find_next_silent,
            "Find Prev":           self.find_prev_silent,
            "Fold/Unfold":         self.editor.toggle_fold_current,
            "Format Bold":         self.editor.format_bold,
            "Format Italic":       self.editor.format_italic,
            "Format Underline":    lambda: self.editor.toggle_format("<u>", "</u>"),
            "Add Comment":         self.editor.add_comment,
            "Jump to Cursor":      self.editor.jump_to_timestamp_at_cursor,
            "Increase Speed":      self.increase_speed,
            "Decrease Speed":      self.decrease_speed,
            "Speed 25%":           lambda: self.set_speed(0.25),
            "Speed 50%":           lambda: self.set_speed(0.50),
            "Speed 75%":           lambda: self.set_speed(0.75),
            "Speed 100%":          lambda: self.set_speed(1.0),
            "Volume Up":           self.increase_volume,
            "Volume Down":         self.decrease_volume,
            "Seek -0.1s":          lambda: self.seek_rel(-0.1),
            "Seek +0.1s":          lambda: self.seek_rel(0.1),
            "Seek -0.5s":          lambda: self.seek_rel(-0.5),
            "Seek +0.5s":          lambda: self.seek_rel(0.5),
            "Seek -1.0s":          lambda: self.seek_rel(-1.0),
            "Seek +1.0s":          lambda: self.seek_rel(1.0),
            "Seek -5.0s":          lambda: self.seek_rel(-5.0),
            "Seek +5.0s":          lambda: self.seek_rel(5.0),
            "Waveform 0.1s":       lambda: self.set_window_size(0.1),
            "Waveform 0.5s":       lambda: self.set_window_size(0.5),
            "Waveform 1.0s":       lambda: self.set_window_size(1.0),
            "Waveform 2.0s":       lambda: self.set_window_size(2.0),
            "Waveform 5.0s":       lambda: self.set_window_size(5.0),
            "Set/Jump/Unset A":    self.toggle_mark_a,
            "Set/Jump/Unset B":    self.toggle_mark_b,
            "Toggle Loop":         self.loop_btn.toggle,
            # Preferences shortcut handled via menu action on Win/Linux only
        }
        self.current_shortcuts = {}
        for name, default_seq in DEFAULT_SHORTCUTS.items():
            self.current_shortcuts[name] = self.settings.value(
                f"shortcut_{name}", default_seq
            )
        self.apply_shortcuts()

    def apply_shortcuts(self):
        for sc in self.active_qshortcuts:
            sc.deleteLater()
        self.active_qshortcuts.clear()

        for name, seq_str in self.current_shortcuts.items():
            if not seq_str:
                continue
            if name in self.menu_actions:
                self.menu_actions[name].setShortcut(QKeySequence(seq_str))
            elif name in self.shortcut_handlers:
                sc = QShortcut(QKeySequence(seq_str), self)
                sc.activated.connect(self.shortcut_handlers[name])
                self.active_qshortcuts.append(sc)

    def quit_app(self):
        self.close()

    # ------------------------------------------------------------------ close
    def closeEvent(self, e):
        if self.editor.document().isModified():
            ans = QMessageBox.warning(
                self,
                self.tr("Unsaved Changes"),
                self.tr("You have unsaved changes. Do you want to save them before exiting?"),
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            )
            if ans == QMessageBox.Save:
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

        if self.player:
            self.player.terminate()
        e.accept()


# ------------------------------------------------------------------ entry point
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("TranscribeEdit")
    app.setWindowIcon(get_app_icon())

    try:
        locale.setlocale(locale.LC_NUMERIC, "C")
    except locale.Error:
        pass

    locale_name = QLocale.system().name()
    base_lang = locale_name.split("_")[0]

    qt_translator = QTranslator()
    qt_path = QLibraryInfo.location(QLibraryInfo.TranslationsPath)
    if qt_translator.load(f"qt_{locale_name}", qt_path) or qt_translator.load(
        f"qt_{base_lang}", qt_path
    ):
        app.installTranslator(qt_translator)

    app_translator = QTranslator()
    if app_translator.load(
        f"transcribeedit_{locale_name}", "translations"
    ) or app_translator.load(f"transcribeedit_{base_lang}", "translations"):
        app.installTranslator(app_translator)

    try:
        qdarktheme.setup_theme("auto")
    except AttributeError:
        app.setStyleSheet(qdarktheme.load_stylesheet("dark"))

    win = AudioPlayer()
    win.show()
    sys.exit(app.exec_())
