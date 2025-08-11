from PyQt6.QtWidgets import (
    QWidget,
    QSplitter,
    QLineEdit,
    QListWidget,
    QVBoxLayout,
    QDialog,
    QHBoxLayout,
    QToolBar,
    QPushButton,
    QLabel,
    QListWidgetItem,
    QInputDialog,
    QMessageBox,
    QCheckBox,
    QDateEdit,
    QTextEdit,
    QDialogButtonBox,
    QComboBox,
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QIcon
from pathlib import Path


class BatchUserDialog(QDialog):
    def __init__(self, parent=None, controller=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Inserir Usuários em Lote")

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Cole a lista de alunos no formato: número matrícula nome completo (um por linha)"
            )
        )

        self.txt = QTextEdit()
        layout.addWidget(self.txt)

        layout.addWidget(QLabel("Turma"))
        self.cmbGroups = QComboBox()
        if controller:
            self.cmbGroups.addItems(controller.list_groups())
        self.cmbGroups.addItem("-- Criar nova turma --")
        layout.addWidget(self.cmbGroups)

        self.chk = QCheckBox("Definir data de expiração para todos")
        layout.addWidget(self.chk)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setEnabled(False)
        self.chk.toggled.connect(self.date_edit.setEnabled)
        layout.addWidget(self.date_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

    def get_data(self):
        text = self.txt.toPlainText()
        users_data = []
        for idx, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            parts = line.strip().split(maxsplit=2)
            if len(parts) < 3:
                raise ValueError(f"Linha {idx} inválida: '{line}'")
            users_data.append((parts[1], parts[2]))
        if not users_data:
            raise ValueError("Nenhum usuário válido informado.")
        valid_until = (
            self.date_edit.date().toString("yyyy-MM-dd") if self.chk.isChecked() else None
        )
        group_name = self.cmbGroups.currentText()
        if group_name == "-- Criar nova turma --":
            group_name, ok = QInputDialog.getText(
                self,
                "Nova Turma",
                "Digite o nome da nova turma (o prefixo 'grp_' será adicionado automaticamente):",
            )
            if not ok or not group_name.strip():
                raise ValueError("Nome da turma inválido.")
            group_name = group_name.strip()
            if not group_name.lower().startswith("grp_"):
                group_name = f"grp_{group_name.lower()}"
        return users_data, valid_until, group_name


class UsersView(QWidget):
    def __init__(self, parent=None, controller=None):
        super().__init__(parent)
        assets_dir = Path(__file__).resolve().parents[2] / "assets"
        self.setWindowIcon(QIcon(str(assets_dir / "icone.png")))
        self.controller = controller
        self.setWindowTitle("Gerenciador de Usuários")
        # Controle de UX
        self._select_username_on_refresh = None
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
        self.btnDelete = QPushButton("Excluir Selecionado")
        self.btnChangePassword = QPushButton("Alterar Senha")
        # Widgets para renovação de validade
        self.renewDateEdit = QDateEdit()
        self.renewDateEdit.setCalendarPopup(True)
        self.renewDateEdit.setDate(QDate.currentDate())
        self.btnRenew = QPushButton("Renovar")
        self.btnRenew.setEnabled(False)
        self.renewDateEdit.setEnabled(False)
        self.btnDelete.setEnabled(False)
        self.btnChangePassword.setEnabled(False)
        self.toolbar.addWidget(self.btnNewUser)
        self.toolbar.addWidget(self.btnBatchUsers)
        self.toolbar.addWidget(self.btnDelete)
        self.toolbar.addWidget(self.btnChangePassword)
        self.toolbar.addWidget(self.renewDateEdit)
        self.toolbar.addWidget(self.btnRenew)
        layout.addWidget(self.toolbar)
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.topPanel = QWidget()
        leftLayout = QVBoxLayout(self.topPanel)
        self.txtFilter = QLineEdit()
        self.txtFilter.setPlaceholderText("Buscar usuário...")
        self.lstEntities = QListWidget()
        leftLayout.addWidget(self.txtFilter)
        leftLayout.addWidget(self.lstEntities)
        self.splitter.addWidget(self.topPanel)

        # Bottom panel with details and group management
        self.bottomPanel = QWidget()
        bottomLayout = QVBoxLayout(self.bottomPanel)
        self.detailSplitter = QSplitter(Qt.Orientation.Horizontal)

        # Details section
        self.detailSection = QWidget()
        self.propLayout = QVBoxLayout(self.detailSection)
        self.propLayout.addWidget(QLabel("Selecione um usuário para ver detalhes."))
        self.detailSplitter.addWidget(self.detailSection)

        # Group management section
        self.groupSection = QWidget()
        groupLayout = QVBoxLayout(self.groupSection)
        lists_layout = QHBoxLayout()

        left_groups_layout = QVBoxLayout()
        left_groups_layout.addWidget(QLabel("Turmas do Aluno"))
        self.lstUserGroups = QListWidget()
        left_groups_layout.addWidget(self.lstUserGroups)
        lists_layout.addLayout(left_groups_layout)

        btns_layout = QVBoxLayout()
        self.btnAddGroup = QPushButton("<- Adicionar")
        self.btnRemoveGroup = QPushButton("Remover ->")
        self.btnAddGroup.setEnabled(False)
        self.btnRemoveGroup.setEnabled(False)
        btns_layout.addStretch()
        btns_layout.addWidget(self.btnAddGroup)
        btns_layout.addWidget(self.btnRemoveGroup)
        btns_layout.addStretch()
        lists_layout.addLayout(btns_layout)

        right_groups_layout = QVBoxLayout()
        right_groups_layout.addWidget(QLabel("Turmas Disponíveis"))
        self.lstAvailableGroups = QListWidget()
        right_groups_layout.addWidget(self.lstAvailableGroups)
        lists_layout.addLayout(right_groups_layout)

        groupLayout.addLayout(lists_layout)
        self.groupSection.setLayout(groupLayout)
        self.detailSplitter.addWidget(self.groupSection)

        bottomLayout.addWidget(self.detailSplitter)
        self.splitter.addWidget(self.bottomPanel)

        layout.addWidget(self.splitter)

        # Apenas botão Fechar: todas as operações já são aplicadas imediatamente
        # pelos controllers/managers. Não há um "Salvar" aqui.
        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        layout.addWidget(self.buttonBox)

        self.setLayout(layout)

    def _connect_signals(self):
        self.txtFilter.textChanged.connect(self.filter_list)
        self.lstEntities.currentItemChanged.connect(self.on_entity_selected)
        self.btnNewUser.clicked.connect(self.on_new_user_clicked)
        self.btnBatchUsers.clicked.connect(self.on_new_user_batch_clicked)
        self.btnDelete.clicked.connect(self.on_delete_user_clicked)
        self.btnChangePassword.clicked.connect(self.on_change_password_clicked)
        self.btnRenew.clicked.connect(self.on_renew_clicked)
        self.btnAddGroup.clicked.connect(self.on_add_group_clicked)
        self.btnRemoveGroup.clicked.connect(self.on_remove_group_clicked)
        # Close fecha a janela; conectar diretamente o botão Close
        close_btn = self.buttonBox.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.clicked.connect(self.close)
        else:
            # Fallback defensivo
            self.buttonBox.rejected.connect(self.close)
            self.buttonBox.accepted.connect(self.close)

    def refresh_lists(self):
        # Preserva seleção e posição de scroll atuais
        selected_username = None
        current_item = self.lstEntities.currentItem()
        if current_item:
            selected_username = current_item.data(Qt.ItemDataRole.UserRole)
        current_row = self.lstEntities.currentRow()
        scroll_val = self.lstEntities.verticalScrollBar().value()

        self.lstEntities.clear()
        if not self.controller:
            return
        try:
            for user in self.controller.list_users():
                item = QListWidgetItem(f"👤 {user}")
                item.setData(Qt.ItemDataRole.UserRole, user)
                self.lstEntities.addItem(item)
            # Definir alvo de seleção: 1) seleção solicitada; 2) usuário anterior; 3) índice próximo
            target_username = self._select_username_on_refresh or selected_username
            selected = False
            if target_username is not None:
                for i in range(self.lstEntities.count()):
                    it = self.lstEntities.item(i)
                    if it.data(Qt.ItemDataRole.UserRole) == target_username:
                        self.lstEntities.setCurrentItem(it)
                        selected = True
                        break
            if not selected and self.lstEntities.count() > 0:
                # Seleciona linha próxima do índice anterior
                target_row = current_row if 0 <= current_row < self.lstEntities.count() else self.lstEntities.count() - 1
                self.lstEntities.setCurrentRow(target_row)

            # Restaurar scroll
            self.lstEntities.verticalScrollBar().setValue(scroll_val)

            # Limpa seleção pendente específica
            self._select_username_on_refresh = None
        except Exception as e:
            QMessageBox.critical(self, "Erro de Listagem", f"Não foi possível listar usuários: {e}")

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
        self.lstUserGroups.clear()
        self.lstAvailableGroups.clear()
        self.btnAddGroup.setEnabled(False)
        self.btnRemoveGroup.setEnabled(False)
        self.btnRenew.setEnabled(False)
        self.renewDateEdit.setEnabled(False)

        if not current:
            self.propLayout.addWidget(QLabel("Selecione um usuário para ver detalhes."))
            self.btnChangePassword.setEnabled(False)
            self.btnDelete.setEnabled(False)
            return

        username = current.data(Qt.ItemDataRole.UserRole)
        user_details = self.controller.get_user(username) if self.controller else None
        if user_details:
            details_text = f"<b>Usuário:</b> {user_details.username}"
            if user_details.valid_until:
                details_text += f"<br><b>Expira em:</b> {user_details.valid_until.strftime('%d/%m/%Y')}"
            self.lblUserDetails = QLabel(details_text)
            self.propLayout.addWidget(self.lblUserDetails)
        else:
            self.propLayout.addWidget(QLabel(f"Nome: {username}"))
        self.btnChangePassword.setEnabled(True)
        self.btnDelete.setEnabled(True)
        self.btnRenew.setEnabled(True)
        self.renewDateEdit.setEnabled(True)

        if user_details and getattr(user_details, "valid_until", None):
            dt = user_details.valid_until
            self.renewDateEdit.setDate(QDate(dt.year, dt.month, dt.day))
        else:
            self.renewDateEdit.setDate(QDate.currentDate())

        self._update_group_lists(username)

    def on_new_user_clicked(self):
        username, ok1 = QInputDialog.getText(
            self, "Novo Usuário", "Digite o nome do novo usuário:"
        )
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

        dlg = QDialog(self)
        dlg.setWindowTitle("Validade do Usuário")
        vlayout = QVBoxLayout(dlg)
        chk = QCheckBox("Definir data de expiração")
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDate(QDate.currentDate())
        date_edit.setEnabled(False)
        chk.toggled.connect(date_edit.setEnabled)
        vlayout.addWidget(chk)
        vlayout.addWidget(date_edit)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        vlayout.addWidget(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        valid_until = (
            date_edit.date().toString("yyyy-MM-dd") if chk.isChecked() else None
        )
        try:
            self.controller.create_user(username, password, valid_until)
            # Selecionar o usuário recém-criado após o refresh via sinal
            self._select_username_on_refresh = username
            QMessageBox.information(
                self, "Sucesso", f"Usuário '{username}' criado com sucesso!"
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Erro", f"Não foi possível criar o usuário.\nMotivo: {e}"
            )

    def on_new_user_batch_clicked(self):
        dlg = BatchUserDialog(self, self.controller)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            users_data, valid_until, group_name = dlg.get_data()
        except ValueError as e:
            QMessageBox.warning(self, "Erro de Formato", str(e))
            return
        try:
            created = self.controller.create_users_batch(users_data, valid_until, group_name)
            # Seleciona o último criado, se houver
            if created:
                self._select_username_on_refresh = created[-1]
            QMessageBox.information(
                self, "Sucesso", f"{len(created)} usuários criados com sucesso!"
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Erro", f"Falha ao inserir usuários em lote.\nMotivo: {e}"
            )

    def on_delete_user_clicked(self):
        current_item = self.lstEntities.currentItem()
        if not current_item:
            return
        username = current_item.data(Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.question(
            self,
            "Confirmar Deleção",
            f"Tem certeza que deseja deletar o usuário '{username}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                success = self.controller.delete_user(username)
                if success:
                    QMessageBox.information(
                        self,
                        "Sucesso",
                        f"Usuário '{username}' deletado com sucesso.",
                    )
                    # Após refresh, se o mesmo usuário não existir, a seleção vai para um vizinho
                    # O método refresh_lists usa o índice anterior como fallback
                else:
                    QMessageBox.critical(
                        self,
                        "Erro",
                        "Ocorreu um erro ao deletar o usuário. Verifique os logs.",
                    )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Erro",
                    f"Não foi possível deletar o usuário.\nMotivo: {e}",
                )

    def on_change_password_clicked(self):
        current_item = self.lstEntities.currentItem()
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
                QMessageBox.information(self, "Sucesso", "Senha alterada com sucesso!")
            except Exception as e:
                QMessageBox.critical(
                    self, "Erro", f"Não foi possível alterar a senha.\nMotivo: {e}"
                )

    def on_renew_clicked(self):
        current_item = self.lstEntities.currentItem()
        if not current_item:
            return
        username = current_item.data(Qt.ItemDataRole.UserRole)
        new_date = self.renewDateEdit.date().toString("yyyy-MM-dd")
        try:
            success = self.controller.renew_user_validity(username, new_date)
            if success:
                self._select_username_on_refresh = username
                QMessageBox.information(self, "Sucesso", "Validade atualizada!")
            else:
                QMessageBox.critical(self, "Erro", "Falha ao renovar validade.")
        except Exception as e:
            QMessageBox.critical(
                self, "Erro", f"Não foi possível renovar a validade.\nMotivo: {e}"
            )

    def _update_group_lists(self, username):
        # Guardar seleção e posição de scroll atuais
        sel_user_group = (
            self.lstUserGroups.currentItem().text()
            if self.lstUserGroups.currentItem()
            else None
        )
        sel_available_group = (
            self.lstAvailableGroups.currentItem().text()
            if self.lstAvailableGroups.currentItem()
            else None
        )
        ug_scroll = self.lstUserGroups.verticalScrollBar().value()
        av_scroll = self.lstAvailableGroups.verticalScrollBar().value()

        self.lstUserGroups.clear()
        self.lstAvailableGroups.clear()
        if self.controller:
            try:
                user_groups = set(self.controller.list_user_groups(username))
                all_groups = set(self.controller.list_groups())
                for g in sorted(user_groups):
                    self.lstUserGroups.addItem(g)
                for g in sorted(all_groups - user_groups):
                    self.lstAvailableGroups.addItem(g)
                self.btnAddGroup.setEnabled(True)
                self.btnRemoveGroup.setEnabled(True)

                # Restaurar seleção anterior, se possível
                if sel_user_group is not None:
                    matches = self.lstUserGroups.findItems(sel_user_group, Qt.MatchFlag.MatchExactly)
                    if matches:
                        self.lstUserGroups.setCurrentItem(matches[0])
                if sel_available_group is not None:
                    matches = self.lstAvailableGroups.findItems(sel_available_group, Qt.MatchFlag.MatchExactly)
                    if matches:
                        self.lstAvailableGroups.setCurrentItem(matches[0])

                # Restaurar posição de scroll
                self.lstUserGroups.verticalScrollBar().setValue(ug_scroll)
                self.lstAvailableGroups.verticalScrollBar().setValue(av_scroll)
            except Exception as e:
                QMessageBox.critical(
                    self, "Erro", f"Não foi possível carregar turmas do usuário.\nMotivo: {e}"
                )

    def on_add_group_clicked(self):
        user_item = self.lstEntities.currentItem()
        group_item = self.lstAvailableGroups.currentItem()
        if not user_item or not group_item:
            return
        username = user_item.data(Qt.ItemDataRole.UserRole)
        group = group_item.text()
        try:
            if not self.controller.add_user_to_group(username, group):
                QMessageBox.critical(
                    self,
                    "Erro",
                    f"Não foi possível adicionar o aluno à turma '{group}'.",
                )
        except Exception as e:
            QMessageBox.critical(
                self, "Erro", f"Falha ao adicionar o aluno à turma.\nMotivo: {e}"
            )
        self._update_group_lists(username)

    def on_remove_group_clicked(self):
        user_item = self.lstEntities.currentItem()
        group_item = self.lstUserGroups.currentItem()
        if not user_item or not group_item:
            return
        username = user_item.data(Qt.ItemDataRole.UserRole)
        group = group_item.text()
        try:
            if not self.controller.remove_user_from_group(username, group):
                QMessageBox.critical(
                    self,
                    "Erro",
                    f"Não foi possível remover o aluno da turma '{group}'.",
                )
        except Exception as e:
            QMessageBox.critical(
                self, "Erro", f"Falha ao remover o aluno da turma.\nMotivo: {e}"
            )
        self._update_group_lists(username)

    # Não há on_save_clicked: mantido por compatibilidade se existir ligação externa
    def on_save_clicked(self):
        self.close()

