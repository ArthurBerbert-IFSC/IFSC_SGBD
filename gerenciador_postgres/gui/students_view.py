from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QToolBar,
    QPushButton,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QMessageBox,
    QInputDialog,
)
from PyQt6.QtCore import Qt


class StudentsView(QWidget):
    """Interface básica para gestão individual de alunos (usuários)."""

    def __init__(self, parent=None, controller=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Gestão de Alunos")
        self._setup_ui()
        self._connect_signals()
        if self.controller:
            self.controller.data_changed.connect(self.refresh_list)
        self.refresh_list()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.toolbar = QToolBar()
        self.btnNewUser = QPushButton("Novo Usuário")
        self.btnDelete = QPushButton("Excluir Selecionado")
        self.btnChangePassword = QPushButton("Alterar Senha")
        self.btnDelete.setEnabled(False)
        self.btnChangePassword.setEnabled(False)
        self.toolbar.addWidget(self.btnNewUser)
        self.toolbar.addWidget(self.btnDelete)
        self.toolbar.addWidget(self.btnChangePassword)
        layout.addWidget(self.toolbar)

        self.txtFilter = QLineEdit()
        self.txtFilter.setPlaceholderText("Buscar aluno...")
        layout.addWidget(self.txtFilter)

        self.lstUsers = QListWidget()
        layout.addWidget(self.lstUsers)

        self.infoLabel = QLabel("Selecione um aluno para ver detalhes.")
        layout.addWidget(self.infoLabel)

        self.setLayout(layout)

    def _connect_signals(self):
        self.txtFilter.textChanged.connect(self.filter_list)
        self.lstUsers.currentItemChanged.connect(self.on_user_selected)
        self.btnNewUser.clicked.connect(self.on_new_user_clicked)
        self.btnDelete.clicked.connect(self.on_delete_user_clicked)
        self.btnChangePassword.clicked.connect(self.on_change_password_clicked)

    def refresh_list(self):
        self.lstUsers.clear()
        if not self.controller:
            return
        try:
            users, _ = self.controller.list_entities()
            for user in users:
                item = QListWidgetItem(user)
                item.setData(Qt.ItemDataRole.UserRole, user)
                self.lstUsers.addItem(item)
        except Exception as e:
            QMessageBox.critical(self, "Erro de Listagem", f"Não foi possível listar usuários: {e}")

    def filter_list(self):
        filter_text = self.txtFilter.text().lower()
        for i in range(self.lstUsers.count()):
            item = self.lstUsers.item(i)
            item.setHidden(filter_text not in item.text().lower())

    def on_user_selected(self, current, previous):
        if not current:
            self.infoLabel.setText("Selecione um aluno para ver detalhes.")
            self.btnChangePassword.setEnabled(False)
            self.btnDelete.setEnabled(False)
            return
        username = current.data(Qt.ItemDataRole.UserRole)
        self.infoLabel.setText(f"Aluno: {username}")
        self.btnChangePassword.setEnabled(True)
        self.btnDelete.setEnabled(True)

    def on_new_user_clicked(self):
        username, ok1 = QInputDialog.getText(self, "Novo Aluno", "Digite o nome do novo aluno:")
        if ok1 and username:
            username = username.lower()
        else:
            return
        password, ok2 = QInputDialog.getText(
            self,
            "Nova Senha",
            f"Senha para '{username}':",
            QLineEdit.EchoMode.Password,
        )
        if not ok2 or not password:
            return
        try:
            self.controller.create_user(username, password)
            QMessageBox.information(
                self, "Sucesso", f"Aluno '{username}' criado com sucesso!"
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Erro", f"Não foi possível criar o aluno.\nMotivo: {e}"
            )

    def on_delete_user_clicked(self):
        current_item = self.lstUsers.currentItem()
        if not current_item:
            return
        username = current_item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(
            self,
            "Confirmar Deleção",
            f"Tem certeza que deseja deletar o aluno '{username}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                success = self.controller.delete_user(username)
                if success:
                    QMessageBox.information(
                        self, "Sucesso", f"Aluno '{username}' deletado com sucesso."
                    )
                else:
                    QMessageBox.critical(
                        self,
                        "Erro",
                        "Ocorreu um erro ao deletar o aluno. Verifique os logs.",
                    )
            except Exception as e:
                QMessageBox.critical(
                    self, "Erro", f"Não foi possível deletar o aluno.\nMotivo: {e}"
                )

    def on_change_password_clicked(self):
        current_item = self.lstUsers.currentItem()
        if not current_item:
            return
        username = current_item.data(Qt.ItemDataRole.UserRole)
        password, ok = QInputDialog.getText(
            self,
            "Alterar Senha",
            f"Nova senha para '{username}':",
            QLineEdit.EchoMode.Password,
        )
        if ok and password:
            try:
                self.controller.change_password(username, password)
                QMessageBox.information(
                    self, "Sucesso", "Senha alterada com sucesso!"
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Erro", f"Não foi possível alterar a senha.\nMotivo: {e}"
                )
