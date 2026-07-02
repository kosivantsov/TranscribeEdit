import os
import json
import threading
import time
import requests
from PyQt5.QtCore import QObject, pyqtSignal

class CloudWorkerSignals(QObject):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

class CloudWorker(threading.Thread):
    def __init__(self, config, audio_path, duration, signals):
        super().__init__(daemon=True)
        self.config = config
        self.audio_path = audio_path
        self.duration = duration
        self.signals = signals
        self.is_cancelled = False  # Cancellation flag

    def cancel(self):
        self.is_cancelled = True

    def _resolve_vars(self, text, variables):
        if not isinstance(text, str): 
            return text
        for k, v in variables.items():
            text = text.replace(f"${{{k}}}", str(v))
        return text

    def _extract_json_path(self, data, path):
        if not path: return data
        for part in path.split('.'):
            if isinstance(data, dict) and part in data:
                data = data[part]
            else:
                return None
        return data

    def run(self):
        variables = self.config.get("variables", {}).copy()
        variables["FILE"] = self.audio_path
        
        raw_url = self.config.get("url")
        if not raw_url:
            self.signals.error.emit("API Endpoint URL is missing.")
            return
        url = self._resolve_vars(raw_url, variables)

        headers = {}
        for k, v in self.config.get("headers", {}).items():
            headers[self._resolve_vars(k, variables)] = self._resolve_vars(v, variables)

        data = {}
        file_field_name = 'file'
        for k, v in self.config.get("data", {}).items():
            resolved_k = self._resolve_vars(k, variables)
            if v == "${FILE}":
                file_field_name = resolved_k
            else:
                data[resolved_k] = self._resolve_vars(v, variables)
            
        try:
            self.signals.progress.emit(10, "Uploading audio...")
            
            with open(self.audio_path, 'rb') as f:
                files = {file_field_name: (os.path.basename(self.audio_path), f)}
                response = requests.post(url, headers=headers, data=data, files=files, timeout=300)

            if self.is_cancelled: return  # Check if cancelled during upload

            if response.status_code not in [200, 201, 202]:
                self.signals.error.emit(f"Server Error {response.status_code}:\n{response.text}")
                return

            async_cfg = self.config.get("async", {})
            final_data = None
            
            # --- TWO-STEP POLLING WORKFLOW ---
            if async_cfg.get("enabled"):
                resp_json = response.json()
                job_id = self._extract_json_path(resp_json, async_cfg.get("job_id_key", "id"))
                
                if not job_id:
                    self.signals.error.emit(f"Could not find Job ID key '{async_cfg.get('job_id_key')}' in response:\n{response.text}")
                    return
                
                variables["JOB_ID"] = str(job_id)
                poll_url_template = async_cfg.get("poll_url", "")
                interval = int(async_cfg.get("interval", 5))
                ready_val = async_cfg.get("ready_val", "completed").lower()
                fail_val = async_cfg.get("fail_val", "failed").lower()
                status_key = async_cfg.get("status_key", "status")

                while True:
                    if self.is_cancelled: return  # Abort loop

                    poll_url = self._resolve_vars(poll_url_template, variables)
                    poll_resp = requests.get(poll_url, headers=headers, timeout=60)
                    
                    if poll_resp.status_code != 200:
                        self.signals.error.emit(f"Polling Error {poll_resp.status_code}:\n{poll_resp.text}")
                        return
                    
                    poll_json = poll_resp.json()
                    status = str(self._extract_json_path(poll_json, status_key) or "unknown")
                    
                    self.signals.progress.emit(50, f"Polling... Status: {status}")
                    
                    if status.lower() == ready_val:
                        result_key = async_cfg.get("result_key", "")
                        final_data = self._extract_json_path(poll_json, result_key) if result_key else poll_json
                        break
                    
                    # --- NEW: Check for API Fail Value ---
                    elif fail_val and status.lower() == fail_val:
                        self.signals.error.emit(f"API processing failed. Job status: {status}")
                        return
                        
                    # Custom sleep loop so we can abort instantly if cancelled
                    for _ in range(interval * 10):
                        if self.is_cancelled: return
                        time.sleep(0.1)
            
            # --- SINGLE-STEP WORKFLOW ---
            else:
                self.signals.progress.emit(90, "Processing response...")
                try:
                    final_data = response.json()
                except ValueError:
                    final_data = response.text

            if self.is_cancelled: return

            # --- PARSE THE FINAL OUTPUT ---
            response_type = self.config.get("response_type", "json (OpenAI/Lemonfox)")
            segs = []

            if "json" in response_type.lower():
                if isinstance(final_data, dict):
                    if "segments" in final_data:
                        segs = final_data["segments"]
                    elif "text" in final_data:
                        segs = [{"start": 0.0, "end": self.duration, "text": final_data["text"], "speaker": "SPEAKER_00"}]
                    else:
                        self.signals.error.emit(f"Unexpected JSON format returned:\n{str(final_data)[:200]}")
                        return
                else:
                    self.signals.error.emit(f"Expected JSON object but got:\n{str(final_data)[:200]}")
                    return

            elif response_type in ["text", "srt", "vtt"]:
                if isinstance(final_data, dict):
                    text_content = final_data.get("text", str(final_data))
                else:
                    text_content = str(final_data).strip()
                    
                segs = [{"start": 0.0, "end": self.duration, "text": text_content, "speaker": "SPEAKER_00"}]

            self.signals.progress.emit(100, "Done")
            self.signals.finished.emit(segs)

        except requests.exceptions.Timeout:
            if not self.is_cancelled: self.signals.error.emit("The API request timed out.")
        except requests.exceptions.RequestException as e:
            if not self.is_cancelled: self.signals.error.emit(f"Network error connecting to API: {str(e)}")
        except Exception as e:
            if not self.is_cancelled: self.signals.error.emit(f"An unexpected error occurred: {str(e)}")
