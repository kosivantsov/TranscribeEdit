import re
from PyQt5.QtWidgets import QTextEdit, QMessageBox
from PyQt5.QtGui import QFont, QTextCursor, QColor, QTextCharFormat, QTextFormat, QSyntaxHighlighter
from PyQt5.QtCore import pyqtSignal
from utils import TIMESTAMP_RE, ts_to_seconds, seconds_to_ts, format_srt_time

class TranscriptHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.ts_format = QTextCharFormat()
        self.spk_format = QTextCharFormat()
        self.ts_pattern = TIMESTAMP_RE
        self.spk_pattern = re.compile(r'<<[^>]+>>')

    def update_formats(self, ts_fg, ts_bg, spk_fg, spk_bg):
        self.ts_format = QTextCharFormat()
        if ts_fg: self.ts_format.setForeground(QColor(ts_fg))
        if ts_bg: self.ts_format.setBackground(QColor(ts_bg))
        
        self.spk_format = QTextCharFormat()
        if spk_fg: self.spk_format.setForeground(QColor(spk_fg))
        if spk_bg: self.spk_format.setBackground(QColor(spk_bg))
        
        self.rehighlight()

    def highlightBlock(self, text):
        for m in self.ts_pattern.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self.ts_format)
        for m in self.spk_pattern.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self.spk_format)


class TranscriptEditor(QTextEdit):
    jump_requested = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFont("Courier New")
        font.setStyleHint(QFont.TypeWriter)
        font.setPointSize(10)
        self.setFont(font)
        self.setLineWrapMode(QTextEdit.WidgetWidth)
        self.setAcceptRichText(False)
        self.setPlaceholderText(self.tr("Type transcription here...\nCtrl+T inserts the current audio timestamp.\nF5 jumps to the timestamp currently under your cursor."))
        
        self.highlighter = TranscriptHighlighter(self.document())

    def _timestamp_at_cursor(self):
        cursor = self.textCursor()
        block_text = cursor.block().text()
        col = cursor.positionInBlock()
        for m in TIMESTAMP_RE.finditer(block_text):
            if m.start() <= col <= m.end():
                ts = f"{m.group(1)}:{m.group(2)}:{m.group(3)}.{m.group(4)}"
                return ts_to_seconds(ts)
        return None

    def jump_to_timestamp_at_cursor(self):
        sec = self._timestamp_at_cursor()
        if sec is not None:
            self.jump_requested.emit(sec)
            return True
        return False

    def highlight_closest_timestamp(self, current_seconds):
        text = self.toPlainText()
        matches = list(TIMESTAMP_RE.finditer(text))
        if not matches:
            return

        closest_match = None
        min_diff = float('inf')

        for m in matches:
            ts_str = f"{m.group(1)}:{m.group(2)}:{m.group(3)}.{m.group(4)}"
            sec = ts_to_seconds(ts_str)
            diff = abs(sec - current_seconds)
            if diff < min_diff:
                min_diff = diff
                closest_match = m

        if closest_match:
            temp_cursor = QTextCursor(self.document())
            temp_cursor.setPosition(closest_match.start())
            temp_cursor.select(QTextCursor.LineUnderCursor)

            selection = QTextEdit.ExtraSelection()
            format = QTextCharFormat()
            format.setBackground(QColor(200, 200, 0, 100))
            format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.format = format
            selection.cursor = temp_cursor

            self.setExtraSelections([selection])

            block = temp_cursor.block()
            y_pos = self.document().documentLayout().blockBoundingRect(block).top()
            viewport_height = self.viewport().height()
            
            scrollbar = self.verticalScrollBar()
            target_y = int(y_pos - viewport_height / 2 + 10)
            target_y = max(scrollbar.minimum(), min(target_y, scrollbar.maximum()))
            scrollbar.setValue(target_y)
            
    def clear_highlight(self):
        self.setExtraSelections([])

    def insert_timestamp(self, seconds, parent_widget=None):
        ts_str = f"[{seconds_to_ts(seconds)}]"
        cursor = self.textCursor()
        
        text_before = self.toPlainText()[:cursor.position()]
        matches = list(TIMESTAMP_RE.finditer(text_before))
        
        if matches:
            last_match = matches[-1]
            last_ts_str = f"[{last_match.group(1)}:{last_match.group(2)}:{last_match.group(3)}.{last_match.group(4)}]"
            last_sec = ts_to_seconds(last_ts_str.strip('[]'))
            
            if last_sec > seconds:
                if parent_widget:
                    ans = QMessageBox.question(parent_widget, self.tr("Warning"), 
                        self.tr("Inserted timestamp ({0}) is earlier than the previous one ({1}).\nContinue?").format(ts_str, last_ts_str),
                        QMessageBox.Yes | QMessageBox.No)
                    if ans != QMessageBox.Yes:
                        return
                        
        cursor.select(QTextCursor.LineUnderCursor)
        line_text = cursor.selectedText()
        
        if re.fullmatch(r'^\s*\[\d{2}:\d{2}:\d{2}\.\d{2}\]\s*$', line_text):
            existing_ts = line_text.strip()
            cursor.insertText(f"{existing_ts} {ts_str}")
        else:
            cursor.clearSelection()
            cursor.movePosition(QTextCursor.EndOfLine)
            cursor.insertText(f"\n{ts_str} ")
            
        self.setTextCursor(cursor)

    def insert_or_cycle_speaker(self, speakers):
        if not speakers: return
        cursor = self.textCursor()
        cursor.select(QTextCursor.LineUnderCursor)
        line_text = cursor.selectedText().strip()
        
        tagged_speakers = [f"<<{s}>>" for s in speakers if s]
        if not tagged_speakers: return
        
        if not line_text:
            cursor.insertText(tagged_speakers[0])
        elif line_text in tagged_speakers:
            idx = tagged_speakers.index(line_text)
            next_idx = (idx + 1) % len(tagged_speakers)
            cursor.insertText(tagged_speakers[next_idx])
        else:
            cursor.clearSelection()
            cursor.movePosition(QTextCursor.EndOfLine)
            cursor.insertText(f"\n{tagged_speakers[0]}")
            
        self.setTextCursor(cursor)

    def load_segments(self, segments):
        lines = []
        for seg in segments:
            text = seg.get('text', '').strip()
            
            if 'start' in seg and 'end' in seg:
                start = float(seg['start'])
                end = float(seg['end'])
                ts_start = f"[{seconds_to_ts(start)}]"
                ts_end = f"[{seconds_to_ts(end)}]"
                lines.append(f"{ts_start} {ts_end}")
                
            speaker = seg.get('speaker', '')
            if speaker:
                lines.append(f"<<{speaker}>>")
                
            lines.append(text)
            lines.append("")
            
        self.setPlainText('\n'.join(lines))
        self.document().setModified(False)

    def to_segments(self):
        seg_re = re.compile(r'^\[(\d+:\d{2}:\d{2}\.\d{2})\]\s*(?:\[(\d+:\d{2}:\d{2}\.\d{2})\])?')
        speaker_re = re.compile(r'^<<([^>]+)>>\s*(.*)$')
        
        segments = []
        current_seg = None
        
        for line in self.toPlainText().splitlines():
            line_stripped = line.strip()
            
            if not line_stripped:
                if current_seg:
                    current_seg['text'] = current_seg['text'].strip()
                    if current_seg['text'] or 'start' in current_seg:
                        segments.append(current_seg)
                    current_seg = None
                continue
                
            m = seg_re.match(line_stripped)
            if m: 
                if current_seg:
                    current_seg['text'] = current_seg['text'].strip()
                    if current_seg['text'] or 'start' in current_seg:
                        segments.append(current_seg)
                    
                start_s = ts_to_seconds(m.group(1))
                end_s = ts_to_seconds(m.group(2)) if m.group(2) else start_s
                
                current_seg = {
                    'start': round(start_s, 3),
                    'end': round(end_s, 3),
                    'text': ''
                }
            else:
                if current_seg is None:
                    current_seg = {
                        'text': ''
                    }
                    
                if not current_seg['text'] and not current_seg.get('speaker'):
                    sm = speaker_re.match(line_stripped)
                    if sm:
                        current_seg['speaker'] = sm.group(1)
                        current_seg['text'] += sm.group(2) + " "
                        continue
                
                current_seg['text'] += line_stripped + " "
                
        if current_seg:
            current_seg['text'] = current_seg['text'].strip()
            if current_seg['text'] or 'start' in current_seg:
                segments.append(current_seg)
            
        for seg in segments:
            if 'start' in seg and 'end' in seg:
                start_s = seg['start']
                end_s = seg['end']
                h_s, m_s = divmod(int(start_s // 60), 60)
                h_e, m_e = divmod(int(end_s // 60), 60)
                seg['timestamp'] = f"{m_s:02d}:{int(start_s%60):02d} - {m_e:02d}:{int(end_s%60):02d}"
            
        return segments

    def to_srt(self):
        parts = []
        for i, seg in enumerate(self.to_segments(), 1):
            start_s = seg.get('start', 0)
            end_s = seg.get('end', 0)
            parts.append(f"{i}\n{format_srt_time(start_s)} --> {format_srt_time(end_s)}")
            parts.append(f"[{seg['speaker']}] {seg['text']}" if seg.get('speaker') else seg['text'])
            parts.append("")
        return '\n'.join(parts)
