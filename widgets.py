import json
import numpy as np
import os
import re
import subprocess
import tempfile
import wave
from PyQt5.QtWidgets import (QWidget, QLabel, QDialog, QVBoxLayout, QHBoxLayout, 
                             QGridLayout, QLineEdit, QPushButton, QSlider, 
                             QColorDialog, QFontDialog, QCheckBox, QFileDialog, 
                             QComboBox, QMessageBox)
from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtGui import QPainter, QPen, QFont, QColor, QTextDocument, QTextCursor
from utils import seconds_to_ts

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
        self.setMinimumHeight(80)

    def load_audio_ffmpeg(self, path):
        temp_wav = None
        try:
            temp_wav = os.path.join(tempfile.gettempdir(), "waveform_temp.wav")
            if os.path.exists(temp_wav):
                try: os.remove(temp_wav)
                except Exception: pass

            cmd = [
                "ffmpeg", "-y", "-i", path, 
                "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", 
                temp_wav
            ]
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
            return 0
            
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
        if max_val == 0.0:
            max_val = 1.0
            
        painter.fillRect(0, 0, w, h, Qt.black)
        painter.setPen(QPen(Qt.cyan))
        
        for i, val in enumerate(data):
            x = int(i * w / self.window_len)
            y = int((val / max_val) * (h / 2.8))
            painter.drawLine(x, center - y, x, center + y)
            
        cursor_x = int((self.position - self.window_start) * w / self.window_len)
        cursor_x = max(0, min(cursor_x, w))
        painter.setPen(QPen(Qt.red, 2))
        painter.drawLine(cursor_x, 0, cursor_x, h)
        painter.end()

    def mousePressEvent(self, event):
        if not self.active or self.bars is None or self.callback_seek is None: return
        x = event.pos().x()
        
        frame = int(self.window_start + x * self.window_len / self.width())
        seconds = frame / 200.0  
        self.callback_seek(seconds)


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

        self.find_next_btn.clicked.connect(self.find_next)
        self.find_prev_btn.clicked.connect(self.find_prev)
        self.search_input.returnPressed.connect(self.find_next)

    def find_next(self):
        self._do_find(False)

    def find_prev(self):
        self._do_find(True)

    def _do_find(self, backward):
        text = self.search_input.text()
        if not text: return

        options = QTextDocument.FindFlags()
        if backward:
            options |= QTextDocument.FindBackward

        if self.regex_cb.isChecked():
            regex = QRegExp(text)
            found = self.editor.find(regex, options)
        else:
            found = self.editor.find(text, options)
            
        if not found:
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.End if backward else QTextCursor.Start)
            self.editor.setTextCursor(cursor)

            if self.regex_cb.isChecked():
                self.editor.find(QRegExp(text), options)
            else:
                self.editor.find(text, options)


# --- WIDGET TABS FOR PREFERENCES ---

class HandyConfigWidget(QWidget):
    def __init__(self, parent, current_bin, current_model, current_device):
        super().__init__(parent)
        self._current_model = current_model
        self._current_device = current_device
        
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(self.tr("Handy Binary Path:")))
        bin_layout = QHBoxLayout()
        self.bin_edit = QLineEdit(current_bin)
        self.browse_btn = QPushButton(self.tr("Browse..."))
        self.browse_btn.clicked.connect(self.browse_binary)
        bin_layout.addWidget(self.bin_edit)
        bin_layout.addWidget(self.browse_btn)
        layout.addLayout(bin_layout)

        self.refresh_btn = QPushButton(self.tr("Refresh Models & Devices"))
        self.refresh_btn.clicked.connect(self.refresh_info)
        layout.addWidget(self.refresh_btn)

        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel(self.tr("Model:")))
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(300)
        model_layout.addWidget(self.model_combo, 1)
        layout.addLayout(model_layout)

        device_layout = QHBoxLayout()
        device_layout.addWidget(QLabel(self.tr("Device:")))
        self.device_combo = QComboBox()
        device_layout.addWidget(self.device_combo, 1)
        layout.addLayout(device_layout)
        
        layout.addStretch()

        if current_bin and os.path.exists(current_bin):
            self.refresh_info(silent=True)

    def browse_binary(self):
        path, _ = QFileDialog.getOpenFileName(self, self.tr("Select CLI Binary"))
        if path:
            self.bin_edit.setText(path)
            self.refresh_info()

    def refresh_info(self, silent=False):
        bin_path = self.bin_edit.text().strip()
        if not bin_path or not os.path.isfile(bin_path):
            if not silent:
                QMessageBox.warning(self, self.tr("Error"), self.tr("Invalid binary path."))
            return

        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText(self.tr("Querying..."))

        self.model_combo.clear()
        self.model_combo.addItem(self.tr("Default (Auto)"), "")
        self.device_combo.clear()
        self.device_combo.addItem(self.tr("Default (Auto)"), "")

        try:
            res = subprocess.run([bin_path, "--list-models", "--json"], 
                                 capture_output=True, text=True, encoding="utf-8", errors="replace")
            
            output_str = res.stdout.strip()
            json_start = output_str.find('[')
            if json_start != -1:
                models = json.loads(output_str[json_start:])
            else:
                models = []

            installed_models = []
            uninstalled_models = []
            
            for m in models:
                if not isinstance(m, dict):
                    continue
                    
                model_id = str(m.get("id", ""))
                model_name = str(m.get("name", model_id))
                is_downloaded = m.get("is_downloaded", False)
                
                if is_downloaded:
                    display_name = f"✓ {model_name}"
                    installed_models.append((display_name, model_id))
                else:
                    display_name = f"   {model_name}"
                    uninstalled_models.append((display_name, model_id))

            for display_name, model_id in installed_models:
                self.model_combo.addItem(display_name, model_id)
                
            if installed_models and uninstalled_models:
                self.model_combo.insertSeparator(self.model_combo.count())
                
            for display_name, model_id in uninstalled_models:
                self.model_combo.addItem(display_name, model_id)

            if self._current_model:
                idx = self.model_combo.findData(self._current_model)
                if idx >= 0:
                    self.model_combo.setCurrentIndex(idx)

        except Exception as e:
            if not silent:
                print(f"Failed to fetch models: {e}")

        try:
            res = subprocess.run([bin_path, "--list-devices"], 
                                 capture_output=True, text=True, encoding="utf-8", errors="replace")
            
            for line in res.stdout.splitlines():
                line = line.strip()
                if line.startswith("index="):
                    idx_match = re.search(r"index=(\d+)", line)
                    kind_match = re.search(r"kind=(\S+)", line)
                    name_match = re.search(r"name=(.+?)(?:\s+vram=|$)", line)
                    
                    if idx_match and name_match:
                        device_index = idx_match.group(1)
                        kind = kind_match.group(1) if kind_match else "unknown"
                        name = name_match.group(1).strip()
                            
                        dev_name = f"[{kind}:{device_index}] {name}"
                        
                        self.device_combo.addItem(dev_name, device_index)

            if self._current_device:
                idx = self.device_combo.findData(self._current_device)
                if idx >= 0:
                    self.device_combo.setCurrentIndex(idx)

            if not silent:
                QMessageBox.information(self, self.tr("Success"), self.tr("Successfully refreshed info."))

        except Exception as e:
            if not silent:
                print(f"Failed to fetch devices: {e}")

        finally:
            self.refresh_btn.setEnabled(True)
            self.refresh_btn.setText(self.tr("Refresh Models & Devices"))

    @property
    def bin_path(self): 
        return self.bin_edit.text().strip()
    
    @property
    def model(self): 
        idx = self.model_combo.currentIndex()
        if idx >= 0 and self.model_combo.itemData(idx):
            return self.model_combo.itemData(idx)
        return ""
    
    @property
    def device(self): 
        idx = self.device_combo.currentIndex()
        if idx >= 0 and self.device_combo.itemData(idx):
            return self.device_combo.itemData(idx)
        return ""

class SpeakerConfigWidget(QWidget):
    def __init__(self, parent, current_speakers):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.edits = []
        for i in range(6):
            row = QHBoxLayout()
            row.addWidget(QLabel(self.tr("Speaker {0}:").format(i+1)))
            edit = QLineEdit(current_speakers[i] if i < len(current_speakers) else f"SPEAKER_0{i}")
            self.edits.append(edit)
            row.addWidget(edit)
            layout.addLayout(row)
        layout.addStretch()

    @property
    def result_speakers(self):
        return [e.text().strip() for e in self.edits]


class EditorConfigWidget(QWidget):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = config.copy()

        layout = QVBoxLayout(self)
        grid = QGridLayout()

        labels = [
            ("text_fg", self.tr("General Text Foreground")),
            ("text_bg", self.tr("General Text Background")),
            ("ts_fg", self.tr("Timestamp Foreground")),
            ("ts_bg", self.tr("Timestamp Background")),
            ("spk_fg", self.tr("Speaker Tag Foreground")),
            ("spk_bg", self.tr("Speaker Tag Background")),
        ]
        
        self.color_btns = {}
        for i, (key, label) in enumerate(labels):
            grid.addWidget(QLabel(label), i, 0)
            btn = QPushButton()
            self._update_btn_color(btn, self.config.get(key, ""))
            btn.clicked.connect(lambda checked, k=key, b=btn: self._pick_color(k, b))
            grid.addWidget(btn, i, 1)

            clear_btn = QPushButton(self.tr("Clear"))
            clear_btn.clicked.connect(lambda checked, k=key, b=btn: self._clear_color(k, b))
            grid.addWidget(clear_btn, i, 2)
            self.color_btns[key] = btn

        layout.addLayout(grid)

        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel(self.tr("Editor Font:")))
        self.font_btn = QPushButton(self.tr("Select Font..."))
        self.font_btn.clicked.connect(self._pick_font)
        font_layout.addWidget(self.font_btn)
        layout.addLayout(font_layout)
        layout.addStretch()

    def _update_btn_color(self, btn, color_str):
        if color_str:
            btn.setStyleSheet(f"background-color: {color_str};")
            btn.setText("")
        else:
            btn.setStyleSheet("")
            btn.setText(self.tr("Default"))

    def _clear_color(self, key, btn):
        self.config[key] = ""
        self._update_btn_color(btn, "")

    def _pick_color(self, key, btn):
        initial = QColor(self.config.get(key, "#ffffff")) if self.config.get(key) else Qt.white
        color = QColorDialog.getColor(initial, self, self.tr("Select Color"))
        if color.isValid():
            hex_color = color.name()
            self.config[key] = hex_color
            self._update_btn_color(btn, hex_color)

    def _pick_font(self):
        font = QFont()
        if self.config.get("font"):
            font.fromString(self.config["font"])
        font, ok = QFontDialog.getFont(font, self, self.tr("Select Editor Font"))
        if ok:
            self.config["font"] = font.toString()


class JumpDialog(QWidget):
    def __init__(self, parent, duration, current_pos, callback):
        super().__init__(parent, Qt.Window | Qt.WindowStaysOnTopHint)
        self.setWindowTitle(self.tr("Jump To Position"))
        self.setWindowModality(Qt.ApplicationModal)
        self.duration = duration
        self.callback = callback
        self.resize(450, 180)
        layout = QVBoxLayout(self)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, int(duration * 10))
        self.slider.setValue(int(current_pos * 10))
        layout.addWidget(self.slider)
        self.pos_label = ColorLabel(f"{seconds_to_ts(current_pos)} / {seconds_to_ts(duration)}")
        layout.addWidget(self.pos_label)
        btn_layout = QHBoxLayout()
        ok = QPushButton(self.tr("OK")); ok.clicked.connect(self.on_ok)
        cl = QPushButton(self.tr("Cancel")); cl.clicked.connect(self.close)
        btn_layout.addWidget(ok); btn_layout.addWidget(cl)
        layout.addLayout(btn_layout)
        self.slider.valueChanged.connect(lambda v: self.pos_label.setText(f"{seconds_to_ts(v/10)} / {seconds_to_ts(duration)}"))

    def on_ok(self):
        self.callback(self.slider.value() / 10)
        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Left: self.slider.setValue(max(0, self.slider.value() - 1))
        elif event.key() == Qt.Key_Right: self.slider.setValue(min(self.slider.maximum(), self.slider.value() + 1))
        elif event.key() in (Qt.Key_Enter, Qt.Key_Return): self.on_ok()
        elif event.key() == Qt.Key_Escape: self.close()
        else: super().keyPressEvent(event)
