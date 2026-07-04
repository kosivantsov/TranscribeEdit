# io_mixin.py
"""IOMixin — extracted from main.py.

Contains all project/JSON/audio file I/O: load_project, save_project,
save_project_as, open_file, load_json, save_json, save_json_as, export_file,
send_to_cloud, transcribe_with_handy, and their worker callbacks.
"""
import os
import json
import zipfile
import tempfile
import shutil

from PyQt5.QtWidgets import QFileDialog, QMessageBox, QProgressDialog
from PyQt5.QtCore import Qt

from exporter import export as export_segments, get_filter
from cloud_client import CloudWorker, CloudWorkerSignals
from cli_connector import CliTranscribeWorker, CliTranscribeSignals
from prefs_tab_deps import get_dep_path


class IOMixin:
    """Mixin providing all project/file I/O behaviour for AudioPlayer."""

    # ------------------------------------------------------------------ open audio
    def open_file(self):
        last_dir = self.settings.value("last_audio_dir", "")
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Open Audio"),
            last_dir,
            self.tr("Audio Files (*.mp3 *.wav *.flac *.ogg *.m4a *.aac)"),
        )
        if not path:
            return
        self.settings.setValue("last_audio_dir", os.path.dirname(path))
        self.current_project_path = None
        self._open_audio_path(path)

    # ------------------------------------------------------------------ project I/O
    def load_project(self):
        last_dir = self.settings.value("last_proj_dir", "")
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Open Project"),
            last_dir,
            self.tr("TranscribeEdit Projects (*.teproj)"),
        )
        if not path:
            return
        self.settings.setValue("last_proj_dir", os.path.dirname(path))

        temp_dir = os.path.join(tempfile.gettempdir(), "te_active_project")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        os.makedirs(temp_dir, exist_ok=True)

        try:
            with zipfile.ZipFile(path, "r") as zf:
                zf.extractall(temp_dir)

            with open(os.path.join(temp_dir, "data.json"), "r", encoding="utf-8") as f:
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
        if getattr(self, "current_project_path", None):
            return self._do_save_project(self.current_project_path)
        return self.save_project_as()

    def save_project_as(self):
        last_dir = self.settings.value("last_proj_dir", "")
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save Project"),
            last_dir,
            self.tr("TranscribeEdit Projects (*.teproj)"),
        )
        if path:
            if not path.lower().endswith(".teproj"):
                path += ".teproj"
            return self._do_save_project(path)
        return False

    def _do_save_project(self, path):
        if not self.audio_file or not os.path.exists(self.audio_file):
            QMessageBox.warning(
                self,
                self.tr("No Audio"),
                self.tr("Cannot save a project without an active audio file."),
            )
            return False
        try:
            data = {
                "audio_file": os.path.basename(self.audio_file),
                "audio_pos": self.current_pos,
                "cursor_pos": self.editor.textCursor().position(),
                "segments": self.editor.to_segments(),
                "raw_text": self.editor.toPlainText(),
            }
            with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as zf:
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

    # ------------------------------------------------------------------ JSON I/O
    def load_json(self):
        last_dir = self.settings.value("last_json_dir", "")
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Load JSON"), last_dir, self.tr("JSON Files (*.json)")
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                segments = data.get("segments", data) if isinstance(data, dict) else data
                self.editor.load_segments(segments)
                self.current_json_path = path
                self.current_project_path = None
                self.settings.setValue("last_json_dir", os.path.dirname(path))
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
        last_dir = self.settings.value("last_json_dir", "")
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Save JSON as"), last_dir, self.tr("JSON Files (*.json)")
        )
        if path:
            if not path.lower().endswith(".json"):
                path += ".json"
            return self._do_save_json(path)
        return False

    def _do_save_json(self, path):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.editor.to_segments(), f, indent=2, ensure_ascii=False)
            self.current_json_path = path
            self.settings.setValue("last_json_dir", os.path.dirname(path))
            self.editor.document().setModified(False)
            self.update_status_bar()
            return True
        except Exception as e:
            QMessageBox.critical(self, self.tr("Save Error"), str(e))
            return False

    # ------------------------------------------------------------------ export
    def export_file(self, fmt):
        last_dir = self.settings.value("last_export_dir", "")
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr(f"Export {fmt.upper()}"), last_dir, get_filter(fmt)
        )
        if path:
            try:
                ext = path.split(".")[-1].lower() if "." in path else ""
                valid_exts = [fmt]
                if fmt == "html":
                    valid_exts.extend(["html", "htm"])
                if fmt == "ass":
                    valid_exts.extend(["ass", "ssa"])
                if not ext or ext not in valid_exts:
                    path += f".{fmt}"

                opts = {
                    "md_format_string": self.settings.value("export_md_format", ""),
                    "html_format_string": self.settings.value("export_html_format", ""),
                }
                content = export_segments(self.editor.to_segments(), fmt, opts)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.settings.setValue("last_export_dir", os.path.dirname(path))
            except Exception as e:
                QMessageBox.critical(self, self.tr("Export Error"), str(e))

    # ------------------------------------------------------------------ cloud
    def send_to_cloud(self):
        if not self.audio_file:
            QMessageBox.warning(
                self, self.tr("No audio"), self.tr("Please open an audio file first.")
            )
            return

        profiles_str = self.settings.value("cloud_profiles", "{}")
        try:
            profiles = json.loads(profiles_str) if isinstance(profiles_str, str) else profiles_str
        except Exception:
            profiles = {}

        current_name = self.settings.value("current_cloud_profile", "")
        config = profiles.get(current_name, {})

        if not config.get("url"):
            QMessageBox.warning(
                self,
                self.tr("Configuration Missing"),
                self.tr("Please configure the Cloud API first."),
            )
            self.open_cloud_config()
            return

        self.progress = QProgressDialog(
            self.tr("Sending to Cloud API…"), self.tr("Cancel"), 0, 100, self
        )
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

    # ------------------------------------------------------------------ handy cli tool
    def transcribe_with_handy(self):
        if not self.audio_file:
            QMessageBox.warning(
                self, self.tr("No audio"), self.tr("Please open an audio file first.")
            )
            return

        handy_bin = get_dep_path(self.settings, "handy_bin")
        if not handy_bin or not os.path.exists(handy_bin):
            QMessageBox.warning(
                self,
                self.tr("Handy Binary Missing"),
                self.tr("Please configure the Handy Tool path in Options > Handy Tool Configuration."),
            )
            return

        self._handy_progress = QProgressDialog(
            self.tr("Starting Handy Tool..."), self.tr("Cancel"), 0, 100, self
        )
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
            handy_bin,
            self.audio_file,
            self.duration,
            handy_model,
            handy_device,
            self._handy_signals,
        )
        self._handy_progress.canceled.connect(self._handy_worker.cancel)
        self._handy_worker.start()

    def _on_handy_progress(self, pct, msg):
        if hasattr(self, "_handy_progress") and self._handy_progress:
            if self._handy_progress.wasCanceled():
                return
            self._handy_progress.setValue(pct)
            self._handy_progress.setLabelText(msg)

    def _on_handy_finished(self, segments):
        if hasattr(self, "_handy_progress") and self._handy_progress:
            self._handy_progress.close()
        if not segments:
            QMessageBox.information(
                self, self.tr("No result"), self.tr("Handy returned no segments.")
            )
            return
        self.editor.load_segments(segments)
        self.editor.document().setModified(True)
        self.update_status_bar()

    def _on_handy_error(self, msg):
        if hasattr(self, "_handy_progress") and self._handy_progress:
            self._handy_progress.close()
        QMessageBox.critical(self, self.tr("Handy Tool Error"), msg)
