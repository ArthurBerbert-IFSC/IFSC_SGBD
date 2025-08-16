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
from dataclasses import dataclass, field
import logging

from gerenciador_postgres.controllers.groups_controller import DependencyWarning


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


@dataclass
class PrivilegesState:
    schema_privs: set[str] = field(default_factory=set)
    table_privs: dict[str, set[str]] = field(default_factory=dict)
    default_privs: set[str] = field(default_factory=set)
    dirty_schema: bool = False
    dirty_table: bool = False
    dirty_default: bool = False

    @property
    def dirty(self) -> bool:
        return self.dirty_schema or self.dirty_table or self.dirty_default


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
        # Cache de privilégios em memória por (role, schema)
        self._priv_cache: dict[tuple[str, str], PrivilegesState] = {}
        self._setup_ui()
        self._connect_signals()
        if self.controller:
            self.controller.data_changed.connect(self.refresh_groups)
        self.refresh_groups()

    # ------------------------------------------------------------------
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel
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

        # Right panel
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        top = QHBoxLayout()
        top.addWidget(QLabel("Template:"))
        self.cmbTemplates = QComboBox()
        self.btnApplyTemplate = QPushButton("Aplicar")
        top.addWidget(self.cmbTemplates)
        top.addWidget(self.btnApplyTemplate)
        right_layout.addLayout(top)

        # Schema management (master-detail)
        self.schema_group = QGroupBox("Gerenciamento de Schemas")
        schema_management_layout = QVBoxLayout()
        detail_layout = QHBoxLayout()
        self.schema_list = QListWidget()
        self.schema_list.setMaximumWidth(250)
        detail_layout.addWidget(self.schema_list)
        self.schema_details_panel = QWidget()
        self.schema_details_layout = QVBoxLayout(self.schema_details_panel)
        detail_layout.addWidget(self.schema_details_panel, 1)
        schema_management_layout.addLayout(detail_layout)
        self.schema_group.setLayout(schema_management_layout)
        right_layout.addWidget(self.schema_group)

        # Table privileges tree
        self.treePrivileges = QTreeWidget()
        self.treePrivileges.setHeaderLabels([
            "Schema/Tabela", "SELECT", "INSERT", "UPDATE", "DELETE"
        ])
        right_layout.addWidget(self.treePrivileges)

        # Action buttons
        self.btnSaveSchema = QPushButton("Salvar Schema")
        self.btnSaveDefaults = QPushButton("Salvar Defaults")
        self.btnSaveTables = QPushButton("Salvar Tabelas")
        self.btnReloadTables = QPushButton("Recarregar Tabelas")
        self.btnSweep = QPushButton("Sincronizar (Full Sweep)")
        actions_layout = QHBoxLayout()
        for btn in [self.btnSaveSchema, self.btnSaveDefaults, self.btnSaveTables, self.btnReloadTables, self.btnSweep]:
            actions_layout.addWidget(btn)
        actions_layout.addStretch(1)
        right_layout.addLayout(actions_layout)

        self.splitter.addWidget(right_panel)
        layout.addWidget(self.splitter)
        self.setLayout(layout)

        # Initial disabled state
        for w in [self.schema_group, self.treePrivileges, self.btnApplyTemplate,
                  self.btnSaveSchema, self.btnSaveDefaults, self.btnSaveTables,
                  self.btnReloadTables, self.btnSweep, self.lstMembers]:
            w.setEnabled(False)

    def _connect_signals(self):
        self.btnNewGroup.clicked.connect(self._on_new_group)
        self.btnDeleteGroup.clicked.connect(self._on_delete_group)
        self.lstGroups.currentItemChanged.connect(self._on_group_selected)
        self.schema_list.currentItemChanged.connect(self._update_schema_details)
        self.btnApplyTemplate.clicked.connect(self._apply_template)
        self.btnSaveSchema.clicked.connect(self._save_schema_privileges)
        self.btnSaveDefaults.clicked.connect(self._save_default_privileges)
        self.btnSaveTables.clicked.connect(self._save_table_privileges)
        self.btnReloadTables.clicked.connect(self._reload_tables)
        self.btnSweep.clicked.connect(self._sweep_privileges)
        self.treePrivileges.itemChanged.connect(self._on_table_priv_changed)

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
            "Digite o nome do grupo (o prefixo 'turma_' será adicionado automaticamente):",
            QLineEdit.EchoMode.Normal,
            "",
        )
        if not ok or not name.strip():
            return
        name = name.strip().lower()
        if not name.startswith("turma_"):
            name = f"turma_{name}"
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
        if previous and not self._check_dirty_for_group(previous.text()):
            self.lstGroups.blockSignals(True)
            self.lstGroups.setCurrentItem(previous)
            self.lstGroups.blockSignals(False)
            return
        if not current:
            # Limpa estado quando nada selecionado
            self.current_group = None
            self.schema_group.setEnabled(False)
            self.treePrivileges.setEnabled(False)
            self.btnApplyTemplate.setEnabled(False)
            self.btnSaveSchema.setEnabled(False)
            self.btnSaveDefaults.setEnabled(False)
            self.btnSaveTables.setEnabled(False)
            self.btnSweep.setEnabled(False)
            self.lstMembers.setEnabled(False)
            self.lstMembers.clear()
            self.schema_list.clear()
            self._clear_layout(self.schema_details_layout)
            return

        # Novo grupo selecionado
        self.current_group = current.text()
        for w in [self.schema_group, self.treePrivileges, self.btnApplyTemplate,
                  self.btnSaveSchema, self.btnSaveDefaults, self.btnSaveTables,
                  self.btnReloadTables, self.btnSweep, self.lstMembers]:
            w.setEnabled(True)
        self._populate_privileges()
        self._refresh_members()

    # ------------------------------------------------------------------
    def _check_dirty_for_group(self, group: str) -> bool:
        dirty_keys = [k for k, st in self._priv_cache.items() if k[0] == group and st.dirty]
        if not dirty_keys:
            return True
        resp = QMessageBox.question(
            self,
            "Alterações não salvas",
            "Salvar alterações antes de mudar de grupo?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if resp == QMessageBox.StandardButton.Save:
            for key in dirty_keys:
                if not self._save_state_sync(*key):
                    return False
            return True
        if resp == QMessageBox.StandardButton.Discard:
            for key in dirty_keys:
                self._priv_cache.pop(key, None)
            return True
        return False

    def _check_dirty_for_schema(self, role: str, schema: str) -> bool:
        key = (role, schema)
        state = self._priv_cache.get(key)
        if not state or not state.dirty:
            return True
        resp = QMessageBox.question(
            self,
            "Alterações não salvas",
            f"Salvar alterações de '{schema}'?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if resp == QMessageBox.StandardButton.Save:
            return self._save_state_sync(role, schema)
        if resp == QMessageBox.StandardButton.Discard:
            self._priv_cache.pop(key, None)
            return True
        return False

    def _save_state_sync(self, role: str, schema: str) -> bool:
        state = self._priv_cache.get((role, schema))
        if not state:
            return True
        ok1 = self.controller.grant_schema_privileges(
            role, schema, state.schema_privs, emit_signal=False
        )
        ok2 = self.controller.alter_default_privileges(
            role, schema, "tables", state.default_privs, emit_signal=False
        )
        ok3 = self.controller.apply_group_privileges(
            role, {schema: state.table_privs}, defaults_applied=True, emit_signal=False
        )
        if ok1 and ok2 and ok3:
            state.dirty_schema = state.dirty_default = state.dirty_table = False
            return True
        return False

    def _update_schema_priv(self, role: str, schema: str, perm: str, checked: bool):
        key = (role, schema)
        state = self._priv_cache.setdefault(key, PrivilegesState())
        if checked:
            state.schema_privs.add(perm)
        else:
            state.schema_privs.discard(perm)
        state.dirty_schema = True

    def _update_default_priv(self, role: str, schema: str, perm: str, checked: bool):
        key = (role, schema)
        state = self._priv_cache.setdefault(key, PrivilegesState())
        if checked:
            state.default_privs.add(perm)
        else:
            state.default_privs.discard(perm)
        state.dirty_default = True

    def _on_table_priv_changed(self, item: QTreeWidgetItem, column: int):
        if column == 0 or not self.current_group:
            return
        schema_item = item.parent()
        if not schema_item:
            return
        schema = schema_item.text(0)
        table = item.text(0)
        perm_labels = ["SELECT", "INSERT", "UPDATE", "DELETE"]
        if column - 1 >= len(perm_labels):
            return
        perm = perm_labels[column - 1]
        checked = item.checkState(column) == Qt.CheckState.Checked
        key = (self.current_group, schema)
        state = self._priv_cache.setdefault(key, PrivilegesState())
        table_perms = state.table_privs.setdefault(table, set())
        if checked:
            table_perms.add(perm)
        else:
            table_perms.discard(perm)
        state.dirty_table = True

    def _populate_privileges(self):
        if not self.controller or not self.current_group:
            return
        role = self.current_group
        try:
            self.schema_tables = self.controller.get_schema_tables()
            table_privs = self.controller.get_group_privileges(role)
        except Exception as e:  # pragma: no cover
            logging.exception("Erro ao ler privilégios do grupo")
            QMessageBox.warning(
                self,
                "Erro",
                f"Não foi possível ler os privilégios.\nMotivo: {e}",
            )
            self.schema_tables, table_privs = {}, {}

        self.schema_list.blockSignals(True)
        self.schema_list.clear()
        for schema in sorted(self.schema_tables.keys()):
            self.schema_list.addItem(QListWidgetItem(schema))
        self.schema_list.blockSignals(False)
        if self.schema_list.count() > 0:
            self.schema_list.setCurrentRow(0)

        self.treePrivileges.blockSignals(True)
        self.treePrivileges.clear()
        for schema, tables in self.schema_tables.items():
            schema_item = QTreeWidgetItem([schema])
            self.treePrivileges.addTopLevelItem(schema_item)
            key = (role, schema)
            state = self._priv_cache.get(key)
            if not state:
                state = PrivilegesState()
                self._priv_cache[key] = state
            for table in tables:
                table_item = QTreeWidgetItem([table, "", "", "", ""])
                table_item.setFlags(
                    table_item.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsSelectable
                )
                perms_db = table_privs.get(schema, {}).get(table, set())
                perms = state.table_privs.get(table, set(perms_db))
                state.table_privs[table] = set(perms)
                for col, label in enumerate(["SELECT", "INSERT", "UPDATE", "DELETE"], start=1):
                    table_item.setCheckState(
                        col,
                        Qt.CheckState.Checked if label in perms else Qt.CheckState.Unchecked,
                    )
                schema_item.addChild(table_item)
        self.treePrivileges.blockSignals(False)
        self.treePrivileges.expandAll()

    def _update_schema_details(self, current_item, previous_item):
        if previous_item and not self._check_dirty_for_schema(self.current_group, previous_item.text()):
            self.schema_list.blockSignals(True)
            self.schema_list.setCurrentItem(previous_item)
            self.schema_list.blockSignals(False)
            return
        if not current_item or not self.controller or not self.current_group:
            return
        schema_name = current_item.text()
        role = self.current_group

        self._clear_layout(self.schema_details_layout)

        try:
            schema_privs_all = self.controller.get_schema_level_privileges(role)
            schema_privs_db = schema_privs_all.get(schema_name, set())
            default_all = self.controller.get_default_table_privileges(role)
            default_info = default_all.get(schema_name, {})
            default_privs_db = default_info.get("privileges", set())
            owner_role = default_info.get("owner")
            key = (role, schema_name)
            state = self._priv_cache.get(key)
            if not state:
                state = PrivilegesState()
                self._priv_cache[key] = state
            if not state.schema_privs:
                state.schema_privs = set(schema_privs_db)
            if not state.default_privs:
                state.default_privs = set(default_privs_db)
            schema_privs = state.schema_privs
            default_privs = state.default_privs
        except Exception as e:  # pragma: no cover
            logging.exception("Erro ao ler privilégios de schema")
            QMessageBox.warning(
                self,
                "Erro",
                f"Não foi possível ler os privilégios.\nMotivo: {e}",
            )
            schema_privs, default_privs, owner_role = set(), set(), None

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

        # Conecta mudanças aos caches
        self.cb_usage.stateChanged.connect(
            lambda st, r=role, s=schema_name: self._update_schema_priv(r, s, "USAGE", st == Qt.CheckState.Checked)
        )
        self.cb_create.stateChanged.connect(
            lambda st, r=role, s=schema_name: self._update_schema_priv(r, s, "CREATE", st == Qt.CheckState.Checked)
        )
        self.cb_default_select.stateChanged.connect(
            lambda st, r=role, s=schema_name: self._update_default_priv(r, s, "SELECT", st == Qt.CheckState.Checked)
        )
        self.cb_default_insert.stateChanged.connect(
            lambda st, r=role, s=schema_name: self._update_default_priv(r, s, "INSERT", st == Qt.CheckState.Checked)
        )
        self.cb_default_update.stateChanged.connect(
            lambda st, r=role, s=schema_name: self._update_default_priv(r, s, "UPDATE", st == Qt.CheckState.Checked)
        )
        self.cb_default_delete.stateChanged.connect(
            lambda st, r=role, s=schema_name: self._update_default_priv(r, s, "DELETE", st == Qt.CheckState.Checked)
        )

        if owner_role:
            owner_label = QLabel(f"owner: {owner_role}")
            self.schema_details_layout.addWidget(owner_label)

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

    # ------------------------ Salvamentos separados ---------------------
    def _current_schema_checked(self):
        item = self.schema_list.currentItem()
        if not self.current_group or not item:
            QMessageBox.warning(self, "Atenção", "Selecione um grupo e um schema primeiro.")
            return None, None
        return self.current_group, item.text()

    def _save_schema_privileges(self):
        role, schema = self._current_schema_checked()
        if not role:
            return
        state = self._priv_cache.get((role, schema))
        schema_perms = set(state.schema_privs) if state else set()

        def task():
            return self.controller.grant_schema_privileges(role, schema, schema_perms, emit_signal=False)

        def on_success(success):
            if success:
                if state:
                    state.dirty_schema = False
                QMessageBox.information(self, "Sucesso", f"Schema '{schema}' atualizado (USAGE/CREATE).")
            else:
                QMessageBox.critical(self, "Erro", "Falha ao salvar privilégios de schema.")

        def on_error(e: Exception):
            QMessageBox.critical(self, "Erro", f"Falha ao salvar privilégios de schema: {e}")

        self._execute_async(task, on_success, on_error, "Salvando privilégios de schema...")

    def _reload_tables(self):
        """Recarrega apenas a árvore de tabelas sem mexer nos checkboxes de defaults/schema."""
        if not self.current_group:
            return
        def task():
            # Apenas força reconsulta das tabelas e privilégios de tabela
            return True
        def on_success(_):
            self._populate_privileges()
            # Reaplicar painel atual sem perder defaults (cache já mantém)
            current_item = self.schema_list.currentItem()
            if current_item:
                self._update_schema_details(current_item, None)
        def on_error(e: Exception):
            QMessageBox.critical(self, "Erro", f"Falha ao recarregar tabelas: {e}")
        self._execute_async(task, on_success, on_error, "Recarregando tabelas...")

    def _save_default_privileges(self):
        role, schema = self._current_schema_checked()
        if not role:
            return
        state = self._priv_cache.get((role, schema))
        default_perms = set(state.default_privs) if state else set()

        def task():
            return self.controller.alter_default_privileges(role, schema, "tables", default_perms, emit_signal=False)

        def on_success(success):
            if success:
                if state:
                    state.dirty_default = False
                QMessageBox.information(self, "Sucesso", f"Defaults de tabelas em '{schema}' atualizados.")
            else:
                QMessageBox.critical(self, "Erro", "Falha ao salvar defaults.")

        def on_error(e: Exception):
            QMessageBox.critical(self, "Erro", f"Falha ao salvar defaults: {e}")

        self._execute_async(task, on_success, on_error, "Salvando defaults...")

    def _collect_table_privs(self):
        tables: dict[str, dict[str, set[str]]] = {}
        for (role, schema), state in self._priv_cache.items():
            if role == self.current_group:
                tables[schema] = state.table_privs
        return tables

    def _save_table_privileges(self):
        if not self.current_group:
            QMessageBox.warning(self, "Atenção", "Selecione um grupo primeiro.")
            return
        role = self.current_group
        tables_privs = self._collect_table_privs()

        def task():
            return self.controller.apply_group_privileges(role, tables_privs, defaults_applied=True, emit_signal=False)

        def on_success(success):
            if success:
                for (r, _), st in self._priv_cache.items():
                    if r == role:
                        st.dirty_table = False
                QMessageBox.information(self, "Sucesso", "Privilégios de tabelas atualizados.")
            else:
                QMessageBox.critical(self, "Erro", "Falha ao salvar privilégios de tabelas.")

        def on_error(e: Exception):
            if isinstance(e, DependencyWarning):
                resp = QMessageBox.question(
                    self,
                    "Dependências detectadas",
                    f"{e}\nContinuar revogação com CASCADE?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if resp == QMessageBox.StandardButton.Yes:
                    try:
                        success = self.controller.apply_group_privileges(
                            role,
                            tables_privs,
                            defaults_applied=True,
                            emit_signal=False,
                            check_dependencies=False,
                        )
                        if success:
                            for (r, _), st in self._priv_cache.items():
                                if r == role:
                                    st.dirty_table = False
                            QMessageBox.information(
                                self, "Sucesso", "Privilégios de tabelas atualizados."
                            )
                        else:
                            QMessageBox.critical(
                                self, "Erro", "Falha ao salvar privilégios de tabelas."
                            )
                    except Exception as err:
                        QMessageBox.critical(
                            self, "Erro", f"Falha ao salvar privilégios de tabelas: {err}"
                        )
                # If user cancels, do nothing
            else:
                QMessageBox.critical(self, "Erro", f"Falha ao salvar privilégios de tabelas: {e}")

        self._execute_async(task, on_success, on_error, "Salvando privilégios de tabelas...")

    # Mantém método antigo para compatibilidade interna, chamando os três (se necessário)
    def _save_privileges(self):  # legacy
        self._save_schema_privileges()
        self._save_default_privileges()
        self._save_table_privileges()

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
