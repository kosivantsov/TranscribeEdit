# editor.py
import re
from PyQt5.QtWidgets import QPlainTextEdit, QTextEdit, QMessageBox, QWidget
from PyQt5.QtGui import (
    QFont, QTextCursor, QColor, QTextCharFormat,
    QTextFormat, QSyntaxHighlighter, QPainter, QPen
)
from PyQt5.QtCore import pyqtSignal, Qt, QRect, QSize, QSettings

from utils import TIMESTAMP_RE, ts_to_seconds, seconds_to_ts

COMMENT_OPEN_RE  = re.compile(r'<!--')
COMMENT_CLOSE_RE = re.compile(r'-->')


class TranscriptHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)

        self.ts_format  = QTextCharFormat()
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

        self._list_bg_fmt     = QTextCharFormat()
        self._list_marker_fmt = QTextCharFormat()

        self._comment_fmt = QTextCharFormat()
        self._comment_fmt.setForeground(QColor(110, 140, 90))
        self._comment_fmt.setFontItalic(True)

        self.ts_pattern  = TIMESTAMP_RE
        self.spk_pattern = re.compile(r'⟪[^⟫]+⟫')

    def _merge_format(self, pos, length, src_fmt):
        if length <= 0:
            return
        existing = self.format(pos)
        existing.merge(src_fmt)
        self.setFormat(pos, length, existing)

    def update_formats(self, colors):
        self.ts_format = QTextCharFormat()
        if colors.get("ts_fg"):
            self.ts_format.setForeground(QColor(colors["ts_fg"]))
        if colors.get("ts_bg"):
            self.ts_format.setBackground(QColor(colors["ts_bg"]))
        if colors.get("ts_font"):
            f = QFont(); f.fromString(colors["ts_font"])
            self.ts_format.setFont(f)

        self.spk_format = QTextCharFormat()
        if colors.get("spk_fg"):
            self.spk_format.setForeground(QColor(colors["spk_fg"]))
        if colors.get("spk_bg"):
            self.spk_format.setBackground(QColor(colors["spk_bg"]))
        if colors.get("spk_font"):
            f = QFont(); f.fromString(colors["spk_font"])
            self.spk_format.setFont(f)

        if colors.get("md_heading_fg"):
            self._heading_fmt.setForeground(QColor(colors["md_heading_fg"]))

        if colors.get("md_hr_fg"):
            self.hr_color = QColor(colors["md_hr_fg"])
            self._hr_fmt.setForeground(self.hr_color)

        if colors.get("md_list_bg"):
            self._list_bg_fmt.setBackground(QColor(colors["md_list_bg"]))
        if colors.get("md_list_marker_fg"):
            self._list_marker_fmt.setForeground(QColor(colors["md_list_marker_fg"]))

        if colors.get("md_markup_fg"):
            self._markup_fmt.setForeground(QColor(colors["md_markup_fg"]))
        if colors.get("md_markup_font"):
            f = QFont(); f.fromString(colors["md_markup_font"])
            self._markup_fmt.setFont(f)

        self._code_fmt = QTextCharFormat()
        if colors.get("md_code_font"):
            f = QFont(); f.fromString(colors["md_code_font"])
            self._code_fmt.setFont(f)
        else:
            self._code_fmt.setFontFamily("Courier New")
        if colors.get("md_code_bg"):
            self._code_fmt.setBackground(QColor(colors["md_code_bg"]))
        else:
            self._code_fmt.setBackground(QColor(60, 60, 60, 120))
        if colors.get("md_code_fg"):
            self._code_fmt.setForeground(QColor(colors["md_code_fg"]))

        self._quote_fmt = QTextCharFormat()
        self._quote_fmt.setFontItalic(True)
        if colors.get("md_blockquote_fg"):
            self._quote_fmt.setForeground(QColor(colors["md_blockquote_fg"]))
        else:
            self._quote_fmt.setForeground(QColor(150, 180, 150))

        self._comment_fmt = QTextCharFormat()
        if colors.get("comment_font"):
            f = QFont(); f.fromString(colors["comment_font"])
            self._comment_fmt.setFont(f)
        else:
            self._comment_fmt.setFontItalic(True)
        if colors.get("comment_fg"):
            self._comment_fmt.setForeground(QColor(colors["comment_fg"]))
        else:
            self._comment_fmt.setForeground(QColor(110, 140, 90))
        if colors.get("comment_bg"):
            self._comment_fmt.setBackground(QColor(colors["comment_bg"]))

        self.rehighlight()

    def _highlight_comments(self, text):
        in_comment = self.previousBlockState() == 1

        if text.strip() == "":
            self.setCurrentBlockState(-1)
            return in_comment

        pos    = 0
        length = len(text)
        while pos < length:
            if not in_comment:
                m = COMMENT_OPEN_RE.search(text, pos)
                if not m:
                    break
                start   = m.start()
                m_close = COMMENT_CLOSE_RE.search(text, m.end())
                if m_close:
                    end = m_close.end()
                    self.setFormat(start, end - start, self._comment_fmt)
                    pos = end
                else:
                    self.setFormat(start, length - start, self._comment_fmt)
                    in_comment = True
                    pos = length
            else:
                m_close = COMMENT_CLOSE_RE.search(text, pos)
                if m_close:
                    end = m_close.end()
                    self.setFormat(0, end, self._comment_fmt)
                    in_comment = False
                    pos = end
                else:
                    self.setFormat(0, length, self._comment_fmt)
                    pos = length

        self.setCurrentBlockState(1 if in_comment else -1)

    def highlightBlock(self, text):
        block      = self.currentBlock()
        next_block = block.next()
        next_text  = next_block.text().strip() if next_block.isValid() else ""
        text_stripped = text.strip()

        is_heading = False
        if re.match(r'^#{1,6}\s+', text_stripped) or (
            text_stripped and re.fullmatch(r'={3,}|-{3,}', next_text)
        ):
            is_heading = True

        if is_heading:
            self.setFormat(0, len(text), self._heading_fmt)
            self.setCurrentBlockState(-1)
            return

        if re.fullmatch(r'(\*{3,}|-{3,}|_{3,})', text_stripped):
            prev_block = block.previous()
            if not prev_block.isValid() or not prev_block.text().strip():
                self.setFormat(0, len(text), self._hr_fmt)
                self.setCurrentBlockState(-1)
                return

        m_list = re.match(r'^(\s*)([-*+]\s+)(.*)', text)
        if m_list:
            content_start = m_list.start(2)
            content_len   = len(m_list.group(2)) + len(m_list.group(3))
            self.setFormat(content_start, content_len, self._list_bg_fmt)
            self.setFormat(m_list.start(2), len(m_list.group(2)), self._list_marker_fmt)

        m = re.match(r'^(>+)\s*(.*)', text)
        if m:
            self.setFormat(m.start(1), m.end(1) - m.start(1), self._markup_fmt)
            self.setFormat(m.start(2), m.end(2) - m.start(2), self._quote_fmt)

        for m in re.finditer(r'(\*\*|__)(.+?)(\1)', text):
            self._merge_format(m.start(1), m.end(1) - m.start(1), self._markup_fmt)
            self._merge_format(m.start(2), m.end(2) - m.start(2), self._bold_fmt)
            self._merge_format(m.start(3), m.end(3) - m.start(3), self._markup_fmt)

        for m in re.finditer(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', text):
            self._merge_format(m.start(), 1, self._markup_fmt)
            self._merge_format(m.start(1), m.end(1) - m.start(1), self._italic_fmt)
            self._merge_format(m.end() - 1, 1, self._markup_fmt)

        for m in re.finditer(r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)', text):
            self._merge_format(m.start(), 1, self._markup_fmt)
            self._merge_format(m.start(1), m.end(1) - m.start(1), self._italic_fmt)
            self._merge_format(m.end() - 1, 1, self._markup_fmt)

        for m in re.finditer(r'(~~)(.+?)(~~)', text):
            self._merge_format(m.start(1), 2, self._markup_fmt)
            self._merge_format(m.start(2), m.end(2) - m.start(2), self._strike_fmt)
            self._merge_format(m.start(3), 2, self._markup_fmt)

        for m in re.finditer(r'(`)(.+?)(`)', text):
            self._merge_format(m.start(1), 1, self._markup_fmt)
            self._merge_format(m.start(2), m.end(2) - m.start(2), self._code_fmt)
            self._merge_format(m.start(3), 1, self._markup_fmt)

        for m in re.finditer(r'(<u>)(.+?)(</u>)', text):
            self._merge_format(m.start(1), 3, self._markup_fmt)
            self._merge_format(m.start(2), m.end(2) - m.start(2), self._underline_fmt)
            self._merge_format(m.start(3), 4, self._markup_fmt)

        for m in re.finditer(r'(\[)(.*?)(\])(\()(.+?)(\))', text):
            self._merge_format(m.start(1), 1, self._markup_fmt)
            self._merge_format(m.start(2), m.end(2) - m.start(2), self._link_fmt)
            self._merge_format(m.start(3), 2, self._markup_fmt)
            self._merge_format(m.start(5), m.end(5) - m.start(5), self._markup_fmt)
            self._merge_format(m.start(6), 1, self._markup_fmt)

        for m in re.finditer(r'(<)(.+?@[^>]+|[a-zA-Z]+://[^>]+)(>)', text):
            self._merge_format(m.start(1), 1, self._markup_fmt)
            self._merge_format(m.start(2), m.end(2) - m.start(2), self._link_fmt)
            self._merge_format(m.start(3), 1, self._markup_fmt)

        for m in re.finditer(r'</?[a-zA-Z0-9]+[^>]*>', text):
            self._merge_format(m.start(), m.end() - m.start(), self._markup_fmt)

        for m in self.ts_pattern.finditer(text):
            self._merge_format(m.start(), m.end() - m.start(), self.ts_format)

        for m in self.spk_pattern.finditer(text):
            self._merge_format(m.start(), m.end() - m.start(), self.spk_format)

        self._highlight_comments(text)


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

    SINGLE_TS_LINE_RE = re.compile(r'^\s*⟦\d{1,}:\d{2}:\d{2}\.\d{2,3}⟧\s*$')
    DOUBLE_TS_LINE_RE = re.compile(r'^\s*⟦\d{1,}:\d{2}:\d{2}\.\d{2,3}⟧\s+⟦\d{1,}:\d{2}:\d{2}\.\d{2,3}⟧\s*$')
    SPEAKER_ONLY_RE   = re.compile(r'^\s*⟪[^⟫]+⟫\s*$')
    TS_ONLY_RE        = re.compile(r'^\s*⟦(\d+:\d{2}:\d{2}\.\d{2,3})⟧(?:\s*⟦(\d+:\d{2}:\d{2}\.\d{2,3})⟧)?\s*$')
    SPEAKER_RE        = re.compile(r'^⟪([^⟫]+)⟫\s*(.*)$')
    COMMENT_LINE_RE   = re.compile(r'<!--(.*?)-->', re.DOTALL)

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
        self.margin      = EditorMargin(self)
        self.blockCountChanged.connect(self.update_margin_width)
        self.updateRequest.connect(self.update_margin)
        self.update_margin_width()

        self.find_extra_selections = []
        self.ts_extra_selections   = []

    def setStyleSheet(self, sheet):
        super().setStyleSheet(sheet.replace("QTextEdit", "QPlainTextEdit"))

    def paintEvent(self, e):
        super().paintEvent(e)
        painter = QPainter(self.viewport())
        painter.setPen(QPen(self.highlighter.hr_color, 1, Qt.SolidLine))

        block = self.firstVisibleBlock()
        top   = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())

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
            top   = bottom

    def toggle_format(self, tag_open, tag_close=None):
        if not tag_close:
            tag_close = tag_open

        cursor = self.textCursor()
        original_caret_pos = cursor.position()

        if not cursor.hasSelection():
            cursor.select(QTextCursor.WordUnderCursor)

        text = cursor.selectedText()
        if not text:
            return

        len_o, len_c = len(tag_open), len(tag_close)
        pos    = cursor.position()
        anchor = cursor.anchor()
        start, end = min(pos, anchor), max(pos, anchor)
        caret_pos = original_caret_pos

        tracker = QTextCursor(self.document())
        tracker.setPosition(caret_pos)

        edit_cursor = QTextCursor(self.document())
        edit_cursor.beginEditBlock()

        if text.startswith(tag_open) and text.endswith(tag_close) and len(text) >= len_o + len_c:
            edit_cursor.setPosition(end - len_c)
            edit_cursor.setPosition(end, QTextCursor.KeepAnchor)
            edit_cursor.removeSelectedText()

            edit_cursor.setPosition(start)
            edit_cursor.setPosition(start + len_o, QTextCursor.KeepAnchor)
            edit_cursor.removeSelectedText()
        else:
            edit_cursor.setPosition(start)
            edit_cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, len_o)
            left_text = edit_cursor.selectedText()

            edit_cursor.setPosition(end)
            edit_cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, len_c)
            right_text = edit_cursor.selectedText()

            if left_text == tag_open and right_text == tag_close:
                edit_cursor.setPosition(end)
                edit_cursor.setPosition(end + len_c, QTextCursor.KeepAnchor)
                edit_cursor.removeSelectedText()

                edit_cursor.setPosition(start - len_o)
                edit_cursor.setPosition(start, QTextCursor.KeepAnchor)
                edit_cursor.removeSelectedText()
            else:
                edit_cursor.setPosition(end)
                edit_cursor.insertText(tag_close)

                edit_cursor.setPosition(start)
                edit_cursor.insertText(tag_open)

        edit_cursor.endEditBlock()

        tracker.clearSelection()
        self.setTextCursor(tracker)
        self.ensureCursorVisible()

    def format_bold(self):
        self.toggle_format("**")

    def format_italic(self):
        self.toggle_format("_")

    def add_comment(self):
        cursor = self.textCursor()
        edit   = QTextCursor(self.document())
        edit.beginEditBlock()

        if cursor.hasSelection():
            start = min(cursor.position(), cursor.anchor())
            end   = max(cursor.position(), cursor.anchor())

            edit.setPosition(end)
            edit.insertText("-->")
            edit.setPosition(start)
            edit.insertText("<!--")

            final = QTextCursor(self.document())
            final.setPosition(end + 4 + 3)
            edit.endEditBlock()
            self.setTextCursor(final)

        else:
            block      = cursor.block()
            block_text = block.text()

            if block_text.strip():
                line_start = block.position()
                line_len   = len(block_text)

                edit.setPosition(line_start)
                edit.setPosition(line_start + line_len, QTextCursor.KeepAnchor)
                replacement = f"<!--\n{block_text}\n-->"
                edit.insertText(replacement)

                final = QTextCursor(self.document())
                final.setPosition(line_start + len(replacement))
                edit.endEditBlock()
                self.setTextCursor(final)

            else:
                pos = block.position()
                edit.setPosition(pos)
                edit.insertText("<!--\n-->")

                final = QTextCursor(self.document())
                final.setPosition(pos + 5)
                edit.endEditBlock()
                self.setTextCursor(final)

        self.ensureCursorVisible()

    def highlight_find_result(self):
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return

        selection = QTextEdit.ExtraSelection()
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(255, 150, 0, 180))
        fmt.setForeground(QColor(0, 0, 0))
        selection.format  = fmt
        selection.cursor  = cursor

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
        block  = self.firstVisibleBlock()
        top    = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid():
            if top <= pos.y() <= bottom:
                if self.is_unit_start(block) and self.unit_has_content(block):
                    self.toggle_fold(block)
                break
            block  = block.next()
            top    = bottom
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
        painter  = QPainter(self.margin)
        base_bg  = self.palette().window().color()

        if base_bg.lightness() < 128:
            bg_color = base_bg.lighter(130)
        else:
            bg_color = base_bg.darker(130)

        painter.fillRect(event.rect(), bg_color)

        text_color = self.palette().windowText().color()
        btn_color  = self.palette().button().color()

        block  = self.firstVisibleBlock()
        top    = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        line_h = self.fontMetrics().height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                if self.is_unit_start(block) and self.unit_has_content(block):
                    is_folded = self.is_unit_folded(block)
                    box_s = 10
                    bx = (self.margin.width() - box_s) // 2
                    by = top + (line_h - box_s) // 2

                    painter.setPen(QPen(text_color))
                    painter.setBrush(btn_color)
                    painter.drawRect(bx, by, box_s, box_s)
                    painter.drawLine(bx + 2, by + box_s // 2, bx + box_s - 2, by + box_s // 2)

                    if is_folded:
                        painter.drawLine(bx + box_s // 2, by + 2, bx + box_s // 2, by + box_s - 2)
            block  = block.next()
            top    = bottom
            bottom = top + int(self.blockBoundingRect(block).height())

    def _apply_all_extra_selections(self):
        all_selections = []
        all_selections.extend(self.ts_extra_selections)
        all_selections.extend(self.find_extra_selections)
        self.setExtraSelections(all_selections)

    def highlight_closest_timestamp(self, current_seconds):
        text    = self.toPlainText()
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

        block          = temp_cursor.block()
        y_pos          = self.document().documentLayout().blockBoundingRect(block).top()
        viewport_height = self.viewport().height()
        scrollbar      = self.verticalScrollBar()
        target_y       = int(y_pos - viewport_height / 2 + 10)
        scrollbar.setValue(max(scrollbar.minimum(), min(target_y, scrollbar.maximum())))

    def clear_highlight(self):
        self.ts_extra_selections = []
        self._apply_all_extra_selections()

    def _timestamp_at_cursor(self):
        cursor     = self.textCursor()
        block_text = cursor.block().text()
        col        = cursor.positionInBlock()
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
        suffix    = ts_str if line_text.endswith(" ") else f" {ts_str}"
        self._insert_text_at_block_end(block, suffix)

    def _next_speaker_tag(self, current_text, tagged_speakers):
        stripped = current_text.strip()
        if stripped in tagged_speakers:
            idx = tagged_speakers.index(stripped)
            return tagged_speakers[(idx + 1) % len(tagged_speakers)]
        return tagged_speakers[0]

    def _validate_timestamp_insertion(self, seconds, parent_widget=None):
        """Return True if insertion should proceed, False to block it."""
        settings = QSettings()
        if not settings.value("editor/validate_timestamps", True, type=bool):
            return True

        cursor   = self.textCursor()
        caret    = cursor.position()
        doc_text = self.toPlainText()

        text_before = doc_text[:caret]
        prev_match  = None
        for m in TIMESTAMP_RE.finditer(text_before):
            prev_match = m

        if prev_match is None:
            return True

        prev_ts_str = (
            f"{prev_match.group(1)}:{prev_match.group(2)}"
            f":{prev_match.group(3)}.{prev_match.group(4)}"
        )
        prev_sec = ts_to_seconds(prev_ts_str)

        # Normalize the incoming 'seconds' by formatting it as a timestamp string first.
        # This eliminates discrepancies between the raw float and the rounded text.
        inserted_ts_str = seconds_to_ts(seconds)
        inserted_sec    = ts_to_seconds(inserted_ts_str)

        if prev_ts_str == inserted_ts_str:
            ans = QMessageBox.question(
                parent_widget,
                self.tr("Duplicate Timestamp"),
                self.tr(
                    "The timestamp about to be inserted ({0}) is identical to "
                    "the closest preceding timestamp ({1}).\n\nInsert anyway?"
                ).format(inserted_ts_str, prev_ts_str),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            return ans == QMessageBox.Yes

        if inserted_sec < prev_sec:
            ans = QMessageBox.question(
                parent_widget,
                self.tr("Out-of-Order Timestamp"),
                self.tr(
                    "The timestamp about to be inserted ({0}) is earlier than "
                    "the closest preceding timestamp ({1}).\n\nInsert anyway?"
                ).format(inserted_ts_str, prev_ts_str),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            return ans == QMessageBox.Yes

        return True

    def insert_timestamp(self, seconds, parent_widget=None):
        ts_str = f"⟦{seconds_to_ts(seconds)}⟧"

        if not self._validate_timestamp_insertion(seconds, parent_widget):
            return

        cursor     = self.textCursor()
        block      = cursor.block()
        block_text = block.text()
        at_bol     = self._cursor_at_block_start(cursor)
        block_is_empty = (block_text.strip() == "")

        prev_block = block.previous()
        prev_text  = self._block_text(prev_block)

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
                ts_line    = block.next()
                blank_line = ts_line.next() if ts_line.isValid() else ts_line
                self._set_cursor_to_block_start(blank_line)

            else:
                self._insert_text_at_block_end(block, f"\n{ts_str}\n")
                ts_line    = block.next()
                blank_line = ts_line.next() if ts_line.isValid() else ts_line
                self._set_cursor_to_block_start(blank_line)

        cursor.endEditBlock()

    def insert_or_cycle_speaker(self, speakers):
        if not speakers:
            return

        tagged_speakers = [f"⟪{s}⟫" for s in speakers if s]
        if not tagged_speakers:
            return

        cursor     = self.textCursor()
        block      = cursor.block()
        block_text = block.text()
        at_bol     = self._cursor_at_block_start(cursor)
        block_is_empty = (block_text.strip() == "")

        prev_block = block.previous()
        prev_text  = self._block_text(prev_block)

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
            comment = seg.get('comment', '')
            if comment:
                lines.append(f"<!--{comment}-->")
            lines.append("")

        self.setPlainText('\n'.join(lines))
        self.document().setModified(False)

    @staticmethod
    def _extract_valid_comments(full_text):
        comments = []
        pos      = 0
        length   = len(full_text)
        while True:
            start = full_text.find("<!--", pos)
            if start == -1:
                break
            end_marker = full_text.find("-->", start + 4)
            if end_marker == -1:
                break
            end   = end_marker + 3
            inner = full_text[start + 4:end_marker]
            if re.search(r'\n[ \t]*\n', inner):
                pos = start + 4
                continue
            comments.append((start, end, inner.strip()))
            pos = end
        return comments

    def to_segments(self):
        full_text = self.toPlainText()
        comments  = self._extract_valid_comments(full_text)

        comment_map   = {}
        working_chars = list(full_text)
        for start, end, comment_text in comments:
            line_index = full_text.count("\n", 0, start)
            comment_map[line_index] = comment_text
            for i in range(start, end):
                if working_chars[i] != "\n":
                    working_chars[i] = " "
        working_text = "".join(working_chars)

        segments    = []
        current_seg = None

        def _flush():
            nonlocal current_seg
            if current_seg:
                current_seg['text'] = current_seg['text'].strip()
                if current_seg['text'] or 'start' in current_seg or current_seg.get('comment'):
                    segments.append(current_seg)
                current_seg = None

        lines = working_text.splitlines()
        for idx, line in enumerate(lines):
            line_stripped = line.strip()

            if idx in comment_map:
                if current_seg is None:
                    current_seg = {'text': ''}
                current_seg['comment'] = (
                    (current_seg.get('comment', '') + "\n" + comment_map[idx]).strip()
                    if current_seg.get('comment') else comment_map[idx]
                )
                if not line_stripped:
                    continue

            if not line_stripped:
                _flush()
                continue

            m = self.TS_ONLY_RE.match(line_stripped)
            if m:
                _flush()
                start_s = ts_to_seconds(m.group(1))
                end_s   = ts_to_seconds(m.group(2)) if m.group(2) else start_s
                current_seg = {
                    'start': round(start_s, 3),
                    'end':   round(end_s,   3),
                    'text':  ''
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
                end_s   = seg['end']
                h_s, m_s = divmod(int(start_s // 60), 60)
                h_e, m_e = divmod(int(end_s   // 60), 60)
                seg['timestamp'] = f"{m_s:02d}:{int(start_s % 60):02d} - {m_e:02d}:{int(end_s % 60):02d}"

        return segments
