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
    QTabWidget,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
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


class _TablePrivilegeDialog(QDialog):
    """Dialogo simples para edição de privilégios de uma tabela."""

    def __init__(self, parent, privileges: set[str]):
        super().__init__(parent)
        self.setWindowTitle("Privilégios da Tabela")
        layout = QVBoxLayout(self)

        self.chk_select = QCheckBox("SELECT")
        self.chk_insert = QCheckBox("INSERT")
        self.chk_update = QCheckBox("UPDATE")
        self.chk_delete = QCheckBox("DELETE")

        for chk, label in [
            (self.chk_select, "SELECT"),
            (self.chk_insert, "INSERT"),
            (self.chk_update, "UPDATE"),
            (self.chk_delete, "DELETE"),
        ]:
            chk.setChecked(label in privileges)
            layout.addWidget(chk)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_privileges(self) -> set[str]:
        privs = set()
        if self.chk_select.isChecked():
            privs.add("SELECT")
        if self.chk_insert.isChecked():
            privs.add("INSERT")
        if self.chk_update.isChecked():
            privs.add("UPDATE")
        if self.chk_delete.isChecked():
            privs.add("DELETE")
        return privs

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
            self.controller.data_changed.connect(self._on_privileges_changed)
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

        self.tabsPrivileges = QTabWidget()

        # Tab for table privileges (existing tree)
        self.tabTables = QWidget()
        tab_tables_layout = QVBoxLayout(self.tabTables)
        self.treePrivileges = QTreeWidget()
        self.treePrivileges.setHeaderLabels([
            "Schema/Tabela",
            "SELECT",
            "INSERT",
            "UPDATE",
            "DELETE",
        ])
        self.treePrivileges.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        tab_tables_layout.addWidget(self.treePrivileges)
        self.btnSaveTables = QPushButton("Salvar")
        tab_tables_layout.addWidget(self.btnSaveTables)
        self.tabTables.setLayout(tab_tables_layout)

        # Tab for schema privileges
        self.tabSchemas = QWidget()
        tab_schema_layout = QVBoxLayout(self.tabSchemas)
        schema_select = QHBoxLayout()
        schema_select.addWidget(QLabel("Schema:"))
        self.cmbSchemas = QComboBox()
        schema_select.addWidget(self.cmbSchemas)
        tab_schema_layout.addLayout(schema_select)
        self.chkSchemaUsage = QCheckBox("USAGE")
        self.chkSchemaCreate = QCheckBox("CREATE")
        self.chkSchemaFuture = QCheckBox("Privilégios futuros (SELECT)")
        tab_schema_layout.addWidget(self.chkSchemaUsage)
        tab_schema_layout.addWidget(self.chkSchemaCreate)
        tab_schema_layout.addWidget(self.chkSchemaFuture)
        self.btnSaveSchema = QPushButton("Salvar Privilégios do Schema")
        tab_schema_layout.addWidget(self.btnSaveSchema)
        self.tabSchemas.setLayout(tab_schema_layout)

        self.tabsPrivileges.addTab(self.tabTables, "Tabelas")
        self.tabsPrivileges.addTab(self.tabSchemas, "Esquemas")
        right_layout.addWidget(self.tabsPrivileges)

        self.splitter.addWidget(right_panel)

        layout.addWidget(self.splitter)
        self.setLayout(layout)

        # Disable privilege controls until a group is selected
        self.treePrivileges.setEnabled(False)
        self.btnApplyTemplate.setEnabled(False)
        self.btnSaveTables.setEnabled(False)
        self.cmbSchemas.setEnabled(False)
        self.chkSchemaUsage.setEnabled(False)
        self.chkSchemaCreate.setEnabled(False)
        self.chkSchemaFuture.setEnabled(False)
        self.btnSaveSchema.setEnabled(False)
        self.lstMembers.setEnabled(False)

    def _connect_signals(self):
        self.btnNewGroup.clicked.connect(self._on_new_group)
        self.btnDeleteGroup.clicked.connect(self._on_delete_group)
        self.lstGroups.currentItemChanged.connect(self._on_group_selected)
        self.btnApplyTemplate.clicked.connect(self._apply_template)
        self.btnSaveTables.clicked.connect(self._save_privileges)
        self.btnSaveSchema.clicked.connect(self._save_schema_privileges)
        self.cmbSchemas.currentIndexChanged.connect(
            self._refresh_schema_privileges
        )
        self.treePrivileges.customContextMenuRequested.connect(
            self._open_table_priv_dialog
        )

    # ------------------------------------------------------------------
    def refresh_groups(self):
        prev = self.current_group
        self.lstGroups.clear()
        self.lstMembers.clear()
        if not self.controller:
            return
        for grp in self.controller.list_groups():
            item = QListWidgetItem(grp)
            self.lstGroups.addItem(item)
            if grp == prev:
                self.lstGroups.setCurrentItem(item)
        self._load_templates()

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
            if reply != QMessageBox.StandardButton.Yes:
                return
            success = self.controller.delete_group_and_members(group)
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
            self.btnSaveTables.setEnabled(False)
            self.cmbSchemas.setEnabled(False)
            self.chkSchemaUsage.setEnabled(False)
            self.chkSchemaCreate.setEnabled(False)
            self.chkSchemaFuture.setEnabled(False)
            self.btnSaveSchema.setEnabled(False)
            self.lstMembers.setEnabled(False)
            self.lstMembers.clear()
            return
        self.current_group = current.text()
        self.treePrivileges.setEnabled(True)
        self.btnApplyTemplate.setEnabled(True)
        self.btnSaveTables.setEnabled(True)
        self.cmbSchemas.setEnabled(True)
        self.chkSchemaUsage.setEnabled(True)
        self.chkSchemaCreate.setEnabled(True)
        self.chkSchemaFuture.setEnabled(True)
        self.btnSaveSchema.setEnabled(True)
        self.lstMembers.setEnabled(True)
        self._populate_tree()
        self._refresh_schema_list()
        self._refresh_schema_privileges()
        self._refresh_members()

    def _populate_tree(self):
        if not self.controller or not self.current_group:
            return
        data = self.controller.get_schema_tables()
        privileges = self.controller.get_group_privileges(self.current_group)
        self.treePrivileges.clear()
        for schema, tables in data.items():
            schema_item = QTreeWidgetItem([schema])
            # Only set the tristate flag so the parent reflects its children.
            schema_item.setFlags(
                schema_item.flags() | Qt.ItemFlag.ItemIsAutoTristate
            )
            self.treePrivileges.addTopLevelItem(schema_item)
            for table in tables:
                table_item = QTreeWidgetItem([table, "", "", "", ""])
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
                self._populate_tree()
                self._refresh_schema_privileges()
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
            for j in range(schema_item.childCount()):
                table_item = schema_item.child(j)
                table = table_item.text(0)
                perms = set()
                for col, label in enumerate(["SELECT", "INSERT", "UPDATE", "DELETE"], start=1):
                    if table_item.checkState(col) == Qt.CheckState.Checked:
                        perms.add(label)
                if perms:
                    privileges.setdefault(schema, {})[table] = perms

        def task():
            return self.controller.apply_group_privileges(
                self.current_group, privileges
            )

        def on_success(success):
            if success:
                QMessageBox.information(self, "Sucesso", "Privilégios atualizados.")
                self._populate_tree()
            else:
                QMessageBox.critical(
                    self, "Erro", "Falha ao salvar os privilégios do grupo."
                )

        def on_error(e: Exception):
            QMessageBox.critical(
                self, "Erro", f"Falha ao salvar os privilégios: {e}"
            )

        self._execute_async(task, on_success, on_error, "Salvando privilégios...")

    def _refresh_members(self):
        self.lstMembers.clear()
        if not self.controller or not self.current_group:
            return
        for user in self.controller.list_group_members(self.current_group):
            self.lstMembers.addItem(user)

    def _refresh_schema_list(self):
        if not self.controller:
            return
        schemas = sorted(self.controller.get_schema_tables().keys())
        self.cmbSchemas.clear()
        self.cmbSchemas.addItems(schemas)

    def _refresh_schema_privileges(self):
        if not self.controller or not self.current_group:
            return
        schema = self.cmbSchemas.currentText()
        privs = self.controller.get_schema_privileges(self.current_group)
        perms = privs.get(schema, set())
        self.chkSchemaUsage.setChecked("USAGE" in perms)
        self.chkSchemaCreate.setChecked("CREATE" in perms)
        # Default privileges not retrieved; assume unchecked by default
        self.chkSchemaFuture.setChecked(False)

    def _save_schema_privileges(self):
        if not self.current_group:
            return
        schema = self.cmbSchemas.currentText()
        privileges = set()
        if self.chkSchemaUsage.isChecked():
            privileges.add("USAGE")
        if self.chkSchemaCreate.isChecked():
            privileges.add("CREATE")

        future = {"SELECT"} if self.chkSchemaFuture.isChecked() else set()

        def task():
            ok1 = self.controller.grant_schema_privileges(
                self.current_group, schema, privileges
            )
            ok2 = self.controller.alter_default_privileges(
                self.current_group, schema, "tables", future
            )
            return ok1 and ok2

        def on_success(success):
            if success:
                QMessageBox.information(
                    self, "Sucesso", "Privilégios de schema atualizados."
                )
                self._refresh_schema_privileges()
            else:
                QMessageBox.critical(
                    self,
                    "Erro",
                    "Falha ao salvar os privilégios de schema.",
                )

        def on_error(e: Exception):
            QMessageBox.critical(
                self,
                "Erro",
                f"Falha ao salvar privilégios de schema: {e}",
            )

        self._execute_async(
            task, on_success, on_error, "Salvando privilégios de schema..."
        )

    def _open_table_priv_dialog(self, pos):
        item = self.treePrivileges.itemAt(pos)
        if not item or not item.parent():
            return
        current = set()
        for col, label in enumerate(["SELECT", "INSERT", "UPDATE", "DELETE"], start=1):
            if item.checkState(col) == Qt.CheckState.Checked:
                current.add(label)
        dlg = _TablePrivilegeDialog(self, current)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            selected = dlg.selected_privileges()
            for col, label in enumerate(
                ["SELECT", "INSERT", "UPDATE", "DELETE"], start=1
            ):
                state = (
                    Qt.CheckState.Checked
                    if label in selected
                    else Qt.CheckState.Unchecked
                )
                item.setCheckState(col, state)

    def _on_privileges_changed(self):
        if not self.current_group:
            return
        self._populate_tree()
        self._refresh_schema_privileges()

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
