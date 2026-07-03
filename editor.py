# editor.py
import re
from PyQt5.QtWidgets import QPlainTextEdit, QTextEdit, QMessageBox, QWidget
from PyQt5.QtGui import (
    QFont, QTextCursor, QColor, QTextCharFormat,
    QTextFormat, QSyntaxHighlighter, QPainter, QPen
)
from PyQt5.QtCore import pyqtSignal, Qt, QRect, QSize

from utils import TIMESTAMP_RE, ts_to_seconds, seconds_to_ts


class TranscriptHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)

        self.ts_format = QTextCharFormat()
        self.spk_format = QTextCharFormat()

        self._markup_fmt = QTextCharFormat()
        self._markup_fmt.setForeground(QColor(120, 120, 120))

        self._bold_fmt = QTextCharFormat()
        self._bold_fmt.setFontWeight(QFont.Bold)

        self._italic_fmt = QTextCharFormat()
        self._italic_fmt.setFontItalic(True)

        self._strike_fmt = QTextCharFormat()
        self._strike_fmt.setFontStrikeOut(True)

        self._code_fmt = QTextCharFormat()
        self._code_fmt.setFontFamily("Courier New")
        self._code_fmt.setBackground(QColor(60, 60, 60, 120))

        self._quote_fmt = QTextCharFormat()
        self._quote_fmt.setForeground(QColor(150, 180, 150))
        self._quote_fmt.setFontItalic(True)

        self._link_fmt = QTextCharFormat()
        self._link_fmt.setForeground(QColor(80, 180, 250))
        self._link_fmt.setFontUnderline(True)

        self._underline_fmt = QTextCharFormat()
        self._underline_fmt.setFontUnderline(True)

        self._heading_fmt = QTextCharFormat()
        self._heading_fmt.setFontWeight(QFont.Bold)

        self._hr_fmt = QTextCharFormat()
        self._hr_fmt.setFontStrikeOut(True)
        self.hr_color = QColor(136, 136, 136)

        self._list_bg_fmt = QTextCharFormat()
        self._list_marker_fmt = QTextCharFormat()

        self.ts_pattern = TIMESTAMP_RE
        self.spk_pattern = re.compile(r'⟪[^⟫]+⟫')

    # ------------------------------------------------------------------
    # Helper: merge src format properties into the already-set format at
    # [pos, pos+length) without erasing properties set by earlier passes.
    # ------------------------------------------------------------------
    def _merge_format(self, pos, length, src_fmt):
        if length <= 0:
            return
        existing = self.format(pos)
        existing.merge(src_fmt)
        self.setFormat(pos, length, existing)

    def update_formats(self, colors):
        # --- Timestamp ---
        self.ts_format = QTextCharFormat()
        if colors.get("ts_fg"):
            self.ts_format.setForeground(QColor(colors["ts_fg"]))
        if colors.get("ts_bg"):
            self.ts_format.setBackground(QColor(colors["ts_bg"]))
        if colors.get("ts_font"):
            f = QFont()
            f.fromString(colors["ts_font"])
            self.ts_format.setFont(f)

        # --- Speaker tag ---
        self.spk_format = QTextCharFormat()
        if colors.get("spk_fg"):
            self.spk_format.setForeground(QColor(colors["spk_fg"]))
        if colors.get("spk_bg"):
            self.spk_format.setBackground(QColor(colors["spk_bg"]))
        if colors.get("spk_font"):
            f = QFont()
            f.fromString(colors["spk_font"])
            self.spk_format.setFont(f)

        # --- Headings ---
        if colors.get("md_heading_fg"):
            self._heading_fmt.setForeground(QColor(colors["md_heading_fg"]))

        # --- Horizontal rule ---
        if colors.get("md_hr_fg"):
            self.hr_color = QColor(colors["md_hr_fg"])
            self._hr_fmt.setForeground(self.hr_color)

        # --- List ---
        if colors.get("md_list_bg"):
            self._list_bg_fmt.setBackground(QColor(colors["md_list_bg"]))
        if colors.get("md_list_marker_fg"):
            self._list_marker_fmt.setForeground(QColor(colors["md_list_marker_fg"]))

        # --- Markup symbols ---
        if colors.get("md_markup_fg"):
            self._markup_fmt.setForeground(QColor(colors["md_markup_fg"]))
        if colors.get("md_markup_font"):
            f = QFont()
            f.fromString(colors["md_markup_font"])
            self._markup_fmt.setFont(f)

        # --- Code span ---
        # Rebuild from scratch so clearing a value goes back to defaults.
        self._code_fmt = QTextCharFormat()
        if colors.get("md_code_font"):
            f = QFont()
            f.fromString(colors["md_code_font"])
            self._code_fmt.setFont(f)
        else:
            self._code_fmt.setFontFamily("Courier New")
        if colors.get("md_code_bg"):
            self._code_fmt.setBackground(QColor(colors["md_code_bg"]))
        else:
            self._code_fmt.setBackground(QColor(60, 60, 60, 120))
        if colors.get("md_code_fg"):
            self._code_fmt.setForeground(QColor(colors["md_code_fg"]))

        # --- Blockquote ---
        # Preserve italic; only override foreground.
        self._quote_fmt = QTextCharFormat()
        self._quote_fmt.setFontItalic(True)
        if colors.get("md_blockquote_fg"):
            self._quote_fmt.setForeground(QColor(colors["md_blockquote_fg"]))
        else:
            self._quote_fmt.setForeground(QColor(150, 180, 150))

        self.rehighlight()

    def highlightBlock(self, text):
        block = self.currentBlock()
        next_block = block.next()
        next_text = next_block.text().strip() if next_block.isValid() else ""
        text_stripped = text.strip()

        is_heading = False
        if re.match(r'^#{1,6}\s+', text_stripped) or (
            text_stripped and re.fullmatch(r'={3,}|-{3,}', next_text)
        ):
            is_heading = True

        if is_heading:
            self.setFormat(0, len(text), self._heading_fmt)
            return

        if re.fullmatch(r'(\*{3,}|-{3,}|_{3,})', text_stripped):
            prev_block = block.previous()
            if not prev_block.isValid() or not prev_block.text().strip():
                self.setFormat(0, len(text), self._hr_fmt)
                return

        # --- List (background pass first so inline spans can merge on top) ---
        m_list = re.match(r'^(\s*)([-*+]\s+)(.*)', text)
        if m_list:
            content_start = m_list.start(2)
            content_len = len(m_list.group(2)) + len(m_list.group(3))
            self.setFormat(content_start, content_len, self._list_bg_fmt)
            self.setFormat(m_list.start(2), len(m_list.group(2)), self._list_marker_fmt)

        # --- Blockquote ---
        m = re.match(r'^(>+)\s*(.*)', text)
        if m:
            self.setFormat(m.start(1), m.end(1) - m.start(1), self._markup_fmt)
            self.setFormat(m.start(2), m.end(2) - m.start(2), self._quote_fmt)

        # --- Bold (merge so list-background is preserved) ---
        for m in re.finditer(r'(\*\*|__)(.+?)(\1)', text):
            self._merge_format(m.start(1), m.end(1) - m.start(1), self._markup_fmt)
            self._merge_format(m.start(2), m.end(2) - m.start(2), self._bold_fmt)
            self._merge_format(m.start(3), m.end(3) - m.start(3), self._markup_fmt)

        # --- Italic * (merge) ---
        for m in re.finditer(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', text):
            self._merge_format(m.start(), 1, self._markup_fmt)
            self._merge_format(m.start() + 1, m.end() - m.start() - 2, self._italic_fmt)
            self._merge_format(m.end() - 1, 1, self._markup_fmt)

        # --- Italic _ (merge) ---
        for m in re.finditer(r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)', text):
            self._merge_format(m.start(), 1, self._markup_fmt)
            self._merge_format(m.start() + 1, m.end() - m.start() - 2, self._italic_fmt)
            self._merge_format(m.end() - 1, 1, self._markup_fmt)

        # --- Strikethrough (merge) ---
        for m in re.finditer(r'(~~)(.+?)(\1)', text):
            self._merge_format(m.start(1), 2, self._markup_fmt)
            self._merge_format(m.start(2), m.end(2) - m.start(2), self._strike_fmt)
            self._merge_format(m.start(3), 2, self._markup_fmt)

        # --- Inline code (merge so bold-in-code etc. also stack) ---
        for m in re.finditer(r'(`)(.+?)(\1)', text):
            self._merge_format(m.start(1), 1, self._markup_fmt)
            self._merge_format(m.start(2), m.end(2) - m.start(2), self._code_fmt)
            self._merge_format(m.start(3), 1, self._markup_fmt)

        # --- Underline <u>...</u> (merge) ---
        for m in re.finditer(r'(<u>)(.+?)(</u>)', text):
            self._merge_format(m.start(1), 3, self._markup_fmt)
            self._merge_format(m.start(2), m.end(2) - m.start(2), self._underline_fmt)
            self._merge_format(m.start(3), 4, self._markup_fmt)

        # --- Markdown link [text](url) ---
        for m in re.finditer(r'(\[)(.*?)(\])(\()(.+?)(\))', text):
            self._merge_format(m.start(1), 1, self._markup_fmt)
            self._merge_format(m.start(2), m.end(2) - m.start(2), self._link_fmt)
            self._merge_format(m.start(3), 2, self._markup_fmt)
            self._merge_format(m.start(5), m.end(5) - m.start(5), self._markup_fmt)
            self._merge_format(m.start(6), 1, self._markup_fmt)

        # --- Auto-link <url> / <email> ---
        for m in re.finditer(r'(<)(.+?@[^>]+|[a-zA-Z]+://[^>]+)(>)', text):
            self._merge_format(m.start(1), 1, self._markup_fmt)
            self._merge_format(m.start(2), m.end(2) - m.start(2), self._link_fmt)
            self._merge_format(m.start(3), 1, self._markup_fmt)

        # --- Generic HTML tags ---
        for m in re.finditer(r'</?[a-zA-Z0-9]+[^>]*>', text):
            self._merge_format(m.start(), m.end() - m.start(), self._markup_fmt)

        # --- Timestamps (always on top) ---
        for m in self.ts_pattern.finditer(text):
            self._merge_format(m.start(), m.end() - m.start(), self.ts_format)

        # --- Speaker tags (always on top) ---
        for m in self.spk_pattern.finditer(text):
            self._merge_format(m.start(), m.end() - m.start(), self.spk_format)


class EditorMargin(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(24, 0)

    def paintEvent(self, event):
        self.editor.marginPaintEvent(event)

    def mousePressEvent(self, event):
        self.editor.margin_clicked(event.pos())

class TranscriptEditor(QPlainTextEdit):
    jump_requested = pyqtSignal(float)

    SINGLE_TS_LINE_RE = re.compile(r'^\s*⟦\d{2,}:\d{2}:\d{2}\.\d{2,3}⟧\s*$')
    DOUBLE_TS_LINE_RE = re.compile(r'^\s*⟦\d{2,}:\d{2}:\d{2}\.\d{2,3}⟧\s+⟦\d{2,}:\d{2}:\d{2}\.\d{2,3}⟧\s*$')
    SPEAKER_ONLY_RE = re.compile(r'^\s*⟪[^⟫]+⟫\s*$')
    TS_ONLY_RE = re.compile(r'^\s*⟦(\d+:\d{2}:\d{2}\.\d{2,3})⟧(?:\s*⟦(\d+:\d{2}:\d{2}\.\d{2,3})⟧)?\s*$')
    SPEAKER_RE = re.compile(r'^⟪([^⟫]+)⟫\s*(.*)$')

    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFont("Courier New")
        font.setStyleHint(QFont.TypeWriter)
        font.setPointSize(10)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.setPlaceholderText(
            self.tr(
                "Type transcription here...\n"
                "Ctrl+T inserts timestamp.\n"
                "F5 jumps to timestamp.\n"
                "Markdown supported."
            )
        )

        self.highlighter = TranscriptHighlighter(self.document())
        self.margin = EditorMargin(self)
        self.blockCountChanged.connect(self.update_margin_width)
        self.updateRequest.connect(self.update_margin)
        self.update_margin_width()

        self.find_extra_selections = []
        self.ts_extra_selections = []

    def setStyleSheet(self, sheet):
        super().setStyleSheet(sheet.replace("QTextEdit", "QPlainTextEdit"))

    def paintEvent(self, e):
        super().paintEvent(e)
        painter = QPainter(self.viewport())
        painter.setPen(QPen(self.highlighter.hr_color, 1, Qt.SolidLine))

        block = self.firstVisibleBlock()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())

        while block.isValid() and top <= e.rect().bottom():
            bottom = top + int(self.blockBoundingRect(block).height())
            if block.isVisible() and bottom >= e.rect().top():
                text_stripped = block.text().strip()
                if re.fullmatch(r'(\*{3,}|-{3,}|_{3,})', text_stripped):
                    prev = block.previous()
                    if not prev.isValid() or not prev.text().strip():
                        fm = self.fontMetrics()
                        try:
                            strike_y = top + fm.ascent() - fm.strikeOutPos()
                        except AttributeError:
                            strike_y = top + fm.height() // 2
                        painter.drawLine(0, strike_y, self.viewport().width(), strike_y)
            block = block.next()
            top = bottom

    def toggle_format(self, tag_open, tag_close=None):
        if not tag_close:
            tag_close = tag_open

        cursor = self.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.WordUnderCursor)

        text = cursor.selectedText()
        if not text:
            return

        len_o, len_c = len(tag_open), len(tag_close)
        pos = cursor.position()
        anchor = cursor.anchor()
        start, end = min(pos, anchor), max(pos, anchor)

        cursor.beginEditBlock()

        if text.startswith(tag_open) and text.endswith(tag_close) and len(text) >= len_o + len_c:
            cursor.insertText(text[len_o:-len_c])
            new_start = start
            new_pos = new_start + (pos - start) - (len_o if pos > start else 0)
            new_anchor = new_start + (anchor - start) - (len_o if anchor > start else 0)
        else:
            cursor.setPosition(start)
            cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, len_o)
            left_text = cursor.selectedText()

            cursor.setPosition(end)
            cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, len_c)
            right_text = cursor.selectedText()

            if left_text == tag_open and right_text == tag_close:
                cursor.setPosition(start - len_o)
                cursor.setPosition(end + len_c, QTextCursor.KeepAnchor)
                cursor.insertText(text)
                new_pos = pos - len_o
                new_anchor = anchor - len_o
            else:
                cursor.setPosition(start)
                cursor.setPosition(end, QTextCursor.KeepAnchor)
                cursor.insertText(f"{tag_open}{text}{tag_close}")
                new_pos = pos + len_o if pos > start else pos
                new_anchor = anchor + len_o if anchor > start else anchor

        rc = self.textCursor()
        rc.setPosition(new_anchor)
        rc.setPosition(new_pos, QTextCursor.KeepAnchor)
        self.setTextCursor(rc)
        cursor.endEditBlock()

    def format_bold(self):
        self.toggle_format("**")

    def format_italic(self):
        self.toggle_format("_")

    def highlight_find_result(self):
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return

        selection = QTextEdit.ExtraSelection()
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(255, 150, 0, 180))
        fmt.setForeground(QColor(0, 0, 0))
        selection.format = fmt
        selection.cursor = cursor

        self.find_extra_selections = [selection]
        self._apply_all_extra_selections()

    def update_margin_width(self, blockCount=0):
        self.setViewportMargins(self.margin.sizeHint().width(), 0, 0, 0)

    def update_margin(self, rect, dy):
        if dy:
            self.margin.scroll(0, dy)
        else:
            self.margin.update(0, rect.y(), self.margin.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_margin_width()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        cr = self.contentsRect()
        self.margin.setGeometry(QRect(cr.left(), cr.top(), self.margin.sizeHint().width(), cr.height()))

    def is_unit_start(self, block):
        if not block.isValid():
            return False
        if block.blockNumber() == 0:
            return True
        prev = block.previous()
        if prev.isValid() and not prev.text().strip():
            if block.text().strip():
                return True
        if TIMESTAMP_RE.match(block.text().strip()):
            return True
        return False

    def unit_has_content(self, block):
        curr = block.next()
        while curr.isValid():
            if self.is_unit_start(curr):
                break
            if curr.text().strip():
                return True
            curr = curr.next()
        return False

    def is_unit_folded(self, block):
        curr = block.next()
        while curr.isValid():
            if self.is_unit_start(curr):
                break
            if curr.text().strip():
                return not curr.isVisible()
            curr = curr.next()
        return False

    def toggle_fold_current(self):
        block = self.textCursor().block()
        while block.isValid() and not self.is_unit_start(block):
            block = block.previous()
        if block.isValid() and self.unit_has_content(block):
            self.toggle_fold(block)

    def margin_clicked(self, pos):
        block = self.firstVisibleBlock()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid():
            if top <= pos.y() <= bottom:
                if self.is_unit_start(block) and self.unit_has_content(block):
                    self.toggle_fold(block)
                break
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())

    def toggle_fold(self, block):
        is_folded = self.is_unit_folded(block)
        curr = block.next()
        while curr.isValid() and not self.is_unit_start(curr):
            curr.setVisible(is_folded)
            curr = curr.next()

        end_pos = curr.position() if curr.isValid() else self.document().characterCount()
        self.document().markContentsDirty(block.position(), end_pos - block.position())
        self.viewport().update()
        self.margin.update()

    def marginPaintEvent(self, event):
        painter = QPainter(self.margin)
        painter.fillRect(event.rect(), QColor(35, 35, 35))
        block = self.firstVisibleBlock()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        line_h = self.fontMetrics().height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                if self.is_unit_start(block) and self.unit_has_content(block):
                    is_folded = self.is_unit_folded(block)
                    box_s = 10
                    bx = (self.margin.width() - box_s) // 2
                    by = top + (line_h - box_s) // 2
                    painter.setPen(QPen(QColor(150, 150, 150)))
                    painter.setBrush(QColor(60, 60, 60))
                    painter.drawRect(bx, by, box_s, box_s)
                    painter.drawLine(bx + 2, by + box_s // 2, bx + box_s - 2, by + box_s // 2)
                    if is_folded:
                        painter.drawLine(bx + box_s // 2, by + 2, bx + box_s // 2, by + box_s - 2)
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())

    def _apply_all_extra_selections(self):
        all_selections = []
        all_selections.extend(self.ts_extra_selections)
        all_selections.extend(self.find_extra_selections)
        self.setExtraSelections(all_selections)

    def highlight_closest_timestamp(self, current_seconds):
        text = self.toPlainText()
        matches = list(TIMESTAMP_RE.finditer(text))
        if not matches:
            return

        closest_match = min(
            matches,
            key=lambda m: abs(
                ts_to_seconds(f"{m.group(1)}:{m.group(2)}:{m.group(3)}.{m.group(4)}") - current_seconds
            )
        )

        temp_cursor = QTextCursor(self.document())
        temp_cursor.setPosition(closest_match.start())
        temp_cursor.select(QTextCursor.LineUnderCursor)

        selection = QTextEdit.ExtraSelection()
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(200, 200, 0, 100))
        fmt.setProperty(QTextFormat.FullWidthSelection, True)
        selection.format = fmt
        selection.cursor = temp_cursor

        self.ts_extra_selections = [selection]
        self._apply_all_extra_selections()

        block = temp_cursor.block()
        y_pos = self.document().documentLayout().blockBoundingRect(block).top()
        viewport_height = self.viewport().height()
        scrollbar = self.verticalScrollBar()
        target_y = int(y_pos - viewport_height / 2 + 10)
        scrollbar.setValue(max(scrollbar.minimum(), min(target_y, scrollbar.maximum())))

    def clear_highlight(self):
        self.ts_extra_selections = []
        self._apply_all_extra_selections()

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

    # ---------- helpers for structural editing ----------

    def _block_text(self, block):
        return block.text() if block.isValid() else ""

    def _is_single_timestamp_line(self, text):
        return bool(self.SINGLE_TS_LINE_RE.fullmatch(text))

    def _is_double_timestamp_line(self, text):
        return bool(self.DOUBLE_TS_LINE_RE.fullmatch(text))

    def _is_speaker_line(self, text):
        return bool(self.SPEAKER_ONLY_RE.fullmatch(text))

    def _cursor_at_block_start(self, cursor):
        return cursor.positionInBlock() == 0

    def _set_cursor_to_block_start(self, block):
        c = QTextCursor(block)
        c.movePosition(QTextCursor.StartOfBlock)
        self.setTextCursor(c)
        self.ensureCursorVisible()

    def _set_cursor_after_block(self, block):
        c = QTextCursor(block)
        c.movePosition(QTextCursor.EndOfBlock)
        if c.block().next().isValid():
            c.movePosition(QTextCursor.NextBlock)
            c.movePosition(QTextCursor.StartOfBlock)
        self.setTextCursor(c)
        self.ensureCursorVisible()

    def _insert_text_at_block_start(self, block, text):
        c = QTextCursor(block)
        c.movePosition(QTextCursor.StartOfBlock)
        c.insertText(text)
        self.setTextCursor(c)

    def _insert_text_at_block_end(self, block, text):
        c = QTextCursor(block)
        c.movePosition(QTextCursor.EndOfBlock)
        c.insertText(text)
        self.setTextCursor(c)

    def _replace_block_text(self, block, text):
        c = QTextCursor(block)
        c.select(QTextCursor.LineUnderCursor)
        c.insertText(text)
        self.setTextCursor(c)

    def _remove_current_empty_block_if_present(self, block):
        if not block.isValid() or block.text().strip():
            return
        c = QTextCursor(block)
        c.movePosition(QTextCursor.EndOfBlock)
        c.deletePreviousChar()

    def _append_timestamp_to_block(self, block, ts_str):
        line_text = block.text()
        suffix = ts_str if line_text.endswith(" ") else f" {ts_str}"
        self._insert_text_at_block_end(block, suffix)

    def _next_speaker_tag(self, current_text, tagged_speakers):
        stripped = current_text.strip()
        if stripped in tagged_speakers:
            idx = tagged_speakers.index(stripped)
            return tagged_speakers[(idx + 1) % len(tagged_speakers)]
        return tagged_speakers[0]

    def _find_neighbors_around_pos(self, pos: int):
        text = self.toPlainText()
        if not text:
            return None, None

        prev_sec = None
        next_sec = None

        start = max(0, pos - 2000)
        before = text[start:pos]
        for m in TIMESTAMP_RE.finditer(before):
            ts = f"{m.group(1)}:{m.group(2)}:{m.group(3)}.{m.group(4)}"
            prev_sec = ts_to_seconds(ts)

        end = min(len(text), pos + 2000)
        after = text[pos:end]
        m_after = TIMESTAMP_RE.search(after)
        if m_after:
            ts = f"{m_after.group(1)}:{m_after.group(2)}:{m_after.group(3)}.{m_after.group(4)}"
            next_sec = ts_to_seconds(ts)

        return prev_sec, next_sec

    def _warn_timestamp_order(self, inserted_sec, previous_sec, parent_widget=None):
        if parent_widget is None:
            return False
        inserted_ts = seconds_to_ts(inserted_sec)
        prev_ts = seconds_to_ts(previous_sec)
        ans = QMessageBox.question(
            parent_widget,
            self.tr("Warning"),
            self.tr(
                "Inserted timestamp ({0}) is earlier than the previous one ({1}).\nContinue?"
            ).format(inserted_ts, prev_ts),
            QMessageBox.Yes | QMessageBox.No,
        )
        return ans == QMessageBox.Yes

    def _warn_identical_timestamp(self, inserted_sec, existing_sec, parent_widget=None):
        if parent_widget is None:
            return False
    
        inserted_ts = seconds_to_ts(inserted_sec)
        existing_ts = seconds_to_ts(existing_sec)
    
        answer = QMessageBox.question(
            parent_widget,
            self.tr("Duplicate timestamp"),
            self.tr(
                "Inserted timestamp ({0}) is identical to an existing neighboring timestamp ({1}).\nContinue?"
            ).format(inserted_ts, existing_ts),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        return answer == QMessageBox.Yes

    def _can_insert_timestamp_at_cursor(self, seconds, parent_widget=None):
        cursor = self.textCursor()
        pos = cursor.position()
        prev_sec, next_sec = self._find_neighbors_around_pos(pos)
    
        if prev_sec is not None and abs(prev_sec - seconds) < 1e-6:
            return self._warn_identical_timestamp(seconds, prev_sec, parent_widget)
    
        if next_sec is not None and abs(next_sec - seconds) < 1e-6:
            return self._warn_identical_timestamp(seconds, next_sec, parent_widget)
    
        if prev_sec is not None and prev_sec > seconds + 1e-6:
            return self._warn_timestamp_order(seconds, prev_sec, parent_widget)
    
        return True

    # ---------- structural insertion ----------

    def insert_timestamp(self, seconds, parent_widget=None):
        ts_str = f"⟦{seconds_to_ts(seconds)}⟧"

        if not self._can_insert_timestamp_at_cursor(seconds, parent_widget):
            return

        cursor = self.textCursor()
        block = cursor.block()
        block_text = block.text()
        at_bol = self._cursor_at_block_start(cursor)
        block_is_empty = (block_text.strip() == "")

        prev_block = block.previous()
        prev_text = self._block_text(prev_block)

        cursor.beginEditBlock()

        if at_bol and block_is_empty:
            if prev_block.isValid() and self._is_single_timestamp_line(prev_text):
                self._append_timestamp_to_block(prev_block, ts_str)
                self._remove_current_empty_block_if_present(block)
                self._set_cursor_after_block(prev_block)

            elif prev_block.isValid() and self._is_double_timestamp_line(prev_text):
                self._insert_text_at_block_start(block, f"{ts_str}\n")
                self._set_cursor_after_block(block)

            else:
                self._insert_text_at_block_start(block, f"{ts_str}\n")
                self._set_cursor_after_block(block)

        else:
            if self._is_single_timestamp_line(block_text):
                self._append_timestamp_to_block(block, ts_str)
                self._set_cursor_after_block(block)

            elif self._is_double_timestamp_line(block_text):
                self._insert_text_at_block_end(block, f"\n{ts_str}\n")
                next_block = block.next() if block.next().isValid() else block
                self._set_cursor_to_block_start(next_block)

            else:
                self._insert_text_at_block_end(block, f"\n{ts_str}\n")
                next_block = block.next() if block.next().isValid() else block
                self._set_cursor_to_block_start(next_block)

        cursor.endEditBlock()

    def insert_or_cycle_speaker(self, speakers):
        if not speakers:
            return

        tagged_speakers = [f"⟪{s}⟫" for s in speakers if s]
        if not tagged_speakers:
            return

        cursor = self.textCursor()
        block = cursor.block()
        block_text = block.text()
        at_bol = self._cursor_at_block_start(cursor)
        block_is_empty = (block_text.strip() == "")

        prev_block = block.previous()
        prev_text = self._block_text(prev_block)

        cursor.beginEditBlock()

        if at_bol and block_is_empty:
            if prev_block.isValid() and self._is_speaker_line(prev_text):
                self._replace_block_text(prev_block, self._next_speaker_tag(prev_text, tagged_speakers))
                self._set_cursor_after_block(prev_block)
            else:
                self._insert_text_at_block_start(block, f"{tagged_speakers[0]}\n")
                self._set_cursor_after_block(block)
        else:
            if self._is_speaker_line(block_text):
                self._replace_block_text(block, self._next_speaker_tag(block_text, tagged_speakers))
                self._set_cursor_after_block(block)
            else:
                self._insert_text_at_block_end(block, f"\n{tagged_speakers[0]}\n")
                next_block = block.next() if block.next().isValid() else block
                self._set_cursor_to_block_start(next_block)

        cursor.endEditBlock()

    def load_segments(self, segments):
        lines = []
        for seg in segments:
            text = seg.get('text', '').strip()
            if 'start' in seg and 'end' in seg:
                lines.append(f"⟦{seconds_to_ts(float(seg['start']))}⟧ ⟦{seconds_to_ts(float(seg['end']))}⟧")
            speaker = seg.get('speaker', '')
            if speaker:
                lines.append(f"⟪{speaker}⟫")
            lines.append(text)
            lines.append("")

        self.setPlainText('\n'.join(lines))
        self.document().setModified(False)

    def to_segments(self):
        segments = []
        current_seg = None

        def _flush():
            nonlocal current_seg
            if current_seg:
                current_seg['text'] = current_seg['text'].strip()
                if current_seg['text'] or 'start' in current_seg:
                    segments.append(current_seg)
            current_seg = None

        for line in self.toPlainText().splitlines():
            line_stripped = line.strip()

            if not line_stripped:
                _flush()
                continue

            m = self.TS_ONLY_RE.match(line_stripped)
            if m:
                _flush()
                start_s = ts_to_seconds(m.group(1))
                end_s = ts_to_seconds(m.group(2)) if m.group(2) else start_s
                current_seg = {
                    'start': round(start_s, 3),
                    'end': round(end_s, 3),
                    'text': ''
                }
                continue

            if current_seg is None:
                current_seg = {'text': ''}

            if not current_seg['text'] and not current_seg.get('speaker'):
                sm = self.SPEAKER_RE.match(line_stripped)
                if sm:
                    current_seg['speaker'] = sm.group(1)
                    if sm.group(2):
                        current_seg['text'] = sm.group(2) + "\n"
                    continue

            if current_seg['text']:
                current_seg['text'] += "\n" + line_stripped
            else:
                current_seg['text'] = line_stripped

        _flush()

        for seg in segments:
            if 'start' in seg and 'end' in seg:
                start_s = seg['start']
                end_s = seg['end']
                h_s, m_s = divmod(int(start_s // 60), 60)
                h_e, m_e = divmod(int(end_s // 60), 60)
                seg['timestamp'] = f"{m_s:02d}:{int(start_s % 60):02d} - {m_e:02d}:{int(end_s % 60):02d}"

        return segments
