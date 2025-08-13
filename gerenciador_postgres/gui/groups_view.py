from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QComboBox,
    QPushButton,
    QLabel,
    QSplitter,
    QToolBar,
    QInputDialog,
    QMessageBox,
    QLineEdit,
    QProgressDialog,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon
from pathlib import Path


class _TaskRunner(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(Exception)

    def __init__(self, func, parent=None):
        super().__init__(parent)
        self._func = func

    def run(self):
        try:
            result = self._func()
            self.succeeded.emit(result)
        except Exception as e:  # pragma: no cover
            self.failed.emit(e)


class GroupsView(QWidget):
    """Janela para gerenciamento de grupos e seus privilégios."""

    def __init__(self, parent=None, controller=None):
        super().__init__(parent)
        assets_dir = Path(__file__).resolve().parents[2] / "assets"
        self.setWindowIcon(QIcon(str(assets_dir / "icone.png")))
        self.controller = controller
        self.current_group = None
        self.templates = {}
        self._threads = []  # type: list[QThread]
        self._setup_ui()
        self._connect_signals()
        if self.controller:
            self.controller.data_changed.connect(self.refresh_groups)
        self.refresh_groups()

    # ------------------------------------------------------------------
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel: list of groups
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        self.toolbar = QToolBar()
        self.btnNewGroup = QPushButton("Novo Grupo")
        self.btnDeleteGroup = QPushButton("Excluir Grupo")
        self.toolbar.addWidget(self.btnNewGroup)
        self.toolbar.addWidget(self.btnDeleteGroup)
        left_layout.addWidget(self.toolbar)
        self.lstGroups = QListWidget()
        left_layout.addWidget(self.lstGroups)
        left_layout.addWidget(QLabel("Membros do Grupo:"))
        self.lstMembers = QListWidget()
        left_layout.addWidget(self.lstMembers)
        self.splitter.addWidget(left_panel)

        # Right panel: privileges
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        top = QHBoxLayout()
        top.addWidget(QLabel("Template:"))
        self.cmbTemplates = QComboBox()
        self.btnApplyTemplate = QPushButton("Aplicar")
        top.addWidget(self.cmbTemplates)
        top.addWidget(self.btnApplyTemplate)
        right_layout.addLayout(top)

        self.treePrivileges = QTreeWidget()
        self.treePrivileges.setHeaderLabels([
            "Schema/Tabela",
            "SELECT",
            "INSERT",
            "UPDATE",
            "DELETE",
            "USAGE(Schema)",
            "CREATE(Schema)",
        ])
        right_layout.addWidget(self.treePrivileges)

        self.btnSave = QPushButton("Salvar")
        self.btnSweep = QPushButton("Sincronizar privilégios")
        actions_layout = QHBoxLayout()
        actions_layout.addWidget(self.btnSave)
        actions_layout.addWidget(self.btnSweep)
        actions_layout.addStretch(1)
        right_layout.addLayout(actions_layout)
        self.splitter.addWidget(right_panel)

        layout.addWidget(self.splitter)
        self.setLayout(layout)

        # Disable privilege controls until a group is selected
        self.treePrivileges.setEnabled(False)
        self.btnApplyTemplate.setEnabled(False)
        self.btnSave.setEnabled(False)
        self.btnSweep.setEnabled(False)
        self.lstMembers.setEnabled(False)

    def _connect_signals(self):
        self.btnNewGroup.clicked.connect(self._on_new_group)
        self.btnDeleteGroup.clicked.connect(self._on_delete_group)
        self.lstGroups.currentItemChanged.connect(self._on_group_selected)
        self.btnApplyTemplate.clicked.connect(self._apply_template)
        self.btnSave.clicked.connect(self._save_privileges)
        self.btnSweep.clicked.connect(self._sweep_privileges)

    # ------------------------------------------------------------------
    def refresh_groups(self):
        # Preserva o grupo selecionado, se houver
        prev = self.current_group
        if not prev:
            item = self.lstGroups.currentItem()
            prev = item.text() if item else None

        self.lstGroups.clear()
        self.lstMembers.clear()
        if not self.controller:
            return
        for grp in self.controller.list_groups():
            self.lstGroups.addItem(QListWidgetItem(grp))
        self._load_templates()
        # Restaura seleção anterior, se possível; senão seleciona o primeiro
        if prev:
            matches = self.lstGroups.findItems(prev, Qt.MatchFlag.MatchExactly)
            if matches:
                self.lstGroups.setCurrentItem(matches[0])
            elif self.lstGroups.count() > 0:
                self.lstGroups.setCurrentRow(0)
        elif self.lstGroups.count() > 0:
            self.lstGroups.setCurrentRow(0)

    def _load_templates(self):
        if not self.controller:
            return
        self.templates = self.controller.list_privilege_templates()
        self.cmbTemplates.clear()
        self.cmbTemplates.addItems(self.templates.keys())

    def _on_new_group(self):
        name, ok = QInputDialog.getText(
            self,
            "Novo Grupo",
            "Digite o nome do grupo (o prefixo 'grp_' será adicionado automaticamente):",
            QLineEdit.EchoMode.Normal,
            "",
        )
        if not ok or not name.strip():
            return
        name = name.strip().lower()
        if not name.startswith("grp_"):
            name = f"grp_{name}"
        try:
            self.controller.create_group(name)
            QMessageBox.information(self, "Sucesso", f"Grupo '{name}' criado.")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível criar o grupo.\nMotivo: {e}")

    def _on_delete_group(self):
        item = self.lstGroups.currentItem()
        if not item:
            return
        group = item.text()
        members = self.controller.list_group_members(group)
        if members:
            msg = (
                f"O grupo '{group}' possui {len(members)} membro(s).\n"
                "Deseja removê-los junto com o grupo?"
            )
            reply = QMessageBox.question(
                self,
                "Grupo com membros",
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                success = self.controller.delete_group_and_members(group)
            else:
                success = self.controller.delete_group(group)
        else:
            reply = QMessageBox.question(
                self,
                "Confirmar Deleção",
                f"Tem certeza que deseja excluir o grupo '{group}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            success = self.controller.delete_group(group)
        if success:
            QMessageBox.information(
                self, "Sucesso", f"Grupo '{group}' excluído com sucesso."
            )
        else:
            QMessageBox.critical(
                self, "Erro", "Não foi possível excluir o grupo."
            )

    def _on_group_selected(self, current, previous):
        if not current:
            self.current_group = None
            self.treePrivileges.setEnabled(False)
            self.btnApplyTemplate.setEnabled(False)
            self.btnSave.setEnabled(False)
            self.btnSweep.setEnabled(False)
            self.lstMembers.setEnabled(False)
            self.lstMembers.clear()
            return
        self.current_group = current.text()
        self.treePrivileges.setEnabled(True)
        self.btnApplyTemplate.setEnabled(True)
        self.btnSave.setEnabled(True)
        self.btnSweep.setEnabled(True)
        self.lstMembers.setEnabled(True)
        self._populate_tree()
        self._refresh_members()

    def _populate_tree(self):
        if not self.controller or not self.current_group:
            return
        data = self.controller.get_schema_tables()
        privileges = self.controller.get_group_privileges(self.current_group)
        schema_level = self.controller.get_schema_level_privileges(self.current_group)
        future_defaults = self.controller.get_default_table_privileges(self.current_group)
        self.treePrivileges.clear()
        for schema, tables in data.items():
            schema_item = QTreeWidgetItem([schema])
            schema_item.setFlags(schema_item.flags() | Qt.ItemFlag.ItemIsAutoTristate)
            self.treePrivileges.addTopLevelItem(schema_item)

            # Se não há tabelas, ainda assim mostramos um nó "(geral)" para configurar privilégios futuros
            if not tables:
                general_item = QTreeWidgetItem(["(geral)", "", "", "", "", "", ""])
                general_item.setData(0, Qt.ItemDataRole.UserRole, {"schema_general": True})
                general_item.setFlags(
                    general_item.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsSelectable
                )
                # Marcar privilégios default futuros existentes
                existing_future = future_defaults.get(schema, set())
                for col, label in enumerate(["SELECT", "INSERT", "UPDATE", "DELETE"], start=1):
                    general_item.setCheckState(
                        col,
                        Qt.CheckState.Checked if label in existing_future else Qt.CheckState.Unchecked,
                    )
                # Marcar USAGE/CREATE reais
                sch_perms = schema_level.get(schema, set())
                general_item.setCheckState(5, Qt.CheckState.Checked if 'USAGE' in sch_perms else Qt.CheckState.Unchecked)
                general_item.setCheckState(6, Qt.CheckState.Checked if 'CREATE' in sch_perms else Qt.CheckState.Unchecked)
                schema_item.addChild(general_item)
            else:
                for table in tables:
                    table_item = QTreeWidgetItem([table, "", "", "", "", "", ""])
                    table_item.setFlags(
                        table_item.flags()
                        | Qt.ItemFlag.ItemIsUserCheckable
                        | Qt.ItemFlag.ItemIsSelectable
                    )
                    perms = privileges.get(schema, {}).get(table, set())
                    for col, label in enumerate(["SELECT", "INSERT", "UPDATE", "DELETE"], start=1):
                        state = Qt.CheckState.Checked if label in perms else Qt.CheckState.Unchecked
                        table_item.setCheckState(col, state)
                    schema_item.addChild(table_item)
                # Adicionar nó (geral) adicional para schema com tabelas (para configurar futuros + USAGE/CREATE)
                general_item = QTreeWidgetItem(["(geral)", "", "", "", "", "", ""])
                general_item.setData(0, Qt.ItemDataRole.UserRole, {"schema_general": True})
                general_item.setFlags(
                    general_item.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsSelectable
                )
                existing_future = future_defaults.get(schema, set())
                for col, label in enumerate(["SELECT", "INSERT", "UPDATE", "DELETE"], start=1):
                    general_item.setCheckState(
                        col,
                        Qt.CheckState.Checked if label in existing_future else Qt.CheckState.Unchecked,
                    )
                sch_perms = schema_level.get(schema, set())
                general_item.setCheckState(5, Qt.CheckState.Checked if 'USAGE' in sch_perms else Qt.CheckState.Unchecked)
                general_item.setCheckState(6, Qt.CheckState.Checked if 'CREATE' in sch_perms else Qt.CheckState.Unchecked)
                schema_item.insertChild(0, general_item)
        # Expand after populating all schemas
        self.treePrivileges.expandAll()

    def _apply_template(self):
        if not self.current_group:
            return
        template_name = self.cmbTemplates.currentText()

        def task():
            return self.controller.apply_template_to_group(
                self.current_group, template_name
            )

        def on_success(success):
            if success:
                QMessageBox.information(
                    self, "Sucesso", "Template aplicado com sucesso."
                )
                perms = self.templates.get(template_name, set())
                for i in range(self.treePrivileges.topLevelItemCount()):
                    schema_item = self.treePrivileges.topLevelItem(i)
                    for j in range(schema_item.childCount()):
                        table_item = schema_item.child(j)
                        for col, label in enumerate(
                            ["SELECT", "INSERT", "UPDATE", "DELETE"], start=1
                        ):
                            state = (
                                Qt.CheckState.Checked
                                if label in perms
                                else Qt.CheckState.Unchecked
                            )
                            table_item.setCheckState(col, state)
            else:
                QMessageBox.critical(
                    self, "Erro", "Falha ao aplicar o template ao grupo."
                )

        def on_error(e: Exception):
            QMessageBox.critical(
                self, "Erro", f"Não foi possível aplicar o template: {e}"
            )

        self._execute_async(task, on_success, on_error, "Aplicando template...")

    def _save_privileges(self):
        if not self.current_group:
            return
        privileges: dict[str, dict[str, set[str]]] = {}
        for i in range(self.treePrivileges.topLevelItemCount()):
            schema_item = self.treePrivileges.topLevelItem(i)
            schema = schema_item.text(0)
            schema_general_perms = None
            for j in range(schema_item.childCount()):
                table_item = schema_item.child(j)
                if table_item.data(0, Qt.ItemDataRole.UserRole):
                    # Nó (geral) - guarda permissões para aplicar como default privileges no backend depois
                    gp = set()
                    for col, label in enumerate(["SELECT", "INSERT", "UPDATE", "DELETE"], start=1):
                        if table_item.checkState(col) == Qt.CheckState.Checked:
                            gp.add(label)
                    schema_general_perms = gp
                    # Schema-level flags (USAGE/CREATE)
                    schema_usage = table_item.checkState(5) == Qt.CheckState.Checked
                    schema_create = table_item.checkState(6) == Qt.CheckState.Checked
                    # Guardar sempre (mesmo vazio) para permitir revogar privilégios de schema
                    privileges.setdefault(schema, {})['__SCHEMA_PRIVS__'] = {
                        *( ['USAGE'] if schema_usage else [] ),
                        *( ['CREATE'] if schema_create else [] ),
                    }
                else:
                    table = table_item.text(0)
                    perms = set()
                    for col, label in enumerate(["SELECT", "INSERT", "UPDATE", "DELETE"], start=1):
                        if table_item.checkState(col) == Qt.CheckState.Checked:
                            perms.add(label)
                    privileges.setdefault(schema, {})[table] = perms

            # Se schema vazio => usar nó geral para criar entrada sintética que o backend tratará como default privileges
            if schema_general_perms is not None and (not privileges.get(schema) or list(privileges.get(schema).keys()) == ['__SCHEMA_PRIVS__']):
                # Representamos com chave especial '__FUTURE__' que não corresponde a uma tabela real
                privileges.setdefault(schema, {})['__FUTURE__'] = schema_general_perms

        def task():
            return self.controller.apply_group_privileges(
                self.current_group, privileges
            )

        def on_success(success):
            if success:
                QMessageBox.information(self, "Sucesso", "Privilégios atualizados.")
                # Atualiza visual imediatamente para refletir o estado salvo
                self._populate_tree()
                self._refresh_members()
            else:
                QMessageBox.critical(
                    self, "Erro", "Falha ao salvar os privilégios do grupo."
                )

        def on_error(e: Exception):
            QMessageBox.critical(
                self, "Erro", f"Falha ao salvar os privilégios: {e}"
            )

        self._execute_async(task, on_success, on_error, "Salvando privilégios...")

    def _sweep_privileges(self):
        # Determina o grupo selecionado no momento do clique
        item = self.lstGroups.currentItem()
        group_name = item.text() if item else self.current_group
        if not group_name:
            QMessageBox.warning(self, "Seleção necessária", "Selecione um grupo para sincronizar.")
            return

        def task():
            return self.controller.sweep_group_privileges(group_name)

        def on_success(success):
            if success:
                QMessageBox.information(
                    self, "Concluído", f"Privilégios do grupo '{group_name}' sincronizados."
                )
            else:
                QMessageBox.critical(
                    self, "Erro", f"Falha ao sincronizar privilégios do grupo '{group_name}'."
                )

        def on_error(e: Exception):
            QMessageBox.critical(
                self, "Erro", f"Não foi possível sincronizar os privilégios do grupo '{group_name}': {e}"
            )

        self._execute_async(task, on_success, on_error, f"Sincronizando privilégios de '{group_name}'...")

    def _refresh_members(self):
        self.lstMembers.clear()
        if not self.controller or not self.current_group:
            return
        for user in self.controller.list_group_members(self.current_group):
            self.lstMembers.addItem(user)

    def _execute_async(self, func, on_success, on_error, label):
        progress = QProgressDialog(label, None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setAutoClose(True)
        progress.show()

        thread = _TaskRunner(func, self)

        def handle_success(result):
            progress.cancel()
            try:
                on_success(result)
            finally:
                if thread in self._threads:
                    self._threads.remove(thread)
                thread.deleteLater()

        def handle_error(e: Exception):
            progress.cancel()
            try:
                on_error(e)
            finally:
                if thread in self._threads:
                    self._threads.remove(thread)
                thread.deleteLater()

        thread.succeeded.connect(handle_success)
        thread.failed.connect(handle_error)
        self._threads.append(thread)
        thread.start()
