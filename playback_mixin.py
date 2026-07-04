# playback_mixin.py
"""PlaybackMixin — extracted from main.py.

Contains all audio playback state and methods:
  play/pause/stop, seeking, speed, volume, A/B loop markers,
  waveform position sync, jump dialog, timestamp insertion,
  always-on-top toggle.
"""
import locale
import os

import mpv
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt, QTimer

from utils import seconds_to_ts
from widgets import JumpDialog
from prefs_tab_deps import get_dep_path


class PlaybackMixin:
    """Mixin providing all audio playback behaviour for AudioPlayer."""

    # ------------------------------------------------------------------ setup
    def _init_playback_state(self):
        self.audio_file = None
        self.player = None
        self.current_pos = 0
        self.duration = 0
        self.volume = 80
        self.speed = 1.0
        self.window_size = 1.0
        self.is_playing = False
        self.on_top_flag = False

        self.loop_a = None
        self.loop_b = None
        self.loop_on = False
        self.was_paused_before_loop_seek = False
        self._loop_seek_pending = False
        self._loop_seek_target = None

    # ------------------------------------------------------------------ audio loading
    def _open_audio_path(self, path):
        self.audio_file = path
        self.file_label.setText(os.path.basename(path))

        self.loop_a = None
        self.loop_b = None
        self.loop_btn.setChecked(False)
        self.loop_on = False
        self._update_loop_markers()

        try:
            ffmpeg_path = get_dep_path(self.settings, "dep_ffmpeg")
            if not ffmpeg_path:
                ffmpeg_path = "ffmpeg"
            self.duration = self.waveform.load_audio_ffmpeg(path, ffmpeg_path)
            self.waveform.callback_seek = self.seek_to
        except Exception as e:
            QMessageBox.warning(
                self,
                self.tr("Audio Load Error"),
                self.tr(f"Could not load waveform.\n\nError: {e}"),
            )
            self.duration = 0

        if self.player:
            self.player.terminate()

        try:
            locale.setlocale(locale.LC_NUMERIC, "C")
        except locale.Error:
            pass

        self.player = mpv.MPV(input_default_bindings=True, osc=False)
        self.player.pause = True
        self.player.volume = self.volume
        self.player.play(path)
        self.play_btn.setText(self.tr("▶ Play"))
        self.update_status_bar()

    def _restore_audio_position(self, target_pos, retries=50):
        if not self.player:
            return
        if getattr(self.player, "duration", None) is not None:
            self.seek_to(target_pos)
            self.current_pos = target_pos
            self.update_ui()
        elif retries > 0:
            QTimer.singleShot(100, lambda: self._restore_audio_position(target_pos, retries - 1))

    # ------------------------------------------------------------------ playback controls
    def play_pause(self):
        if not self.player:
            return
        if self.player.pause:
            try:
                self.player.command("seek", f"{self.current_pos}", "absolute")
            except Exception:
                pass
            self.player.pause = False
            self.play_btn.setText(self.tr("⏸ Pause"))
            self.is_playing = True
            self._apply_loop_resume_check()
        else:
            self.player.pause = True
            self.play_btn.setText(self.tr("▶ Play"))
            self.is_playing = False

    def stop_play(self):
        if not self.player:
            return
        if not self.player.pause:
            self.stop()
        else:
            self.play_pause()

    def stop(self):
        if self.player:
            self.player.pause = True
            try:
                self.player.command("seek", "0", "absolute")
            except Exception:
                pass
            self.play_btn.setText(self.tr("▶ Play"))
            self.is_playing = False

    def seek_rel(self, seconds):
        if self.player:
            try:
                new_pos = max(0, min(self.duration, self.current_pos + seconds))
                self.player.command("seek", f"{new_pos}", "absolute")
            except Exception:
                pass

    def seek_to(self, seconds):
        if self.player:
            try:
                self.player.command("seek", f"{seconds}", "absolute")
            except Exception:
                pass

    def open_jump_dialog(self):
        if self.audio_file:
            JumpDialog(self, self.duration, self.current_pos, self.seek_to).show()

    # ------------------------------------------------------------------ speed / volume
    def set_speed(self, speed):
        self.speed = speed
        if self.player:
            self.player.speed = speed
        for btn, val in self.speed_btns:
            btn.setChecked(val == speed)

    def increase_speed(self):
        speeds = [0.25, 0.5, 0.75, 1.0]
        try:
            idx = speeds.index(self.speed)
        except ValueError:
            return
        if idx < len(speeds) - 1:
            self.set_speed(speeds[idx + 1])

    def decrease_speed(self):
        speeds = [0.25, 0.5, 0.75, 1.0]
        try:
            idx = speeds.index(self.speed)
        except ValueError:
            return
        if idx > 0:
            self.set_speed(speeds[idx - 1])

    def on_volume_change(self, val):
        self.volume = val
        if self.player:
            self.player.volume = val

    def increase_volume(self):
        self.vol_slider.setValue(min(100, self.volume + 10))

    def decrease_volume(self):
        self.vol_slider.setValue(max(0, self.volume - 10))

    # ------------------------------------------------------------------ window size
    def set_window_size(self, size):
        self.window_size = size
        for btn, val in self.win_btns:
            btn.setChecked(val == size)
        if getattr(self, "waveform", None) and self.waveform.bars is not None:
            self.update_ui()

    # ------------------------------------------------------------------ always-on-top
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
        if hasattr(self, "on_top_action"):
            self.on_top_action.setChecked(self.on_top_flag)

    # ------------------------------------------------------------------ timestamp insertion
    def insert_timestamp(self):
        if self.audio_file:
            self.editor.insert_timestamp(self.current_pos, self)
            QApplication.clipboard().setText(f"⟦{seconds_to_ts(self.current_pos)}⟧")

    # ------------------------------------------------------------------ A/B loop
    POS_EPSILON = 0.05

    def toggle_mark_a(self):
        pos = self.current_pos
        if self.loop_a is not None and abs(self.loop_a - pos) < self.POS_EPSILON:
            self.loop_a = None
        elif self.loop_a is None:
            if self.loop_b is not None and abs(self.loop_b - pos) < self.POS_EPSILON:
                self.loop_b = None
            self.loop_a = pos
        else:
            self.seek_to(self.loop_a)
        self._update_loop_markers()

    def toggle_mark_b(self):
        pos = self.current_pos
        if self.loop_b is not None and abs(self.loop_b - pos) < self.POS_EPSILON:
            self.loop_b = None
        elif self.loop_b is None:
            if self.loop_a is not None and abs(self.loop_a - pos) < self.POS_EPSILON:
                self.loop_a = None
            self.loop_b = pos
        else:
            self.seek_to(self.loop_b)
        self._update_loop_markers()

    def _update_loop_markers(self):
        if getattr(self, "waveform", None):
            self.waveform.set_markers(self.loop_a, self.loop_b)

    def set_loop_on(self, checked):
        self.loop_on = checked
        if checked:
            self._apply_loop_resume_check()

    LOOP_SEEK_GUARD_TIMEOUT_MS = 400

    def _apply_loop_resume_check(self):
        if not self.loop_on:
            return
        pos = self.current_pos
        if self.loop_b is not None and pos >= self.loop_b - 1e-3:
            self._perform_loop_seek(self.loop_a if self.loop_a is not None else 0)
        elif self.loop_a is not None and pos < self.loop_a - 1e-3:
            self._perform_loop_seek(self.loop_a)

    def _apply_loop_playback_tick(self):
        if not self.loop_on or not self.is_playing:
            return
        if getattr(self, "_loop_seek_pending", False):
            return
        pos = self.current_pos
        if self.loop_b is not None and pos >= self.loop_b - 1e-3:
            self._perform_loop_seek(self.loop_a if self.loop_a is not None else 0)
        elif self.loop_a is not None and pos < self.loop_a - 1e-3:
            self._perform_loop_seek(self.loop_a)

    def _perform_loop_seek(self, target):
        self._loop_seek_pending = True
        self._loop_seek_target = target
        self.seek_to(target)
        QTimer.singleShot(self.LOOP_SEEK_GUARD_TIMEOUT_MS, self._clear_loop_seek_guard)

    def _clear_loop_seek_guard(self):
        self._loop_seek_pending = False

    # ------------------------------------------------------------------ UI tick
    def update_ui(self):
        if not self.player:
            return
        try:
            pos = float(self.player.time_pos or 0)
        except Exception:
            return

        self.current_pos = max(0, min(self.duration, pos))
        self.time_label.setText(
            f"{seconds_to_ts(self.current_pos)} / {seconds_to_ts(self.duration)}"
        )

        if getattr(self, "_loop_seek_pending", False):
            target = getattr(self, "_loop_seek_target", None)
            if target is not None and abs(self.current_pos - target) < 0.15:
                self._loop_seek_pending = False

        self._apply_loop_playback_tick()

        if getattr(self, "waveform", None) and self.waveform.bars is not None:
            tb = len(self.waveform.bars)
            wb = max(1, int(self.window_size * 200))
            cb = int(self.current_pos * 200)
            sb = max(0, cb - wb // 2)
            sb = min(sb, max(0, tb - wb))
            self.waveform.set_window(sb, wb)
            self.waveform.set_position(cb)
