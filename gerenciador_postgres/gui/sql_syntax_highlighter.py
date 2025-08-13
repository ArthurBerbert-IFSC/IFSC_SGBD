from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QSyntaxHighlighter
from PyQt6.QtWidgets import QTextEdit


class SQLSyntaxHighlighter(QSyntaxHighlighter):
    """Simple SQL syntax highlighter for QTextEdit widgets."""

    def __init__(self, text_edit: QTextEdit):
        super().__init__(text_edit.document())
        self._highlighting_rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("blue"))
        keyword_format.setFontWeight(QFont.Weight.Bold)
        keywords = [
            "SELECT",
            "FROM",
            "WHERE",
            "INSERT",
            "UPDATE",
            "DELETE",
            "CREATE",
            "DROP",
            "TABLE",
            "INTO",
            "VALUES",
            "SET",
            "JOIN",
            "ON",
            "AND",
            "OR",
            "NULL",
            "NOT",
            "IS",
            "LIKE",
            "GROUP",
            "BY",
            "ORDER",
            "HAVING",
            "AS",
            "DISTINCT",
            "LIMIT",
            "OFFSET",
        ]
        for word in keywords:
            pattern = QRegularExpression(
                rf"\\b{word}\\b",
                QRegularExpression.PatternOption.CaseInsensitiveOption,
            )
            self._highlighting_rules.append((pattern, keyword_format))

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("magenta"))
        self._highlighting_rules.append(
            (QRegularExpression(r"'([^']|'')*'"), string_format)
        )

        single_line_comment_format = QTextCharFormat()
        single_line_comment_format.setForeground(QColor("darkGreen"))
        self._highlighting_rules.append(
            (QRegularExpression(r"--[^\n]*"), single_line_comment_format)
        )

        self.multi_line_comment_format = QTextCharFormat()
        self.multi_line_comment_format.setForeground(QColor("darkGreen"))
        self.comment_start = QRegularExpression(r"/\\*")
        self.comment_end = QRegularExpression(r"\\*/")

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt method name)
        for pattern, fmt in self._highlighting_rules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)

        self.setCurrentBlockState(0)
        start_index = 0
        if self.previousBlockState() != 1:
            start_index = self.comment_start.match(text).capturedStart()
        while start_index >= 0:
            end_match = self.comment_end.match(text, start_index)
            if end_match.capturedStart() == -1:
                self.setCurrentBlockState(1)
                comment_length = len(text) - start_index
            else:
                comment_length = (
                    end_match.capturedStart()
                    - start_index
                    + end_match.capturedLength()
                )
            self.setFormat(start_index, comment_length, self.multi_line_comment_format)
            if end_match.capturedStart() == -1:
                break
            start_index = self.comment_start.match(
                text, start_index + comment_length
            ).capturedStart()
