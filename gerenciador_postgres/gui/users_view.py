from PyQt6.QtWidgets import (QWidget, QSplitter, QLineEdit, QListWidget, QTabWidget,
                             QVBoxLayout, QToolBar, QPushButton, QLabel, QListWidgetItem,
                             QInputDialog, QMessageBox)
from PyQt6.QtCore import Qt
from ..settings import APP_NAME

class UsersView(QWidget):
    def __init__(self, parent=None, role_manager=None):
        super().__init__(parent)
        self.role_manager = role_manager
        self.setWindowTitle(f"Gerenciador de Usuários e Grupos - {APP_NAME}")
        self._setup_ui()
        self._connect_signals()
        self.refresh_lists()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.toolbar = QToolBar()
        self.btnNewUser = QPushButton("Novo Usuário")
        self.btnNewGroup = QPushButton("Novo Grupo")
        self.btnDelete = QPushButton("Excluir Selecionado")
        self.btnChangePassword = QPushButton("Alterar Senha")
        self.btnDelete.setEnabled(False)
        self.btnChangePassword.setEnabled(False)
        self.toolbar.addWidget(self.btnNewUser)
        self.toolbar.addWidget(self.btnNewGroup)
        self.toolbar.addWidget(self.btnDelete)
        self.toolbar.addWidget(self.btnChangePassword)
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
        self.btnNewGroup.clicked.connect(self.on_new_group_clicked)
        self.btnDelete.clicked.connect(self.on_delete_item_clicked)
        self.btnChangePassword.clicked.connect(self.on_change_password_clicked)

    def refresh_lists(self):
        self.lstEntities.clear()
        if not self.role_manager: return
        try:
            users = self.role_manager.list_users()
            for user in users:
                item = QListWidgetItem(f"👤 {user}")
                item.setData(Qt.ItemDataRole.UserRole, ('user', user))
                self.lstEntities.addItem(item)
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, f"Não foi possível listar usuários: {e}")
        try:
            groups = self.role_manager.list_groups()
            for group in groups:
                item = QListWidgetItem(f"👥 {group}")
                item.setData(Qt.ItemDataRole.UserRole, ('group', group))
                self.lstEntities.addItem(item)
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, f"Não foi possível listar grupos: {e}")

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
            return
        entity_type, entity_name = current.data(Qt.ItemDataRole.UserRole)
        self.propLayout.addWidget(QLabel(f"Nome: {entity_name}"))
        self.propLayout.addWidget(QLabel(f"Tipo: {entity_type.capitalize()}"))
        is_user = (entity_type == 'user')
        self.btnChangePassword.setEnabled(is_user)
        self.btnDelete.setEnabled(True)

    def on_new_user_clicked(self):
        username, ok1 = QInputDialog.getText(
            self, f"Novo Usuário - {APP_NAME}", "Digite o nome do novo usuário:"
        )
        if ok1 and username:
            username = username.lower()
        else: return
        password, ok2 = QInputDialog.getText(
            self, f"Nova Senha - {APP_NAME}", f"Senha para '{username}':", QLineEdit.EchoMode.Password
        )
        if not ok2 or not password: return
        try:
            self.role_manager.create_user(username, password)
            QMessageBox.information(self, APP_NAME, f"Usuário '{username}' criado com sucesso!")
            self.refresh_lists()
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, f"Não foi possível criar o usuário.\nMotivo: {e}")

    def on_new_group_clicked(self):
        group_name, ok = QInputDialog.getText(
            self, f"Novo Grupo - {APP_NAME}", "Digite o nome do novo grupo (deve começar com 'grp_'):"
        )
        if not ok or not group_name: return
        try:
            self.role_manager.create_group(group_name)
            QMessageBox.information(self, APP_NAME, f"Grupo '{group_name}' criado com sucesso!")
            self.refresh_lists()
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, f"Não foi possível criar o grupo.\nMotivo: {e}")

    def on_delete_item_clicked(self):
        current_item = self.lstEntities.currentItem()
        if not current_item: return
        entity_type, entity_name = current_item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(self, APP_NAME, f"Tem certeza que deseja deletar o {entity_type} '{entity_name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                success = False
                if entity_type == 'user':
                    success = self.role_manager.delete_user(entity_name)
                elif entity_type == 'group':
                    success = self.role_manager.delete_group(entity_name)

                if success:
                    QMessageBox.information(self, APP_NAME, f"{entity_type.capitalize()} '{entity_name}' deletado com sucesso.")
                    self.refresh_lists()
                else:
                    QMessageBox.critical(self, APP_NAME, f"Ocorreu um erro ao deletar o item. Verifique os logs.")
            except Exception as e:
                QMessageBox.critical(self, APP_NAME, f"Não foi possível deletar o item.\nMotivo: {e}")

    def on_change_password_clicked(self):
        current_item = self.lstEntities.currentItem()
        if not current_item: return
        entity_type, username = current_item.data(Qt.ItemDataRole.UserRole)
        if entity_type != 'user': return
        password, ok = QInputDialog.getText(
            self, f"Alterar Senha - {APP_NAME}", f"Nova senha para '{username}':", QLineEdit.EchoMode.Password
        )
        if ok and password:
            try:
                self.role_manager.change_password(username, password)
                QMessageBox.information(self, APP_NAME, "Senha alterada com sucesso!")
            except Exception as e:
                 QMessageBox.critical(self, APP_NAME, f"Não foi possível alterar a senha.\nMotivo: {e}")