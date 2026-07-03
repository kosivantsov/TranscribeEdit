# utils.py
import re

# We now use ⟦ (U+27E6) and ⟧ (U+27E7) for timestamps!
TIMESTAMP_RE = re.compile(r'⟦(\d{2,}):(\d{2}):(\d{2})\.(\d{2,3})⟧')

def ts_to_seconds(ts):
    h, m, s = ts.split(':')
    s, ms = s.split('.')
    return int(h) * 3600 + int(m) * 60 + int(s) + float(f"0.{ms}")

def seconds_to_ts(sec):
    sec = max(0.0, float(sec))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 100))
    if ms >= 100: ms = 99
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:02d}"

def format_srt_time(sec):
    sec = max(0.0, float(sec))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    if ms >= 1000: ms = 999
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
