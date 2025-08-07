from PyQt6.QtWidgets import (
    QWidget,
    QSplitter,
    QLineEdit,
    QListWidget,
    QTabWidget,
    QVBoxLayout,
    QDialog,
    QHBoxLayout,
    QToolBar,
    QPushButton,
    QLabel,
    QListWidgetItem,
    QInputDialog,
    QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from pathlib import Path
from config.permission_templates import DEFAULT_TEMPLATE
from .student_groups_dialog import StudentGroupsDialog


class UsersView(QWidget):
    def __init__(self, parent=None, controller=None):
        super().__init__(parent)
        assets_dir = Path(__file__).resolve().parents[2] / "assets"
        self.setWindowIcon(QIcon(str(assets_dir / "icone.png")))
        self.controller = controller
        self.setWindowTitle("Gerenciador de Usuários e Grupos")
        self._setup_ui()
        self._connect_signals()
        if self.controller:
            self.controller.data_changed.connect(self.refresh_lists)
        self.refresh_lists()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.toolbar = QToolBar()
        self.btnNewUser = QPushButton("Novo Usuário")
        self.btnBatchUsers = QPushButton("Inserir em Lote")
        self.btnNewGroup = QPushButton("Nova Turma")
        self.btnDelete = QPushButton("Excluir Selecionado")
        self.btnChangePassword = QPushButton("Alterar Senha")
        self.btnManageGroups = QPushButton("Gerir Turmas")
        self.btnDelete.setEnabled(False)
        self.btnChangePassword.setEnabled(False)
        self.btnManageGroups.setEnabled(False)
        self.toolbar.addWidget(self.btnNewUser)
        self.toolbar.addWidget(self.btnBatchUsers)
        self.toolbar.addWidget(self.btnNewGroup)
        self.toolbar.addWidget(self.btnDelete)
        self.toolbar.addWidget(self.btnChangePassword)
        self.toolbar.addWidget(self.btnManageGroups)
        layout.addWidget(self.toolbar)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.leftPanel = QWidget()
        leftLayout = QVBoxLayout(self.leftPanel)
        self.txtFilter = QLineEdit()
        self.txtFilter.setPlaceholderText("Buscar usuário ou grupo...")
        self.lstEntities = QListWidget()
        leftLayout.addWidget(self.txtFilter)
        leftLayout.addWidget(self.lstEntities)
        self.splitter.addWidget(self.leftPanel)
        self.rightPanel = QTabWidget()
        self.tabProperties = QWidget()
        self.tabMembers = QWidget()
        self.rightPanel.addTab(self.tabProperties, "Propriedades")
        self.rightPanel.addTab(self.tabMembers, "Membros de Grupo")
        self.splitter.addWidget(self.rightPanel)
        layout.addWidget(self.splitter)
        self.setLayout(layout)
        self.propLayout = QVBoxLayout(self.tabProperties)
        self.propLayout.addWidget(QLabel("Selecione um usuário ou grupo para ver detalhes."))

    def _connect_signals(self):
        self.txtFilter.textChanged.connect(self.filter_list)
        self.lstEntities.currentItemChanged.connect(self.on_entity_selected)
        self.btnNewUser.clicked.connect(self.on_new_user_clicked)
        self.btnBatchUsers.clicked.connect(self.on_new_user_batch_clicked)
        self.btnNewGroup.clicked.connect(self.on_new_group_clicked)
        self.btnDelete.clicked.connect(self.on_delete_item_clicked)
        self.btnChangePassword.clicked.connect(self.on_change_password_clicked)
        self.btnManageGroups.clicked.connect(self.on_manage_groups_clicked)

    def refresh_lists(self):
        self.lstEntities.clear()
        if not self.controller:
            return
        try:
            users, groups = self.controller.list_entities()
            for user in users:
                item = QListWidgetItem(f"👤 {user}")
                item.setData(Qt.ItemDataRole.UserRole, ("user", user))
                self.lstEntities.addItem(item)
            for group in groups:
                item = QListWidgetItem(f"👥 {group}")
                item.setData(Qt.ItemDataRole.UserRole, ("group", group))
                self.lstEntities.addItem(item)
        except Exception as e:
            QMessageBox.critical(self, "Erro de Listagem", f"Não foi possível listar usuários ou grupos: {e}")

    def filter_list(self):
        filter_text = self.txtFilter.text().lower()
        for i in range(self.lstEntities.count()):
            item = self.lstEntities.item(i)
            item.setHidden(filter_text not in item.text().lower())

    def on_entity_selected(self, current, previous):
        while self.propLayout.count():
            child = self.propLayout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        if not current:
            self.propLayout.addWidget(QLabel("Selecione um usuário ou grupo para ver detalhes."))
            self.btnChangePassword.setEnabled(False)
            self.btnDelete.setEnabled(False)
            self.btnManageGroups.setEnabled(False)
            return
        entity_type, entity_name = current.data(Qt.ItemDataRole.UserRole)
        self.propLayout.addWidget(QLabel(f"Nome: {entity_name}"))
        self.propLayout.addWidget(QLabel(f"Tipo: {entity_type.capitalize()}"))
        is_user = (entity_type == 'user')
        self.btnChangePassword.setEnabled(is_user)
        self.btnDelete.setEnabled(True)
        self.btnManageGroups.setEnabled(is_user)

    def on_new_user_clicked(self):
        username, ok1 = QInputDialog.getText(self, "Novo Usuário", "Digite o nome do novo usuário:")
        if ok1 and username:
            username = username.lower()
        else: return
        password, ok2 = QInputDialog.getText(self, "Nova Senha", f"Senha para '{username}':", QLineEdit.EchoMode.Password)
        if not ok2 or not password:
            return
        valid_until, ok3 = QInputDialog.getText(
            self,
            "Validade",
            "Data de expiração (YYYY-MM-DD) - deixe em branco para nenhuma:",
        )
        if not ok3:
            return
        valid_until = valid_until.strip() or None
        try:
            self.controller.create_user(username, password, valid_until)
            QMessageBox.information(self, "Sucesso", f"Usuário '{username}' criado com sucesso!")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível criar o usuário.\nMotivo: {e}")

    def on_new_user_batch_clicked(self):
        text, ok = QInputDialog.getMultiLineText(
            self,
            "Inserir Usuários em Lote",
            "Informe um usuário por linha no formato 'usuario,senha[,YYYY-MM-DD]':",
        )
        if not ok or not text.strip():
            return
        users_data = []
        for line in text.splitlines():
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 2:
                continue
            username, password = parts[0].lower(), parts[1]
            valid_until = parts[2] if len(parts) > 2 and parts[2] else None
            users_data.append((username, password, valid_until))
        if not users_data:
            QMessageBox.warning(self, "Aviso", "Nenhum usuário válido informado.")
            return
        try:
            created = self.controller.create_users_batch(users_data)
            QMessageBox.information(
                self, "Sucesso", f"{len(created)} usuários criados com sucesso!"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Erro",
                f"Falha ao inserir usuários em lote.\nMotivo: {e}",
            )

    def on_new_group_clicked(self):
        group_name, ok = QInputDialog.getText(
            self,
            "Nova Turma",
            "Nome da turma (deve começar com 'grp_'):",
            QLineEdit.EchoMode.Normal,
            "grp_",
        )
        if not ok or not group_name:
            return
        group_name = group_name.strip()
        if not group_name.startswith("grp_"):
            QMessageBox.warning(self, "Erro", "Nome da turma deve começar com 'grp_'.")
            return
        try:
            self.controller.create_group(group_name)
            self.controller.apply_template_to_group(group_name, DEFAULT_TEMPLATE)
            QMessageBox.information(self, "Sucesso", f"Turma '{group_name}' criada com sucesso!")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível criar a turma.\nMotivo: {e}")

    def on_delete_item_clicked(self):
        current_item = self.lstEntities.currentItem()
        if not current_item:
            return
        entity_type, entity_name = current_item.data(Qt.ItemDataRole.UserRole)
        if entity_type == 'group':
            self.on_delete_group_clicked(entity_name)
            return
        reply = QMessageBox.question(
            self,
            "Confirmar Deleção",
            f"Tem certeza que deseja deletar o {entity_type} '{entity_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                success = self.controller.delete_user(entity_name)
                if success:
                    QMessageBox.information(
                        self,
                        "Sucesso",
                        f"{entity_type.capitalize()} '{entity_name}' deletado com sucesso.",
                    )
                else:
                    QMessageBox.critical(
                        self,
                        "Erro",
                        "Ocorreu um erro ao deletar o item. Verifique os logs.",
                    )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Erro",
                    f"Não foi possível deletar o item.\nMotivo: {e}",
                )

    def on_delete_group_clicked(self, group_name: str):
        dialog = QDialog(self)
        dialog.setWindowTitle("Confirmar Deleção")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"Como deseja excluir a turma '{group_name}'?"))
        btn_all = QPushButton("Apagar Turma e Alunos")
        btn_group = QPushButton("Apagar Apenas a Turma")
        btn_cancel = QPushButton("Cancelar")
        btn_all.clicked.connect(lambda: dialog.done(1))
        btn_group.clicked.connect(lambda: dialog.done(2))
        btn_cancel.clicked.connect(lambda: dialog.done(0))
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(btn_all)
        btn_layout.addWidget(btn_group)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        choice = dialog.exec()
        success = False
        if choice == 1:
            success = self.controller.delete_group_and_members(group_name)
            msg_success = f"Turma '{group_name}' e alunos deletados com sucesso."
        elif choice == 2:
            success = self.controller.delete_group(group_name)
            msg_success = f"Turma '{group_name}' deletada com sucesso."
        else:
            return
        if success:
            QMessageBox.information(self, "Sucesso", msg_success)
        else:
            QMessageBox.critical(
                self,
                "Erro",
                "Ocorreu um erro ao deletar o item. Verifique os logs.",
            )

    def on_change_password_clicked(self):
        current_item = self.lstEntities.currentItem()
        if not current_item: return
        entity_type, username = current_item.data(Qt.ItemDataRole.UserRole)
        if entity_type != 'user': return
        password, ok = QInputDialog.getText(self, "Alterar Senha", f"Nova senha para '{username}':", QLineEdit.EchoMode.Password)
        if ok and password:
            try:
                self.controller.change_password(username, password)
                QMessageBox.information(self, "Sucesso", "Senha alterada com sucesso!")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Não foi possível alterar a senha.\nMotivo: {e}")

    def on_manage_groups_clicked(self):
        current_item = self.lstEntities.currentItem()
        if not current_item:
            return
        entity_type, username = current_item.data(Qt.ItemDataRole.UserRole)
        if entity_type != 'user':
            return
        dialog = StudentGroupsDialog(self, controller=self.controller, username=username)
        dialog.exec()

