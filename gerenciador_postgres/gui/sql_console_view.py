from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QPlainTextEdit,
    QComboBox,
    QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from pathlib import Path
from ..db_manager import DBManager
import psycopg2
import json


class SQLConsoleView(QWidget):
    """Janela simples para executar comandos SQL."""

    def __init__(self, db_manager: DBManager, parent: QWidget | None = None):
        super().__init__(parent)
        assets_dir = Path(__file__).resolve().parents[2] / "assets"
        self.setWindowIcon(QIcon(str(assets_dir / "auditoria.jpeg")))
        self.setWindowTitle("Console SQL")
        self.db_manager = db_manager
        self.queries_file = Path(__file__).resolve().parents[2] / "config" / "sql_queries.json"
        self.queries: dict[str, str] = {}
        self._load_queries()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        query_layout = QHBoxLayout()
        self.cmbQueries = QComboBox()
        self.btnSaveQuery = QPushButton("Salvar")
        self.btnDeleteQuery = QPushButton("Remover")
        query_layout.addWidget(self.cmbQueries)
        query_layout.addWidget(self.btnSaveQuery)
        query_layout.addWidget(self.btnDeleteQuery)
        layout.addLayout(query_layout)

        self.txtSQL = QTextEdit()
        self.btnExecute = QPushButton("Executar")
        self.txtResult = QPlainTextEdit()
        self.txtResult.setReadOnly(True)
        layout.addWidget(self.txtSQL)
        layout.addWidget(self.btnExecute, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.txtResult)

        self.btnExecute.clicked.connect(self.on_execute)
        self.cmbQueries.currentIndexChanged.connect(self.on_query_selected)
        self.btnSaveQuery.clicked.connect(self.on_save_query)
        self.btnDeleteQuery.clicked.connect(self.on_delete_query)

        self._refresh_query_list()

    def _load_queries(self):
        if self.queries_file.exists():
            try:
                with self.queries_file.open("r", encoding="utf-8") as f:
                    self.queries = json.load(f)
            except json.JSONDecodeError:
                self.queries = {}
        else:
            self.queries = {}

    def _write_queries(self):
        self.queries_file.parent.mkdir(parents=True, exist_ok=True)
        with self.queries_file.open("w", encoding="utf-8") as f:
            json.dump(self.queries, f, indent=2, ensure_ascii=False)

    def _refresh_query_list(self, current: str | None = None):
        self.cmbQueries.blockSignals(True)
        self.cmbQueries.clear()
        self.cmbQueries.addItem("Selecionar consulta")
        for name in sorted(self.queries.keys()):
            self.cmbQueries.addItem(name)
        if current and current in self.queries:
            index = self.cmbQueries.findText(current)
            self.cmbQueries.setCurrentIndex(index)
        else:
            self.cmbQueries.setCurrentIndex(0)
        self.cmbQueries.blockSignals(False)

    def on_query_selected(self, index: int):
        name = self.cmbQueries.currentText()
        if name in self.queries:
            self.txtSQL.setPlainText(self.queries[name])

    def on_save_query(self):
        text = self.txtSQL.toPlainText().strip()
        if not text:
            return
        name, ok = QInputDialog.getText(self, "Salvar consulta", "Nome da consulta:")
        if ok and name:
            self.queries[name] = text
            self._write_queries()
            self._refresh_query_list(name)

    def on_delete_query(self):
        name = self.cmbQueries.currentText()
        if name in self.queries:
            del self.queries[name]
            self._write_queries()
            self._refresh_query_list()

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
