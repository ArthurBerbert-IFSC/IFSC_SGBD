from time import perf_counter
from pathlib import Path
import json

import psycopg2
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QPlainTextEdit,
    QComboBox,
    QInputDialog,
    QLabel,
    QTabWidget,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QSplitter,
)

from ..db_manager import DBManager
from .sql_syntax_highlighter import SQLSyntaxHighlighter

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

        # Font controls at the top
        self.lblFont = QLabel("Tamanho do texto:")
        self.btnDecrease = QPushButton("-")
        self.btnIncrease = QPushButton("+")
        self.btnClear = QPushButton("Limpar")
        font_layout = QHBoxLayout()
        font_layout.addWidget(self.lblFont)
        font_layout.addWidget(self.btnDecrease)
        font_layout.addWidget(self.btnIncrease)
        font_layout.addWidget(self.btnClear)
        font_layout.addStretch()
        layout.addLayout(font_layout)

        # Saved queries controls
        query_layout = QHBoxLayout()
        self.cmbQueries = QComboBox()
        self.btnSaveQuery = QPushButton("Salvar")
        self.btnDeleteQuery = QPushButton("Remover")
        query_layout.addWidget(self.cmbQueries)
        query_layout.addWidget(self.btnSaveQuery)
        query_layout.addWidget(self.btnDeleteQuery)
        layout.addLayout(query_layout)

        # SQL editor and results
        self.txtSQL = QTextEdit()
        self.txtSQL.setTabStopDistance(
            4 * self.txtSQL.fontMetrics().horizontalAdvance(" ")
        )
        self._highlighter = SQLSyntaxHighlighter(self.txtSQL)
        self.btnExecute = QPushButton("Executar")
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.btnExecute)

        sql_container = QWidget()
        sql_layout = QVBoxLayout(sql_container)
        sql_layout.addWidget(self.txtSQL)
        sql_layout.addLayout(button_layout)

        self.tblDataOutput = QTableWidget()
        self.txtMessages = QPlainTextEdit()
        self.txtMessages.setReadOnly(True)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.tblDataOutput, "Saída de Dados")
        self.tabs.addTab(self.txtMessages, "Mensagens")

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(sql_container)
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        self.status_bar = QStatusBar()

        layout.addWidget(splitter)
        layout.addWidget(self.status_bar)

        # Shortcuts and signals
        self.shortcut = QShortcut(QKeySequence(Qt.Key.Key_F5), self)
        self.shortcut.activated.connect(self.on_execute)
        self.btnExecute.clicked.connect(self.on_execute)
        self.btnClear.clicked.connect(self.txtSQL.clear)
        self.cmbQueries.currentIndexChanged.connect(self.on_query_selected)
        self.btnSaveQuery.clicked.connect(self.on_save_query)
        self.btnDeleteQuery.clicked.connect(self.on_delete_query)
        self.btnIncrease.clicked.connect(self.increase_font)
        self.btnDecrease.clicked.connect(self.decrease_font)
        self.font_size = self.txtSQL.font().pointSize()

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
        self.status_bar.showMessage("Executando...")
        self.tblDataOutput.clear()
        self.tblDataOutput.setRowCount(0)
        self.tblDataOutput.setColumnCount(0)
        self.txtMessages.clear()
        start_time = perf_counter()
        last_row_count = 0
        cur = None
        try:
            with conn.cursor() as cur:
                statements = [s.strip() for s in sql_text.split(";") if s.strip()]
                for stmt in statements:
                    cur.execute(stmt)
                    if cur.description:
                        rows = cur.fetchall()
                        headers = [d[0] for d in cur.description]
                        self.tblDataOutput.setColumnCount(len(headers))
                        self.tblDataOutput.setHorizontalHeaderLabels(headers)
                        self.tblDataOutput.setRowCount(len(rows))
                        for r, row in enumerate(rows):
                            for c, col in enumerate(row):
                                self.tblDataOutput.setItem(
                                    r, c, QTableWidgetItem(str(col))
                                )
                        last_row_count = len(rows)
                    else:
                        last_row_count = cur.rowcount
                        self.tblDataOutput.clear()
                        self.tblDataOutput.setRowCount(0)
                        self.tblDataOutput.setColumnCount(0)
                conn.commit()
                elapsed = perf_counter() - start_time
                self.txtMessages.setPlainText("Comando executado com sucesso.")
                self.status_bar.showMessage(
                    f"Concluído em {elapsed:.2f}s | Linhas afetadas: {last_row_count}"
                )
        except psycopg2.OperationalError as e:
            # Check if it's a connection loss error
            if "server closed the connection unexpectedly" in str(e) or "connection already closed" in str(e):
                self.append_message("Erro: Conexão com o servidor perdida. Verifique sua conexão de rede ou VPN.", "error")
                # Mark connection as closed to prevent further attempts to use it
                if hasattr(conn, 'closed'):
                    conn.closed = 1
            else:
                self.append_message(f"Erro na execução: {e}", "error")
                try:
                    if not getattr(conn, 'closed', True):
                        conn.rollback()
                except (psycopg2.InterfaceError, psycopg2.OperationalError):
                    # Connection already closed, nothing to rollback
                    pass
        except Exception as e:
            self.append_message(f"Erro na execução: {e}", "error")
            try:
                if not getattr(conn, 'closed', True):
                    conn.rollback()
            except (psycopg2.InterfaceError, psycopg2.OperationalError):
                # Connection already closed, nothing to rollback
                pass
        finally:
            # Only close the cursor if the connection is still open
            try:
                if not getattr(conn, 'closed', True) and cur is not None:
                    cur.close()
            except (psycopg2.InterfaceError, psycopg2.OperationalError):
                # Connection already closed, cannot close cursor
                pass

    def _set_font_size(self):
        font = QFont(self.txtSQL.font())
        font.setPointSize(self.font_size)
        self.txtSQL.setFont(font)
        self.tblDataOutput.setFont(font)
        self.txtMessages.setFont(font)

    def increase_font(self):
        self.font_size += 1
        self._set_font_size()

    def decrease_font(self):
        if self.font_size > 1:
            self.font_size -= 1
            self._set_font_size()
