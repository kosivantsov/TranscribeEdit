import os
import json
import subprocess
import threading
import tempfile
from PyQt5.QtCore import QObject, pyqtSignal

class CliTranscribeSignals(QObject):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

class CliTranscribeWorker(threading.Thread):
    def __init__(self, bin_path, audio_path, duration, model, device, signals):
        super().__init__(daemon=True)
        self.bin_path = bin_path
        self.audio_path = audio_path
        self.duration = duration
        self.model = model
        self.device = device
        self.signals = signals
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        temp_wav = None
        try:
            self.signals.progress.emit(10, "Converting audio to 16kHz WAV format for CLI...")
            
            # 1. Convert to 16kHz Mono WAV using ffmpeg
            temp_wav = os.path.join(tempfile.gettempdir(), "cli_transcribe_tmp.wav")
            if os.path.exists(temp_wav):
                try: os.remove(temp_wav)
                except Exception: pass
            
            ffmpeg_cmd = [
                "ffmpeg", "-y", "-i", str(self.audio_path), 
                "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", 
                str(temp_wav)
            ]
            
            # Run ffmpeg silently
            if self._is_cancelled: return
            subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            self.signals.progress.emit(30, "Starting Handy Tool...")

            # 2. Build command dynamically to avoid empty string arguments
            cmd = [self.bin_path]
            
            if self.model:
                cmd.extend(["--model", self.model])
                
            if self.device:
                cmd.extend(["--device-index", self.device])
                
            # Pass the temporary WAV file we just created, not the original m4a
            cmd.extend(["-f", temp_wav, "--json"])

            print(f"DEBUG Executing: {' '.join(cmd)}")
            
            # 3. Start the Handy process
            if self._is_cancelled: return
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Combines stderr into stdout
                text=True,
                encoding='utf-8',
                errors='replace'
            )

            # 4. Read stdout line by line
            for line in iter(proc.stdout.readline, ''):
                if self._is_cancelled:
                    proc.kill()
                    return
                
                line = line.strip()
                if not line: continue

                print(f"CLI: {line}")

                # Try to parse JSON for progress and segments
                try:
                    data = json.loads(line)
                    
                    if "progress" in data:
                        pct_val = data["progress"]
                        pct = int(pct_val * 100) if pct_val <= 1.0 else int(pct_val)
                        
                        # Scale progress between 30% and 99% for UI
                        ui_pct = 30 + int((pct / 100) * 69)
                        self.signals.progress.emit(ui_pct, f"Transcribing... {pct}%")
                        
                    elif "segments" in data or "text" in data:
                        self.signals.progress.emit(100, "Done.")
                        
                        # If the model provides word/sentence segments, use them
                        if "segments" in data:
                            segs = data["segments"]
                        else:
                            # If the model only provides a raw text dump, wrap it in a single segment
                            full_text = data.get("text", "").strip()
                            audio_len = data.get("audio_secs", self.duration)
                            
                            if full_text:
                                segs = [{"start": 0.0, "end": audio_len, "text": full_text, "speaker": "SPEAKER_00"}]
                            else:
                                segs = []
                                
                        self.signals.finished.emit(segs)
                        proc.stdout.close()
                        proc.wait()
                        return
                        
                except json.JSONDecodeError:
                    pass

            proc.stdout.close()
            proc.wait()

            if proc.returncode != 0:
                self.signals.error.emit(f"Handy tool exited with code {proc.returncode}")
            else:
                self.signals.error.emit("Tool finished but returned no transcription data.")

        except Exception as e:
            if not self._is_cancelled:
                self.signals.error.emit(str(e))
        finally:
            # 5. Clean up the temporary WAV file
            if temp_wav and os.path.exists(temp_wav):
                try: os.remove(temp_wav)
                except Exception: pass
