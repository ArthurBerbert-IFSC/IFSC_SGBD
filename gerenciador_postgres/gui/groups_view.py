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
    QGroupBox,
    QCheckBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon
from pathlib import Path
import logging


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
        self.schema_tables = {}
        self.cb_usage = None
        self.cb_create = None
        self.cb_default_select = None
        self.cb_default_insert = None
        self.cb_default_update = None
        self.cb_default_delete = None
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

        # Container para privilégios de schema no padrão mestre-detalhe
        self.schema_container = QWidget()
        self.schema_privs_layout = QHBoxLayout(self.schema_container)
        self.schema_list_widget = QListWidget()
        self.schema_list_widget.setMaximumWidth(200)
        self.schema_privs_layout.addWidget(self.schema_list_widget)

        self.schema_details_widget = QWidget()
        self.schema_details_layout = QVBoxLayout(self.schema_details_widget)
        self.schema_privs_layout.addWidget(self.schema_details_widget, 1)
        right_layout.addWidget(self.schema_container)

        self.treePrivileges = QTreeWidget()
        self.treePrivileges.setHeaderLabels([
            "Schema/Tabela",
            "SELECT",
            "INSERT",
            "UPDATE",
            "DELETE",
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
        self.schema_container.setEnabled(False)
        self.treePrivileges.setEnabled(False)
        self.btnApplyTemplate.setEnabled(False)
        self.btnSave.setEnabled(False)
        self.btnSweep.setEnabled(False)
        self.lstMembers.setEnabled(False)

    def _connect_signals(self):
        self.btnNewGroup.clicked.connect(self._on_new_group)
        self.btnDeleteGroup.clicked.connect(self._on_delete_group)
        self.lstGroups.currentItemChanged.connect(self._on_group_selected)
        self.schema_list_widget.currentItemChanged.connect(
            self._on_schema_selected
        )
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
            self.schema_container.setEnabled(False)
            self.treePrivileges.setEnabled(False)
            self.btnApplyTemplate.setEnabled(False)
            self.btnSave.setEnabled(False)
            self.btnSweep.setEnabled(False)
            self.lstMembers.setEnabled(False)
            self.lstMembers.clear()
            self.schema_list_widget.clear()
            self._clear_layout(self.schema_details_layout)
            return
        self.current_group = current.text()
        self.schema_container.setEnabled(True)
        self.treePrivileges.setEnabled(True)
        self.btnApplyTemplate.setEnabled(True)
        self.btnSave.setEnabled(True)
        self.btnSweep.setEnabled(True)
        self.lstMembers.setEnabled(True)
        self._populate_schemas()
        self._populate_table_tree()
        self._refresh_members()

    def _populate_schemas(self):
        if not self.controller or not self.current_group:
            return
        try:
            self.schema_tables = self.controller.get_schema_tables()
        except Exception as e:  # pragma: no cover
            logging.exception("Erro ao ler schemas")
            QMessageBox.warning(
                self,
                "Erro",
                f"Não foi possível ler os schemas.\nMotivo: {e}",
            )
            self.schema_tables = {}

        self.schema_list_widget.blockSignals(True)
        self.schema_list_widget.clear()
        for schema in sorted(self.schema_tables.keys()):
            self.schema_list_widget.addItem(QListWidgetItem(schema))
        self.schema_list_widget.blockSignals(False)
        if self.schema_list_widget.count() > 0:
            self.schema_list_widget.setCurrentRow(0)

    def _populate_table_tree(self):
        if not self.controller or not self.current_group:
            return
        role = self.current_group
        try:
            schema_tables = self.schema_tables or self.controller.get_schema_tables()
            table_privs = self.controller.get_group_privileges(role)
        except Exception as e:  # pragma: no cover
            logging.exception("Erro ao ler privilégios do grupo")
            QMessageBox.warning(
                self,
                "Erro",
                f"Não foi possível ler os privilégios.\nMotivo: {e}",
            )
            schema_tables, table_privs = {}, {}

        self.treePrivileges.clear()
        for schema, tables in schema_tables.items():
            schema_item = QTreeWidgetItem([schema])
            self.treePrivileges.addTopLevelItem(schema_item)
            for table in tables:
                table_item = QTreeWidgetItem([table, "", "", "", ""])
                table_item.setFlags(
                    table_item.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsSelectable
                )
                perms = table_privs.get(schema, {}).get(table, set())
                for col, label in enumerate(["SELECT", "INSERT", "UPDATE", "DELETE"], start=1):
                    state = (
                        Qt.CheckState.Checked
                        if label in perms
                        else Qt.CheckState.Unchecked
                    )
                    table_item.setCheckState(col, state)
                schema_item.addChild(table_item)
        self.treePrivileges.expandAll()

    def _on_schema_selected(self, current_item, previous_item):
        if not current_item or not self.controller or not self.current_group:
            return
        schema_name = current_item.text()
        role = self.current_group

        self._clear_layout(self.schema_details_layout)

        try:
            schema_privs = self.controller.get_schema_level_privileges(role).get(
                schema_name, set()
            )
            default_privs = self.controller.get_default_table_privileges(role).get(
                schema_name, set()
            )
        except Exception as e:  # pragma: no cover
            logging.exception("Erro ao ler privilégios de schema")
            QMessageBox.warning(
                self,
                "Erro",
                f"Não foi possível ler os privilégios.\nMotivo: {e}",
            )
            schema_privs, default_privs = set(), set()

        usage_create_box = QGroupBox("Permissões no Schema")
        usage_create_layout = QHBoxLayout()
        self.cb_usage = QCheckBox("USAGE")
        self.cb_usage.setChecked("USAGE" in schema_privs)
        usage_create_layout.addWidget(self.cb_usage)
        self.cb_create = QCheckBox("CREATE")
        self.cb_create.setChecked("CREATE" in schema_privs)
        usage_create_layout.addWidget(self.cb_create)
        usage_create_box.setLayout(usage_create_layout)
        self.schema_details_layout.addWidget(usage_create_box)

        defaults_box = QGroupBox("Para Novas Tabelas (Privilégios Futuros)")
        defaults_layout = QHBoxLayout()
        self.cb_default_select = QCheckBox("SELECT")
        self.cb_default_select.setChecked("SELECT" in default_privs)
        defaults_layout.addWidget(self.cb_default_select)
        self.cb_default_insert = QCheckBox("INSERT")
        self.cb_default_insert.setChecked("INSERT" in default_privs)
        defaults_layout.addWidget(self.cb_default_insert)
        self.cb_default_update = QCheckBox("UPDATE")
        self.cb_default_update.setChecked("UPDATE" in default_privs)
        defaults_layout.addWidget(self.cb_default_update)
        self.cb_default_delete = QCheckBox("DELETE")
        self.cb_default_delete.setChecked("DELETE" in default_privs)
        defaults_layout.addWidget(self.cb_default_delete)
        defaults_box.setLayout(defaults_layout)
        self.schema_details_layout.addWidget(defaults_box)

        self.schema_details_layout.addStretch()

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
        current_schema_item = self.schema_list_widget.currentItem()
        if not self.current_group or not current_schema_item:
            QMessageBox.warning(
                self, "Atenção", "Selecione um grupo e um schema primeiro."
            )
            return

        role = self.current_group
        schema = current_schema_item.text()

        schema_perms_to_set = set()
        if self.cb_usage and self.cb_usage.isChecked():
            schema_perms_to_set.add("USAGE")
        if self.cb_create and self.cb_create.isChecked():
            schema_perms_to_set.add("CREATE")

        default_perms_to_set = set()
        if self.cb_default_select and self.cb_default_select.isChecked():
            default_perms_to_set.add("SELECT")
        if self.cb_default_insert and self.cb_default_insert.isChecked():
            default_perms_to_set.add("INSERT")
        if self.cb_default_update and self.cb_default_update.isChecked():
            default_perms_to_set.add("UPDATE")
        if self.cb_default_delete and self.cb_default_delete.isChecked():
            default_perms_to_set.add("DELETE")

        table_privs: dict[str, dict[str, set[str]]] = {}
        for i in range(self.treePrivileges.topLevelItemCount()):
            schema_item = self.treePrivileges.topLevelItem(i)
            schema_name = schema_item.text(0)
            for j in range(schema_item.childCount()):
                table_item = schema_item.child(j)
                table = table_item.text(0)
                perms = set()
                for col, label in enumerate(["SELECT", "INSERT", "UPDATE", "DELETE"], start=1):
                    if table_item.checkState(col) == Qt.CheckState.Checked:
                        perms.add(label)
                table_privs.setdefault(schema_name, {})[table] = perms

        def task():
            self.controller.grant_schema_privileges(role, schema, schema_perms_to_set)
            self.controller.alter_default_privileges(
                role, schema, "tables", default_perms_to_set
            )
            return self.controller.apply_group_privileges(role, table_privs)

        def on_success(success):
            if success:
                QMessageBox.information(
                    self,
                    "Sucesso",
                    f"Privilégios para o schema '{schema}' foram atualizados.",
                )
                self._on_schema_selected(current_schema_item, None)
                self._populate_table_tree()
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

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            elif item.layout() is not None:
                self._clear_layout(item.layout())

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
