from __future__ import annotations

from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QDate
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QSplitter,
    QListWidget,
    QStackedWidget,
    QTableView,
    QHeaderView,
    QAbstractItemView,
    QPushButton,
    QDialog,
    QLineEdit,
    QFormLayout,
    QDialogButtonBox,
    QTextEdit,
    QMessageBox,
    QCheckBox,
    QDateEdit,
    QTextEdit,
    QDialogButtonBox,
    QComboBox,
    QFileDialog,
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QIcon
from pathlib import Path
from PyPDF2 import PdfReader
import re
import logging
try:
    # Reutiliza lógica mais robusta já existente; captura também SystemExit lançado pelo script
    from tools.extract_alunos_pdf import extract_alunos_from_pdf  # type: ignore
except BaseException:  # inclui SystemExit
    extract_alunos_from_pdf = None  # type: ignore


class BatchUserDialog(QDialog):
    """Diálogo para inserção de usuários em lote."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Adicionar Usuários em Lote")

        layout = QVBoxLayout(self)
        self.txt = QTextEdit()
        layout.addWidget(self.txt)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.btnImportPDF.clicked.connect(self.import_from_pdf)

    def import_from_pdf(self):
        """Abre um seletor, tenta extrair (usando extrator dedicado se disponível) e preenche a caixa."""
        file_name, _ = QFileDialog.getOpenFileName(self, "Selecionar PDF", "", "Arquivos PDF (*.pdf)")
        if not file_name:
            return
        try:
            logging.getLogger(__name__).info("Importando alunos de PDF: %s", file_name)
            lines_output = []
            # Caminho 1: usar extrator robusto baseado em pdfplumber, se importado
            if extract_alunos_from_pdf:
                try:
                    alunos = extract_alunos_from_pdf(file_name)
                except Exception as e:
                    logging.getLogger(__name__).warning("Falha extrator pdfplumber: %s", e)
                    alunos = []
                for item in alunos:
                    lines_output.append(f"{item['matricula']} {item['nome']}")

            # Caminho 2 (fallback) se nada encontrado ou extrator indisponível: usar PyPDF2 + regex flexível
            if not lines_output:
                reader = PdfReader(file_name)
                text_lines = []
                for page in reader.pages:
                    text = page.extract_text() or ""
                    text_lines.extend(text.splitlines())
                # Aceita formatos:
                #  a) <seq> <matricula> <nome>
                #  b) <matricula> <nome>
                #  c) <matricula> - <nome>
                #  d) <matricula>\t<nome>
                pat = re.compile(r"^(?:\d+\s+)?(\d{4,})[\s\-\t]+(.+)$")
                for line in text_lines:
                    m = pat.match(line.strip())
                    if not m:
                        continue
                    matricula, nome = m.group(1), m.group(2).strip()
                    # Heurística para descartar cabeçalhos
                    if re.search(r"nome|aluno|discente", nome, re.IGNORECASE):
                        continue
                    lines_output.append(f"{matricula} {nome}")

            if not lines_output:
                QMessageBox.warning(self, "Nenhum Aluno Encontrado", "Não foi possível encontrar dados de alunos no PDF.")
                return
            # Remove duplicados preservando ordem
            seen = set()
            dedup = []
            for ln in lines_output:
                key = ln.lower()
                if key not in seen:
                    seen.add(key)
                    dedup.append(ln)
            self.txt.setPlainText("\n".join(dedup))
            QMessageBox.information(self, "Sucesso", f"{len(dedup)} alunos importados.")
        except Exception as e:
            logging.getLogger(__name__).exception("Erro ao processar PDF")
            QMessageBox.critical(self, "Erro ao Ler PDF", f"Não foi possível processar o arquivo PDF.\nErro: {e}")

    def get_data(self):
        text = self.txt.toPlainText()
        users_data = []
        for idx, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            parts = line.strip().split(maxsplit=1)
            if len(parts) == 2:
                users.append((parts[0], parts[1]))
        if not users:
            raise ValueError("Nenhum usuário informado")
        return users


class UsersView(QWidget):
    """Tela principal para gerenciamento de usuários."""

    def __init__(self, parent: QWidget | None = None, controller=None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._setup_ui()
        if self.controller:
            self.controller.data_changed.connect(self.load_users)
        self.load_users()

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.splitter)

        # Navegação à esquerda
        self.navList = QListWidget()
        self.navList.addItem("Gerenciar Usuários")
        self.navList.addItem("Ações em Lote")
        self.splitter.addWidget(self.navList)

        # Área de páginas à direita
        self.stack = QStackedWidget()
        self.splitter.addWidget(self.stack)

        self.manage_page = self.create_manage_users_page()
        self.batch_page = self.create_batch_actions_page()
        self.stack.addWidget(self.manage_page)
        self.stack.addWidget(self.batch_page)

        self.navList.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.navList.setCurrentRow(0)

    def create_manage_users_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.table = QTableView()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.model = UserTableModel()
        self.table.setModel(self.model)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        self.btnAdd = QPushButton("Adicionar")
        self.btnEdit = QPushButton("Editar")
        self.btnRemove = QPushButton("Remover")
        btn_layout.addWidget(self.btnAdd)
        btn_layout.addWidget(self.btnEdit)
        btn_layout.addWidget(self.btnRemove)
        layout.addLayout(btn_layout)

        self.btnAdd.clicked.connect(self.add_user)
        self.btnEdit.clicked.connect(self.edit_user)
        self.btnRemove.clicked.connect(self.delete_user)
        return page

    def create_batch_actions_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.btnBatchAdd = QPushButton("Adicionar Usuários em Lote")
        layout.addWidget(self.btnBatchAdd)
        layout.addStretch()
        self.btnBatchAdd.clicked.connect(self.add_user_batch)
        return page

    # ------------------------------------------------------------------
    # Operações
    # ------------------------------------------------------------------
    def load_users(self) -> None:
        if not self.controller:
            self.model.set_users([])
            return
        try:
            users = self.controller.list_users()
        except Exception as e:  # pragma: no cover - interface
            QMessageBox.critical(self, "Erro", f"Não foi possível listar usuários: {e}")
            users = []
        self.model.set_users(users)

    def _current_username(self) -> str | None:
        index = self.table.currentIndex()
        if not index.isValid():
            return None
        return self.model.user_at(index.row())

    def add_user(self) -> None:
        dlg = UserDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        username, password, valid_until = dlg.get_data()
        if not username or not password:
            return
        try:
            self.controller.create_user(username, password, valid_until)
            self.load_users()
        except Exception as e:  # pragma: no cover - interface
            QMessageBox.critical(self, "Erro", str(e))

    def edit_user(self) -> None:
        username = self._current_username()
        if not username:
            return
        user = None
        if self.controller:
            try:
                user = self.controller.get_user(username)
            except Exception:
                pass
        valid_until = user.valid_until.strftime("%Y-%m-%d") if getattr(user, "valid_until", None) else None
        dlg = UserDialog(self, username, valid_until)
        dlg.txtUsername.setEnabled(False)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        _username, password, new_valid = dlg.get_data()
        try:
            if password:
                self.controller.change_password(username, password)
            if new_valid:
                self.controller.renew_user_validity(username, new_valid)
            self.load_users()
        except Exception as e:  # pragma: no cover - interface
            QMessageBox.critical(self, "Erro", str(e))

    def delete_user(self) -> None:
        username = self._current_username()
        if not username:
            return
        reply = QMessageBox.question(
            self,
            "Confirmar",
            f"Remover usuário '{username}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.controller.delete_user(username)
            self.load_users()
        except Exception as e:  # pragma: no cover - interface
            QMessageBox.critical(self, "Erro", str(e))

    def add_user_batch(self) -> None:
        dlg = BatchUserDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            users = dlg.get_data()
        except ValueError as e:
            QMessageBox.warning(self, "Erro", str(e))
            return
        try:
            self.controller.create_users_batch(users)
            self.load_users()
        except Exception as e:  # pragma: no cover - interface
            QMessageBox.critical(self, "Erro", str(e))

