# handy_config_dialog.py
"""Standalone dialog for configuring the local Handy CLI transcription tool.

Follows the same pattern as cloud_config_dialog.py::CloudConfigDialog.
The old prefs_tab_handy.py (HandyTab) is superseded by this module and
should be deleted.
"""
import os
import json
import subprocess
import re

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFileDialog, QMessageBox,
    QDialogButtonBox,
)


class HandyConfigDialog(QDialog):
    """Standalone dialog to configure the Handy local CLI transcription tool."""

    def __init__(self, parent, settings):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle(self.tr("Handy CLI Transcription Tool Configuration"))
        self.setMinimumWidth(520)

        self._current_model = settings.value("handy_model", "base")
        self._current_device = settings.value("handy_device", "cpu")

        layout = QVBoxLayout(self)

        info = QLabel(self.tr(
            "Configure the local CLI transcription tool (Handy Tool), "
            "including the path to the executable and the active inference model."
        ))
        info.setWordWrap(True)
        info.setStyleSheet("margin-bottom: 10px;")
        layout.addWidget(info)

        layout.addWidget(QLabel(self.tr("Handy Binary Path:")))
        bin_layout = QHBoxLayout()
        current_bin = settings.value("handy_bin", "")
        self.bin_edit = QLineEdit(current_bin)
        self.browse_btn = QPushButton(self.tr("Browse..."))
        self.browse_btn.clicked.connect(self._browse_binary)
        bin_layout.addWidget(self.bin_edit)
        bin_layout.addWidget(self.browse_btn)
        layout.addLayout(bin_layout)

        self.refresh_btn = QPushButton(self.tr("Refresh Models && Devices"))
        self.refresh_btn.clicked.connect(self._refresh_info)
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

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if current_bin and os.path.exists(current_bin):
            self._refresh_info(silent=True)

    # ------------------------------------------------------------------
    def _browse_binary(self):
        path, _ = QFileDialog.getOpenFileName(self, self.tr("Select CLI Binary"))
        if path:
            self.bin_edit.setText(path)
            self._refresh_info()

    def _refresh_info(self, silent=False):
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
            res = subprocess.run(
                [bin_path, "--list-models", "--json"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            output_str = res.stdout.strip()
            json_start = output_str.find("[")
            models = json.loads(output_str[json_start:]) if json_start != -1 else []
            for m in [m for m in models if isinstance(m, dict)]:
                m_id = str(m.get("id", ""))
                disp = f"{'✓' if m.get('is_downloaded') else '  '} {m.get('name', m_id)}"
                self.model_combo.addItem(disp, m_id)
            idx = self.model_combo.findData(self._current_model)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
        except Exception as e:
            if not silent:
                print(f"Failed to fetch models: {e}")

        try:
            res = subprocess.run(
                [bin_path, "--list-devices"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            for line in res.stdout.splitlines():
                if line.strip().startswith("index="):
                    idx_match = re.search(r"index=(\d+)", line)
                    kind_match = re.search(r"kind=(\S+)", line)
                    name_match = re.search(r"name=(.+?)(?:\s+vram=|$)", line)
                    if idx_match and name_match:
                        kind = kind_match.group(1) if kind_match else "unknown"
                        self.device_combo.addItem(
                            f"[{kind}:{idx_match.group(1)}] {name_match.group(1).strip()}",
                            idx_match.group(1),
                        )
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
            self.refresh_btn.setText(self.tr("Refresh Models && Devices"))

    def _save_and_accept(self):
        self.settings.setValue("handy_bin", self.bin_edit.text().strip())
        midx = self.model_combo.currentIndex()
        if midx >= 0:
            self.settings.setValue("handy_model", self.model_combo.itemData(midx))
        didx = self.device_combo.currentIndex()
        if didx >= 0:
            self.settings.setValue("handy_device", self.device_combo.itemData(didx))
        self.accept()
