from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTextEdit,
    QPushButton,
    QPlainTextEdit,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from pathlib import Path
from ..db_manager import DBManager
import psycopg2
from .sql_syntax_highlighter import SQLSyntaxHighlighter


class SQLConsoleView(QWidget):
    """Janela simples para executar comandos SQL."""

    def __init__(self, db_manager: DBManager, parent: QWidget | None = None):
        super().__init__(parent)
        assets_dir = Path(__file__).resolve().parents[2] / "assets"
        self.setWindowIcon(QIcon(str(assets_dir / "auditoria.jpeg")))
        self.setWindowTitle("Console SQL")
        self.db_manager = db_manager
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.txtSQL = QTextEdit()
        self._highlighter = SQLSyntaxHighlighter(self.txtSQL)
        self.btnExecute = QPushButton("Executar")
        self.txtResult = QPlainTextEdit()
        self.txtResult.setReadOnly(True)
        layout.addWidget(self.txtSQL)
        layout.addWidget(self.btnExecute, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.txtResult)
        self.btnExecute.clicked.connect(self.on_execute)

    def on_execute(self):
        sql_text = self.txtSQL.toPlainText().strip()
        if not sql_text:
            return
        conn = self.db_manager.conn
        try:
            with conn.cursor() as cur:
                statements = [s.strip() for s in sql_text.split(";") if s.strip()]
                output_lines: list[str] = []
                for stmt in statements:
                    cur.execute(stmt)
                    if cur.description:
                        rows = cur.fetchall()
                        headers = [d[0] for d in cur.description]
                        output_lines.append("\t".join(headers))
                        for row in rows:
                            output_lines.append("\t".join(str(col) for col in row))
                    else:
                        output_lines.append(f"{cur.rowcount} linha(s) afetadas.")
                conn.commit()
                self.txtResult.setPlainText("\n".join(output_lines) or "Comando executado.")
        except psycopg2.Error as e:
            conn.rollback()
            self.txtResult.setPlainText(f"Erro: {e}")
