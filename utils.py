import re

TIMESTAMP_RE = re.compile(r'\[(\d{2}):(\d{2}):(\d{2})\.(\d{2})\]')

def seconds_to_ts(sec):
    sec = max(0.0, float(sec))
    h   = int(sec // 3600)
    m   = int((sec % 3600) // 60)
    s   = int(sec % 60)
    cs  = int(round((sec - int(sec)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h:02d}:{m:02d}:{s:02d}.{cs:02d}"

def ts_to_seconds(ts_str):
    m = re.fullmatch(r'(\d+):(\d{2}):(\d{2})\.(\d{2})', ts_str)
    if not m:
        return None
    h, mi, s, cs = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
    return h * 3600 + mi * 60 + s + cs / 100.0

def format_srt_time(sec):
    sec = max(0.0, float(sec))
    h   = int(sec // 3600)
    m   = int((sec % 3600) // 60)
    s   = int(sec % 60)
    ms  = int(round((sec - int(sec)) * 1000))
    if ms >= 1000:
        ms = 999
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
