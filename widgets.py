# widgets.py
import numpy as np
import os
import subprocess
import tempfile
import wave
from PyQt5.QtWidgets import QWidget, QLabel, QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QCheckBox
from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtGui import QPainter, QPen, QFont, QColor, QTextDocument, QTextCursor

class ColorLabel(QLabel):
    def __init__(self, text=""):
        super().__init__(text)
        self.setAlignment(Qt.AlignCenter)
        font = QFont("Courier")
        font.setStyleHint(QFont.TypeWriter)
        font.setPointSize(20)
        font.setBold(True)
        self.setFont(font)
        self.setMinimumHeight(44)
        self.setStyleSheet("background-color: black; color: cyan;")

class WaveformWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.bars = None
        self.position = 0
        self.window_start = 0
        self.window_len = 1
        self.active = False
        self.sample_rate = None
        self.duration = 0
        self.callback_seek = None
        self.marker_a = None
        self.marker_b = None
        self.setMinimumHeight(80)

    def load_audio_ffmpeg(self, path, ffmpeg_bin="ffmpeg"):
        temp_wav = None
        try:
            temp_wav = os.path.join(tempfile.gettempdir(), "waveform_temp.wav")
            if os.path.exists(temp_wav):
                try: os.remove(temp_wav)
                except Exception: pass

            cmd = [
                ffmpeg_bin, "-y", "-i", path,
                "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
                temp_wav
            ]
            # Will raise FileNotFoundError if ffmpeg_bin is invalid
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            with wave.open(temp_wav, 'rb') as wf:
                sr = wf.getframerate()
                n_frames = wf.getnframes()
                audio_bytes = wf.readframes(n_frames)

            data_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
            data = data_int16.astype(np.float32) / 32768.0

            self.set_audio(data, sr)
            return len(data) / sr

        except Exception as e:
            print(f"Error generating waveform: {e}")
            self.set_audio(None, None)
            raise e

        finally:
            if temp_wav and os.path.exists(temp_wav):
                try: os.remove(temp_wav)
                except Exception: pass

    def set_audio(self, data, sr):
        self.active = data is not None
        if self.active:
            self.sample_rate = sr
            self.duration = len(data) / sr

            bars_per_sec = 200
            samples_per_bar = max(1, int(sr / bars_per_sec))
            total_bars = len(data) // samples_per_bar

            if total_bars > 0:
                truncated = data[:total_bars * samples_per_bar]
                reshaped = truncated.reshape((total_bars, samples_per_bar))
                self.bars = np.max(np.abs(reshaped), axis=1)
            else:
                self.bars = np.array([])

            self.window_len = bars_per_sec
        else:
            self.bars = None
            self.window_len = 1
            self.duration = 0
        self.marker_a = None
        self.marker_b = None
        self.update()

    def set_window(self, start_frame, window_frames):
        if not self.active or self.bars is None: return
        window_frames = max(1, window_frames)
        start_frame = max(0, min(start_frame, len(self.bars) - window_frames))
        self.window_start = start_frame
        self.window_len = window_frames
        self.update()

    def set_position(self, frame_idx):
        self.position = frame_idx
        self.update()

    def set_markers(self, a_seconds, b_seconds):
        self.marker_a = a_seconds
        self.marker_b = b_seconds
        self.update()

    def _frame_to_x(self, frame, w):
        x = int((frame - self.window_start) * w / self.window_len)
        return x

    def paintEvent(self, event):
        if not self.active or self.bars is None or self.window_len < 1:
            painter = QPainter(self)
            painter.fillRect(0, 0, self.width(), self.height(), Qt.black)
            painter.end()
            return

        painter = QPainter(self)
        w, h = self.width(), self.height()
        center = h // 2

        data = self.bars[self.window_start:self.window_start + self.window_len]
        max_val = data.max() if data.size else 1.0
        if max_val == 0.0: max_val = 1.0

        painter.fillRect(0, 0, w, h, Qt.black)
        painter.setPen(QPen(Qt.cyan))

        for i, val in enumerate(data):
            x = int(i * w / self.window_len)
            y = int((val / max_val) * (h / 2.8))
            painter.drawLine(x, center - y, x, center + y)

        # --- A/B loop markers (orange bars with letter labels) ---
        marker_font = QFont("Courier New")
        marker_font.setBold(True)
        marker_font.setPointSize(9)
        painter.setFont(marker_font)

        if self.marker_a is not None:
            frame_a = self.marker_a * 200.0
            x_a = self._frame_to_x(frame_a, w)
            if 0 <= x_a <= w:
                painter.setPen(QPen(QColor(255, 165, 0), 2))
                painter.drawLine(x_a, 0, x_a, h)
                painter.setPen(QPen(QColor(255, 165, 0)))
                painter.drawText(x_a + 2, 12, "A")

        if self.marker_b is not None:
            frame_b = self.marker_b * 200.0
            x_b = self._frame_to_x(frame_b, w)
            if 0 <= x_b <= w:
                painter.setPen(QPen(QColor(255, 140, 0), 2))
                painter.drawLine(x_b, 0, x_b, h)
                painter.setPen(QPen(QColor(255, 140, 0)))
                painter.drawText(x_b + 2, 12, "B")

        cursor_x = int((self.position - self.window_start) * w / self.window_len)
        cursor_x = max(0, min(cursor_x, w))
        painter.setPen(QPen(Qt.red, 2))
        painter.drawLine(cursor_x, 0, cursor_x, h)
        painter.end()

    def mousePressEvent(self, event):
        if not self.active or self.bars is None or self.callback_seek is None: return
        x = event.pos().x()
        frame = int(self.window_start + x * self.window_len / self.width())
        self.callback_seek(frame / 200.0)

class FindDialog(QDialog):
    def __init__(self, parent, editor):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Find"))
        self.editor = editor
        self.setWindowFlags(self.windowFlags() | Qt.Tool)

        layout = QVBoxLayout(self)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.tr("Text to find..."))
        layout.addWidget(self.search_input)

        self.regex_cb = QCheckBox(self.tr("Regular Expression"))
        layout.addWidget(self.regex_cb)

        btn_layout = QHBoxLayout()
        self.find_prev_btn = QPushButton(self.tr("Find Previous"))
        self.find_next_btn = QPushButton(self.tr("Find Next"))

        btn_layout.addWidget(self.find_prev_btn)
        btn_layout.addWidget(self.find_next_btn)
        layout.addLayout(btn_layout)

        self.find_next_btn.clicked.connect(lambda: self._do_find(False))
        self.find_prev_btn.clicked.connect(lambda: self._do_find(True))
        self.search_input.returnPressed.connect(lambda: self._do_find(False))

    def _do_find(self, backward):
        text = self.search_input.text()
        if not text: return

        from PyQt5.QtGui import QTextDocument
        from PyQt5.QtCore import QRegularExpression

        options = QTextDocument.FindFlags()
        if backward: options |= QTextDocument.FindBackward

        query = QRegularExpression(text) if self.regex_cb.isChecked() else text

        found = self.editor.find(query, options)
        if not found:
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.End if backward else QTextCursor.Start)
            self.editor.setTextCursor(cursor)
            found = self.editor.find(query, options)

        if found:
            self.editor.highlight_find_result()
        else:
            self.editor.find_extra_selections = []
            self.editor._apply_all_extra_selections()

class JumpDialog(QWidget):
    def __init__(self, parent, duration, current_pos, callback):
        super().__init__(parent, Qt.Window | Qt.WindowStaysOnTopHint)
        self.setWindowTitle(self.tr("Jump To Position"))
        self.setWindowModality(Qt.ApplicationModal)
        self.resize(450, 180)
        layout = QVBoxLayout(self)

        from PyQt5.QtWidgets import QSlider
        from utils import seconds_to_ts
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, int(duration * 10))
        self.slider.setValue(int(current_pos * 10))
        layout.addWidget(self.slider)

        self.pos_label = ColorLabel(f"{seconds_to_ts(current_pos)} / {seconds_to_ts(duration)}")
        layout.addWidget(self.pos_label)

        btn_layout = QHBoxLayout()
        ok = QPushButton(self.tr("OK")); ok.clicked.connect(lambda: [callback(self.slider.value() / 10), self.close()])
        cl = QPushButton(self.tr("Cancel")); cl.clicked.connect(self.close)
        btn_layout.addWidget(ok); btn_layout.addWidget(cl)
        layout.addLayout(btn_layout)

        self.slider.valueChanged.connect(lambda v: self.pos_label.setText(f"{seconds_to_ts(v/10)} / {seconds_to_ts(duration)}"))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Left: self.slider.setValue(max(0, self.slider.value() - 1))
        elif event.key() == Qt.Key_Right: self.slider.setValue(min(self.slider.maximum(), self.slider.value() + 1))
        elif event.key() in (Qt.Key_Enter, Qt.Key_Return): self.on_ok()
        elif event.key() == Qt.Key_Escape: self.close()
        else: super().keyPressEvent(event)
