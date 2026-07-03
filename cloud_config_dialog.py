# cloud_config_dialog.py
import json
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QLabel, QLineEdit, QPushButton, QComboBox, 
                             QTableWidget, QTableWidgetItem, QHeaderView, 
                             QTabWidget, QWidget, QInputDialog, QMessageBox, 
                             QFrame, QCheckBox)
from PyQt5.QtCore import Qt, QSettings

class CloudConfigDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Cloud API Configuration"))
        self.setMinimumWidth(650)
        self.setMinimumHeight(550)
        
        self.settings = QSettings("TranscribeEdit", "TranscribeEdit")
        self._load_profiles()

        layout = QVBoxLayout(self)

        # 1. Profile Manager Section
        prof_layout = QHBoxLayout()
        prof_layout.addWidget(QLabel(self.tr("Profile:")))
        self.profile_combo = QComboBox()
        self.profile_combo.addItems(list(self.profiles.keys()))
        self.profile_combo.setCurrentText(self.current_profile_name)
        self.profile_combo.currentTextChanged.connect(self.load_profile_to_ui)
        prof_layout.addWidget(self.profile_combo, 1)

        save_prof_btn = QPushButton(self.tr("Save"))
        save_prof_btn.clicked.connect(self.save_current_profile)
        save_as_btn = QPushButton(self.tr("Save As..."))
        save_as_btn.clicked.connect(self.save_as_profile)
        del_prof_btn = QPushButton(self.tr("Delete"))
        del_prof_btn.clicked.connect(self.delete_profile)
        
        prof_layout.addWidget(save_prof_btn)
        prof_layout.addWidget(save_as_btn)
        prof_layout.addWidget(del_prof_btn)
        layout.addLayout(prof_layout)
        
        line = QFrame(); line.setFrameShape(QFrame.HLine); line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        # 2. Top Section: URL & Format
        grid = QGridLayout()
        grid.addWidget(QLabel(self.tr("Initial POST Endpoint URL:")), 0, 0)
        self.url_edit = QLineEdit()
        grid.addWidget(self.url_edit, 0, 1)

        grid.addWidget(QLabel(self.tr("Expected Final Response Format:")), 1, 0)
        self.format_combo = QComboBox()
        for fmt in ["json (OpenAI/Lemonfox)", "json (Whisper.cpp/segments)", "text", "srt", "vtt"]:
            self.format_combo.addItem(fmt)
        grid.addWidget(self.format_combo, 1, 1)

        # Async Polling Checkbox
        self.async_cb = QCheckBox(self.tr("Enable Two-Step (Async) Polling"))
        self.async_cb.toggled.connect(self._toggle_polling_tab)
        grid.addWidget(self.async_cb, 2, 0, 1, 2)
        
        layout.addLayout(grid)

        # 3. Tabs Section
        self.tabs = QTabWidget()
        self.vars_table = self._create_table_tab(self.tabs, self.tr("Variables"), "Define variables here. They can be used in URL, Headers or Form-Data as ${VAR_NAME}.\\nNote: ${FILE} is automatically injected at runtime.")
        self.headers_table = self._create_table_tab(self.tabs, self.tr("Headers"), "Define HTTP Headers (e.g., Authorization: Bearer ${APIKEY})")
        self.data_table = self._create_table_tab(self.tabs, self.tr("Form-Data"), "Define Form-Data (e.g., model: whisper-1).\\nIf a Value is exactly ${FILE}, that Key becomes the audio file upload parameter.")
        
        # Async Polling Tab
        self.poll_tab = QWidget()
        poll_layout = QGridLayout(self.poll_tab)
        
        poll_layout.addWidget(QLabel(self.tr("Job ID JSON Key (from initial response):")), 0, 0)
        self.poll_job_id_key = QLineEdit()
        self.poll_job_id_key.setPlaceholderText("id")
        poll_layout.addWidget(self.poll_job_id_key, 0, 1)

        poll_layout.addWidget(QLabel(self.tr("Polling URL (use ${JOB_ID}):")), 1, 0)
        self.poll_url = QLineEdit()
        self.poll_url.setPlaceholderText("https://api.example.com/v1/jobs/${JOB_ID}")
        poll_layout.addWidget(self.poll_url, 1, 1)

        poll_layout.addWidget(QLabel(self.tr("Status JSON Key (from poll response):")), 2, 0)
        self.poll_status_key = QLineEdit()
        self.poll_status_key.setPlaceholderText("status")
        poll_layout.addWidget(self.poll_status_key, 2, 1)

        poll_layout.addWidget(QLabel(self.tr("Ready Value (e.g., 'completed'):")), 3, 0)
        self.poll_ready_val = QLineEdit()
        self.poll_ready_val.setPlaceholderText("completed")
        poll_layout.addWidget(self.poll_ready_val, 3, 1)

        poll_layout.addWidget(QLabel(self.tr("Fail Value (e.g., 'failed'):")), 4, 0)
        self.poll_fail_val = QLineEdit()
        self.poll_fail_val.setPlaceholderText("failed")
        poll_layout.addWidget(self.poll_fail_val, 4, 1)

        poll_layout.addWidget(QLabel(self.tr("Result JSON Key (Optional, if wrapped):")), 5, 0)
        self.poll_result_key = QLineEdit()
        self.poll_result_key.setPlaceholderText("result")
        poll_layout.addWidget(self.poll_result_key, 5, 1)

        poll_layout.addWidget(QLabel(self.tr("Polling Interval (seconds):")), 6, 0)
        self.poll_interval = QLineEdit("5")
        poll_layout.addWidget(self.poll_interval, 6, 1)
        poll_layout.setRowStretch(7, 1)

        self.tabs.addTab(self.poll_tab, self.tr("Polling Settings"))
        self._toggle_polling_tab(False) # Default state

        layout.addWidget(self.tabs)

        # 4. Save/Cancel
        bottom_btns = QHBoxLayout()
        close_btn = QPushButton(self.tr("Close"))
        close_btn.clicked.connect(self.accept)
        bottom_btns.addStretch()
        bottom_btns.addWidget(close_btn)
        layout.addLayout(bottom_btns)

        self.load_profile_to_ui(self.current_profile_name)

    def _toggle_polling_tab(self, checked):
        self.tabs.setTabEnabled(3, checked)

    def _load_profiles(self):
        profiles_str = self.settings.value("cloud_profiles", "{}")
        try:
            self.profiles = json.loads(profiles_str) if isinstance(profiles_str, str) else profiles_str
        except Exception:
            self.profiles = {}

        if not isinstance(self.profiles, dict) or not self.profiles:
            self.profiles = {
                "Default OpenAI": {
                    "url": "https://api.openai.com/v1/audio/transcriptions",
                    "response_type": "json (OpenAI/Lemonfox)",
                    "variables": {"APIKEY": ""},
                    "headers": {"Authorization": "Bearer ${APIKEY}"},
                    "data": {"model": "whisper-1", "file": "${FILE}"},
                    "async": {"enabled": False}
                }
            }
        
        self.current_profile_name = self.settings.value("current_cloud_profile", list(self.profiles.keys())[0])
        if self.current_profile_name not in self.profiles:
            self.current_profile_name = list(self.profiles.keys())[0]

    def _save_profiles_to_settings(self):
        self.settings.setValue("cloud_profiles", json.dumps(self.profiles))
        self.settings.setValue("current_cloud_profile", self.current_profile_name)

    def _create_table_tab(self, tabs_widget, title, help_text):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel(help_text))
        
        table = QTableWidget(0, 2)
        table.setHorizontalHeaderLabels([self.tr("Key"), self.tr("Value")])
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        layout.addWidget(table)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton(self.tr("+ Add Row"))
        add_btn.clicked.connect(lambda: self._add_row(table))
        del_btn = QPushButton(self.tr("- Remove Selected"))
        del_btn.clicked.connect(lambda: self._remove_row(table))
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(del_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        tabs_widget.addTab(tab, title)
        return table

    def _add_row(self, table, key="", value=""):
        row = table.rowCount()
        table.insertRow(row)
        table.setItem(row, 0, QTableWidgetItem(str(key)))
        table.setItem(row, 1, QTableWidgetItem(str(value)))

    def _remove_row(self, table):
        for item in table.selectedItems():
            table.removeRow(item.row())

    def _get_table_data(self, table):
        data = {}
        for row in range(table.rowCount()):
            k_item = table.item(row, 0)
            v_item = table.item(row, 1)
            if k_item and k_item.text().strip():
                data[k_item.text().strip()] = v_item.text().strip() if v_item else ""
        return data

    def _get_ui_state(self):
        return {
            "url": self.url_edit.text().strip(),
            "response_type": self.format_combo.currentText(),
            "variables": self._get_table_data(self.vars_table),
            "headers": self._get_table_data(self.headers_table),
            "data": self._get_table_data(self.data_table),
            "async": {
                "enabled": self.async_cb.isChecked(),
                "job_id_key": self.poll_job_id_key.text().strip(),
                "poll_url": self.poll_url.text().strip(),
                "status_key": self.poll_status_key.text().strip(),
                "ready_val": self.poll_ready_val.text().strip(),
                "fail_val": self.poll_fail_val.text().strip(),
                "result_key": self.poll_result_key.text().strip(),
                "interval": self.poll_interval.text().strip()
            }
        }

    def load_profile_to_ui(self, name):
        if name not in self.profiles: return
        
        self.current_profile_name = name
        
        data = self.profiles[name]
        
        self.url_edit.setText(data.get("url", ""))
        idx = self.format_combo.findText(data.get("response_type", ""))
        if idx >= 0: self.format_combo.setCurrentIndex(idx)
        
        for table, key in [(self.vars_table, "variables"), (self.headers_table, "headers"), (self.data_table, "data")]:
            table.setRowCount(0)
            for k, v in data.get(key, {}).items():
                self._add_row(table, k, v)

        async_cfg = data.get("async", {})
        self.async_cb.setChecked(async_cfg.get("enabled", False))
        self.poll_job_id_key.setText(async_cfg.get("job_id_key", "id"))
        self.poll_url.setText(async_cfg.get("poll_url", ""))
        self.poll_status_key.setText(async_cfg.get("status_key", "status"))
        self.poll_ready_val.setText(async_cfg.get("ready_val", "completed"))
        self.poll_fail_val.setText(async_cfg.get("fail_val", "failed"))
        self.poll_result_key.setText(async_cfg.get("result_key", ""))
        self.poll_interval.setText(str(async_cfg.get("interval", "5")))


    def delete_profile(self):
        target_profile = self.profile_combo.currentText()
        
        if len(self.profiles) <= 1:
            QMessageBox.warning(self, self.tr("Cannot Delete"), self.tr("You must have at least one profile."))
            return
        
        if target_profile in self.profiles:
            del self.profiles[target_profile]
            
        self.current_profile_name = list(self.profiles.keys())[0]
        
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItems(list(self.profiles.keys()))
        self.profile_combo.setCurrentText(self.current_profile_name)
        self.profile_combo.blockSignals(False)
        
        self.load_profile_to_ui(self.current_profile_name)
        self._save_profiles_to_settings()

    def save_current_profile(self):
        self.profiles[self.current_profile_name] = self._get_ui_state()
        self._save_profiles_to_settings()

    def save_as_profile(self):
        name, ok = QInputDialog.getText(self, self.tr("Save Profile As"), self.tr("Profile Name:"))
        if ok and name.strip():
            name = name.strip()
            self.profiles[name] = self._get_ui_state()
            self.current_profile_name = name
            
            self.profile_combo.blockSignals(True)
            self.profile_combo.clear()
            self.profile_combo.addItems(list(self.profiles.keys()))
            self.profile_combo.setCurrentText(name)
            self.profile_combo.blockSignals(False)
            
            self._save_profiles_to_settings()

    def accept(self):
        self.save_current_profile()
        super().accept()
