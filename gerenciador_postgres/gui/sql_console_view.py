from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QPlainTextEdit,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QFont
from pathlib import Path
from ..db_manager import DBManager
import psycopg2


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
        self.btnExecute = QPushButton("Executar")
        self.btnIncrease = QPushButton("+")
        self.btnDecrease = QPushButton("-")
        self.txtResult = QPlainTextEdit()
        self.txtResult.setReadOnly(True)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.btnDecrease)
        button_layout.addWidget(self.btnIncrease)
        button_layout.addStretch()
        button_layout.addWidget(self.btnExecute)

        layout.addWidget(self.txtSQL)
        layout.addLayout(button_layout)
        layout.addWidget(self.txtResult)

        self.btnExecute.clicked.connect(self.on_execute)
        self.btnIncrease.clicked.connect(self.increase_font)
        self.btnDecrease.clicked.connect(self.decrease_font)
        self.font_size = self.txtSQL.font().pointSize()

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

    def _set_font_size(self):
        font = QFont(self.txtSQL.font())
        font.setPointSize(self.font_size)
        self.txtSQL.setFont(font)
        self.txtResult.setFont(font)

    def increase_font(self):
        self.font_size += 1
        self._set_font_size()

    def decrease_font(self):
        if self.font_size > 1:
            self.font_size -= 1
            self._set_font_size()
