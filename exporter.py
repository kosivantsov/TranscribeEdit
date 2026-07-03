# exporter.py
import re
import html as html_module
from html.parser import HTMLParser
import markdown
from utils import format_srt_time, seconds_to_ts

DEFAULT_MD_TEMPLATE = "${timestamp_start} - ${timestamp_end} ${speaker}\\n${text}"
DEFAULT_HTML_TEMPLATE = "<b>${speaker}</b> [${timestamp_start}]<br>${text}"

class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.fed = []
    def handle_data(self, d):
        self.fed.append(d)
    def get_data(self):
        return ''.join(self.fed)

def strip_markdown(text: str) -> str:
    # Convert markdown to HTML, then strip HTML tags for pure plain text
    html = markdown.markdown(text)
    s = MLStripper()
    s.feed(html)
    return s.get_data()

def md_to_html(text: str) -> str:
    html = markdown.markdown(text)
    # Remove the wrapping <p> tag that markdown injects so it fits seamlessly into our template
    if html.startswith('<p>') and html.endswith('</p>'):
        html = html[3:-4]
    return html

def _vtt_time(sec: float) -> str:
    sec = max(0.0, float(sec))
    h = int(sec // 3600); m = int((sec % 3600) // 60); s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    if ms >= 1000: ms = 999
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

def _ttml_time(sec: float) -> str:
    h = int(sec // 3600); m = int((sec % 3600) // 60); s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

def _ass_time(sec: float) -> str:
    sec = max(0.0, float(sec))
    h = int(sec // 3600); m = int((sec % 3600) // 60); s = int(sec % 60)
    cs = int(round((sec - int(sec)) * 100))
    if cs >= 100: cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

def _build_text(seg: dict, converter=None) -> str:
    text = seg.get('text', '').strip()
    if converter: text = converter(text)
    speaker = seg.get('speaker', '')
    return f"[{speaker}] {text}" if speaker else text

def to_srt(segments: list, opts: dict) -> str:
    parts = []
    for i, seg in enumerate([s for s in segments if s.get('start') is not None], 1):
        text = _build_text(seg, strip_markdown)
        if not text: continue
        parts.extend([str(i), f"{format_srt_time(seg['start'])} --> {format_srt_time(seg.get('end', seg['start']))}", text, ""])
    return '\n'.join(parts)

def to_vtt(segments: list, opts: dict) -> str:
    parts = ["WEBVTT", ""]
    for seg in [s for s in segments if s.get('start') is not None]:
        text = _build_text(seg, strip_markdown) # Plain text for VTT for safety
        if not text: continue
        parts.extend([f"{_vtt_time(seg['start'])} --> {_vtt_time(seg.get('end', seg['start']))}", text, ""])
    return '\n'.join(parts)

_ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 384
PlayResY: 288

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,16,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

def to_ass(segments: list, opts: dict) -> str:
    lines = [_ASS_HEADER]
    for seg in [s for s in segments if s.get('start') is not None]:
        text = _build_text(seg, strip_markdown).replace('\n', r'\N')
        if not text: continue
        lines.append(f"Dialogue: 0,{_ass_time(seg['start'])},{_ass_time(seg.get('end', seg['start']))},Default,,0,0,0,,{text}")
    return '\n'.join(lines)

def to_ttml(segments: list, opts: dict) -> str:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<tt xml:lang="und" xmlns="http://www.w3.org/ns/ttml">', '<body><div>']
    for seg in [s for s in segments if s.get('start') is not None]:
        text = html_module.escape(_build_text(seg, strip_markdown))
        if not text: continue
        lines.append(f'  <p begin="{_ttml_time(seg["start"])}" end="{_ttml_time(seg.get("end", seg["start"]))}">{text}</p>')
    lines.extend(['</div></body></tt>'])
    return '\n'.join(lines)

def _apply_format_string(template: str, seg: dict, is_html: bool) -> str:
    s = seg.get('start'); e = seg.get('end')
    ts_start = f"[{seconds_to_ts(s)}]" if s is not None else ""
    ts_end = f"[{seconds_to_ts(e)}]" if e is not None else ""
    spk = seg.get('speaker', '')
    
    # Process text: convert to HTML if requested
    text = seg.get('text', '').strip()
    if is_html:
        text = md_to_html(text)

    # Insert into the user-defined template (template itself is NOT escaped, so custom HTML tags remain intact)
    res = template.replace('${timestamp_start}', ts_start).replace('${timestamp_end}', ts_end)
    res = res.replace('${speaker}', spk).replace('${text}', text)
    
    # Process escapes
    res = res.replace(r'\n', '\n').replace(r'\t', '\t')
    
    # Clean up empty tags if user omitted variables and it left artifacts (like empty brackets)
    res = res.replace('[]', '').replace('()', '').strip()
    return res

def to_md(segments: list, opts: dict) -> str:
    tpl = opts.get('md_format_string') or DEFAULT_MD_TEMPLATE
    parts = []
    for seg in segments:
        if not seg.get('text', '').strip(): continue
        parts.extend([_apply_format_string(tpl, seg, is_html=False), ""])
    return '\n'.join(parts)

def to_html(segments: list, opts: dict) -> str:
    tpl = opts.get('html_format_string') or DEFAULT_HTML_TEMPLATE
    parts = ["<!DOCTYPE html><html><body>"]
    for seg in segments:
        if not seg.get('text', '').strip(): continue
        parts.append(f"<p>{_apply_format_string(tpl, seg, is_html=True)}</p>")
    parts.append("</body></html>")
    return '\n'.join(parts)

FORMATS = {
    'srt':  (to_srt,  "SRT Files (*.srt)"),
    'vtt':  (to_vtt,  "WebVTT Files (*.vtt)"),
    'ass':  (to_ass,  "ASS/SSA Files (*.ass)"),
    'ttml': (to_ttml, "TTML Files (*.ttml)"),
    'md':   (to_md,   "Markdown Files (*.md)"),
    'html': (to_html, "HTML Files (*.html)"),
}

def export(segments: list, fmt: str, opts: dict) -> str:
    return FORMATS[fmt][0](segments, opts)

def get_filter(fmt: str) -> str:
    return FORMATS[fmt][1]
