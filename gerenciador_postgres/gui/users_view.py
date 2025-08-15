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
)


class UserTableModel(QAbstractTableModel):
    """Modelo simples para exibir usuários em uma QTableView."""

    def __init__(self, users: list[str] | None = None) -> None:
        super().__init__()
        self._users = users or []

    # --- Métodos obrigatórios do QAbstractTableModel ---------------------
    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self._users)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return 1

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        return self._users[index.row()]

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return "Usuário"
        return None

    # --- Métodos auxiliares ----------------------------------------------
    def set_users(self, users: list[str]) -> None:
        self.beginResetModel()
        self._users = list(users)
        self.endResetModel()

    def user_at(self, row: int) -> str:
        return self._users[row]


class UserDialog(QDialog):
    """Diálogo simples para criação/edição de usuário."""

    def __init__(self, parent: QWidget | None = None, username: str = "", valid_until: str | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Usuário")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.txtUsername = QLineEdit(username)
        form.addRow("Usuário:", self.txtUsername)
        self.txtPassword = QLineEdit()
        self.txtPassword.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Senha:", self.txtPassword)
        self.chkValid = QCheckBox("Definir data de expiração")
        self.dateEdit = QDateEdit()
        self.dateEdit.setCalendarPopup(True)
        self.dateEdit.setEnabled(False)
        if valid_until:
            self.chkValid.setChecked(True)
            self.dateEdit.setEnabled(True)
            try:
                y, m, d = map(int, valid_until.split("-"))
                self.dateEdit.setDate(QDate(y, m, d))
            except Exception:
                self.dateEdit.setDate(QDate.currentDate())
        else:
            self.dateEdit.setDate(QDate.currentDate())
        form.addRow(self.chkValid)
        form.addRow("Validade:", self.dateEdit)
        self.chkValid.toggled.connect(self.dateEdit.setEnabled)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

    def get_data(self) -> tuple[str, str, str | None]:
        username = self.txtUsername.text().strip()
        password = self.txtPassword.text()
        valid_until = None
        if self.chkValid.isChecked():
            valid_until = self.dateEdit.date().toString("yyyy-MM-dd")
        return username, password, valid_until


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

    def get_data(self) -> list[tuple[str, str]]:
        users: list[tuple[str, str]] = []
        for line in self.txt.toPlainText().splitlines():
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

