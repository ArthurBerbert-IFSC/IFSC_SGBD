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
    QMessageBox,
    QProgressDialog,
    QGroupBox,
    QTabWidget,
    QCheckBox,
    QToolBar,
    QInputDialog,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon
from pathlib import Path
from dataclasses import dataclass, field
import logging
import psycopg2.errors

from config.permission_templates import PERMISSION_TEMPLATES
from gerenciador_postgres.controllers.groups_controller import DependencyWarning
from gerenciador_postgres.db_manager import PRIVILEGE_WHITELIST
logger = logging.getLogger(__name__)


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


class PrivilegesView(QWidget):
    """Janela para gerenciamento de grupos e seus privilégios."""

    def __init__(self, parent=None, controller=None, schema_controller=None):
        super().__init__(parent)
        assets_dir = Path(__file__).resolve().parents[2] / "assets"
        self.setWindowIcon(QIcon(str(assets_dir / "icone.png")))
        self.controller = controller
        self.schema_controller = schema_controller
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
        # Armazena privilégios de banco e indicador de alterações
        self.treeDbPrivileges = None
        self.btnSaveDb = None
        self._db_privs: set[str] = set()
        self._db_dirty: bool = False
        self._setup_ui()
        self._connect_signals()
        if self.controller:
            self.controller.data_changed.connect(self.refresh_groups)
            if hasattr(self.controller, "members_changed"):
                self.controller.members_changed.connect(self._refresh_members)
        if self.schema_controller:
            self.schema_controller.data_changed.connect(self._populate_privileges)
        self.refresh_groups()

    # ------------------------------------------------------------------
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("Grupos"))
        self.lstGroups = QListWidget()
        left_layout.addWidget(self.lstGroups)

        # Painel de membros com possibilidade de recolher/expandir
        self.members_box = QGroupBox("Membros do Grupo")
        self.members_box.setCheckable(True)
        self.members_box.setChecked(False)
        members_layout = QVBoxLayout()
        self.lstMembers = QListWidget()
        self.btnManageMembers = QPushButton("Gerenciar membros…")
        members_layout.addWidget(self.lstMembers)
        members_layout.addWidget(self.btnManageMembers)
        self.members_box.setLayout(members_layout)
        # Conteúdo oculto inicialmente
        self.lstMembers.setVisible(False)
        self.btnManageMembers.setVisible(False)
        left_layout.addWidget(self.members_box)
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

        # Tabs para organização de privilégios
        self.tabs = QTabWidget()

        # --- Banco ---
        db_tab = QWidget()
        db_layout = QVBoxLayout(db_tab)
        self.treeDbPrivileges = QTreeWidget()
        self.treeDbPrivileges.setHeaderLabels(["Privilégio"])
        db_layout.addWidget(self.treeDbPrivileges)
        self.btnSaveDb = QPushButton("Salvar Banco")
        db_layout.addWidget(self.btnSaveDb)
        self.tabs.addTab(db_tab, "Banco")

        # --- Schemas (inclui defaults) ---
        schema_tab = QWidget()
        schema_tab_layout = QVBoxLayout(schema_tab)
        self.schema_group = QGroupBox("Gerenciamento de Schemas")
        schema_management_layout = QVBoxLayout()
        self.schema_toolbar = QToolBar()
        self.btnSchemaNew = QPushButton("Novo Schema")
        self.btnSchemaDelete = QPushButton("Excluir")
        self.btnSchemaOwner = QPushButton("Alterar Owner")
        self.btnSchemaDelete.setEnabled(False)
        self.btnSchemaOwner.setEnabled(False)
        self.schema_toolbar.addWidget(self.btnSchemaNew)
        self.schema_toolbar.addWidget(self.btnSchemaDelete)
        self.schema_toolbar.addWidget(self.btnSchemaOwner)
        schema_management_layout.addWidget(self.schema_toolbar)
        detail_layout = QHBoxLayout()
        self.schema_list = QListWidget()
        self.schema_list.setMaximumWidth(250)
        detail_layout.addWidget(self.schema_list)
        self.schema_details_panel = QWidget()
        self.schema_details_layout = QVBoxLayout(self.schema_details_panel)
        detail_layout.addWidget(self.schema_details_panel, 1)
        schema_management_layout.addLayout(detail_layout)
        self.schema_group.setLayout(schema_management_layout)
        schema_tab_layout.addWidget(self.schema_group)
        schema_btns = QHBoxLayout()
        self.btnSaveSchema = QPushButton("Salvar Schema")
        self.btnSaveDefaults = QPushButton("Salvar Defaults")
        schema_btns.addWidget(self.btnSaveSchema)
        schema_btns.addWidget(self.btnSaveDefaults)
        schema_btns.addStretch(1)
        schema_tab_layout.addLayout(schema_btns)
        self.tabs.addTab(schema_tab, "Schemas")

        # --- Tabelas ---
        tables_tab = QWidget()
        tables_layout = QVBoxLayout(tables_tab)
        self.treePrivileges = QTreeWidget()
        self.treePrivileges.setHeaderLabels([
            "Schema/Tabela", "SELECT", "INSERT", "UPDATE", "DELETE"
        ])
        tables_layout.addWidget(self.treePrivileges)
        tables_btns = QHBoxLayout()
        self.btnSaveTables = QPushButton("Salvar Tabelas")
        self.btnReloadTables = QPushButton("Recarregar Tabelas")
        self.btnSweep = QPushButton("Sincronizar (Full Sweep)")
        tables_btns.addWidget(self.btnSaveTables)
        tables_btns.addWidget(self.btnReloadTables)
        tables_btns.addWidget(self.btnSweep)
        tables_btns.addStretch(1)
        tables_layout.addLayout(tables_btns)
        self.tabs.addTab(tables_tab, "Tabelas")

        right_layout.addWidget(self.tabs)

        # Botões gerais
        self.btnSaveAll = QPushButton("Salvar Tudo")
        actions_layout = QHBoxLayout()
        actions_layout.addWidget(self.btnSaveAll)
        actions_layout.addStretch(1)
        right_layout.addLayout(actions_layout)

        self.splitter.addWidget(right_panel)
        layout.addWidget(self.splitter)
        self.setLayout(layout)

        # Initial disabled state
        for w in [
            self.treeDbPrivileges,
            self.schema_group,
            self.treePrivileges,
            self.btnApplyTemplate,
            self.btnSaveDb,
            self.btnSaveSchema,
            self.btnSaveDefaults,
            self.btnSaveTables,
            self.btnSaveAll,
            self.btnReloadTables,
            self.btnSweep,
            self.members_box,
        ]:
            w.setEnabled(False)

    def _connect_signals(self):
        self.lstGroups.currentItemChanged.connect(self._on_group_selected)
        self.schema_list.currentItemChanged.connect(self._update_schema_details)
        self.btnSchemaNew.clicked.connect(self.on_new_schema)
        self.btnSchemaDelete.clicked.connect(self.on_delete_schema)
        self.btnSchemaOwner.clicked.connect(self.on_change_owner)
        self.btnApplyTemplate.clicked.connect(self._apply_template)
        self.btnSaveDb.clicked.connect(self._save_db_privileges)
        self.btnSaveSchema.clicked.connect(self._save_schema_privileges)
        self.btnSaveDefaults.clicked.connect(self._save_default_privileges)
        self.btnSaveTables.clicked.connect(self._save_table_privileges)
        self.btnSaveAll.clicked.connect(self._save_all_privileges)
        self.btnReloadTables.clicked.connect(self._reload_tables)
        self.btnSweep.clicked.connect(self._sweep_privileges)
        self.treeDbPrivileges.itemChanged.connect(self._on_db_priv_changed)
        self.treePrivileges.itemChanged.connect(self._on_table_priv_changed)
        self.members_box.toggled.connect(self._toggle_members_panel)
        self.btnManageMembers.clicked.connect(self._open_members_manager)

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
        if self.controller:
            self.templates = self.controller.list_privilege_templates()
        else:
            self.templates = PERMISSION_TEMPLATES
        self.cmbTemplates.clear()
        self.cmbTemplates.addItems(self.templates.keys())
    # ------------------------------------------------------------------
    # Métodos utilitários de estado / indicadores (reintroduzidos)
    # ------------------------------------------------------------------
    def _schema_item_name(self, item: QListWidgetItem) -> str:
        """Retorna o nome base do schema (sem indicador de modificação)."""
        if not item:
            return ""
        text = item.text().strip()
        # remove sufixo ' *' se presente
        if text.endswith(" *"):
            return text[:-2]
        return text

    # Utilitário para tratar nomes de schema vindos diretamente de strings (ex: item.text())
    def _strip_dirty_marker(self, name: str) -> str:
        if not name:
            return ""
        name = name.strip()
        if name.endswith(" *"):
            return name[:-2]
        return name

    def _refresh_schema_dirty_indicators(self):
        """Atualiza a exibição (asterisco) dos schemas com alterações pendentes."""
        self.schema_list.blockSignals(True)
        try:
            for i in range(self.schema_list.count()):
                item = self.schema_list.item(i)
                base = self._schema_item_name(item)
                state = self._priv_cache.get((self.current_group, base)) if self.current_group else None
                dirty = bool(state and state.dirty)
                desired = base + (" *" if dirty else "")
                if item.text() != desired:
                    item.setText(desired)
        finally:
            self.schema_list.blockSignals(False)

    def _update_save_all_state(self):
        dirty = self._db_dirty
        if not dirty and self.current_group:
            for (role, _), st in self._priv_cache.items():
                if role == self.current_group and st.dirty:
                    dirty = True
                    break
        self.btnSaveAll.setEnabled(bool(dirty))

    # ------------------------------------------------------------------
    # Handlers de gerenciamento de schemas
    # ------------------------------------------------------------------
    def on_new_schema(self):
        name, ok = QInputDialog.getText(self, "Novo Schema", "Nome do schema:")
        if not ok or not name:
            return
        owner = None
        roles = []
        supers = set()
        if self.schema_controller:
            try:
                roles = self.schema_controller.list_owner_candidates(include_superusers=True)
                supers = set(self.schema_controller.list_superusers())
            except Exception as e:
                logger.error(f"Falha ao listar candidatos a owner: {e}")
        decorated = []
        for r in roles:
            if r in supers:
                decorated.append((0, f"[{r}]", r))
            else:
                decorated.append((1, r, r))
        decorated.sort()
        display_items = [d[1] for d in decorated]
        items = [""] + display_items
        owner, ok2 = QInputDialog.getItem(
            self,
            "Proprietário",
            "Owner (opcional) – superusuários entre []:",
            items,
            0,
            False,
        )
        if not ok2:
            owner = None
        else:
            if owner and owner.startswith("[") and owner.endswith("]"):
                owner = owner[1:-1]
        try:
            if self.schema_controller:
                self.schema_controller.create_schema(name, owner or None)
            QMessageBox.information(self, "Sucesso", f"Schema '{name}' criado.")
            self._populate_privileges()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível criar o schema:\n{e}")
            logger.error(f"Falha ao criar schema '{name}': {e}")

    def on_delete_schema(self):
        item = self.schema_list.currentItem()
        if not item:
            return
        name = self._schema_item_name(item)
        reply = QMessageBox.question(
            self,
            "Confirmar",
            f"Excluir schema '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            if self.schema_controller:
                self.schema_controller.delete_schema(name)
            QMessageBox.information(self, "Sucesso", f"Schema '{name}' removido.")
            self._populate_privileges()
        except Exception as e:
            def _root_exc(ex):
                cur = ex
                while getattr(cur, "__cause__", None) is not None:
                    cur = cur.__cause__
                return cur

            root = _root_exc(e)
            message = str(root)
            pgcode = getattr(root, "pgcode", None)
            is_deps_err = False
            try:
                is_deps_err = isinstance(root, psycopg2.errors.DependentObjectsStillExist)
            except Exception:
                is_deps_err = False
            if not is_deps_err:
                is_deps_err = (pgcode == "2BP01") or ("other objects depend on it" in message)

            if is_deps_err:
                cascade_reply = QMessageBox.question(
                    self,
                    "Objetos Dependentes Encontrados",
                    f"O schema '{name}' possui objetos dependentes (tabelas, etc.).\n\n"
                    f"Deseja remover o schema e TODOS os objetos dependentes?\n\n"
                    f"ATENÇÃO: Esta ação é irreversível!",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if cascade_reply == QMessageBox.StandardButton.Yes:
                    try:
                        if self.schema_controller:
                            self.schema_controller.delete_schema(name, cascade=True)
                        QMessageBox.information(self, "Sucesso", f"Schema '{name}' e objetos dependentes removidos.")
                        self._populate_privileges()
                    except Exception as cascade_e:
                        QMessageBox.critical(self, "Erro", f"Não foi possível remover o schema com CASCADE:\n{cascade_e}")
                        logger.error(f"Falha ao remover schema '{name}' com CASCADE: {cascade_e}")
                else:
                    QMessageBox.information(self, "Cancelado", "Exclusão sem CASCADE cancelada pelo usuário.")
                    logger.info(
                        f"Exclusão de schema '{name}' sem CASCADE cancelada pelo usuário devido a objetos dependentes."
                    )
            else:
                QMessageBox.critical(self, "Erro", f"Não foi possível remover o schema:\n{e}")
                logger.error(f"Falha ao remover schema '{name}': {e}")

    def on_change_owner(self):
        item = self.schema_list.currentItem()
        if not item:
            return
        name = self._schema_item_name(item)
        roles = []
        supers = set()
        if self.schema_controller:
            try:
                roles = self.schema_controller.list_owner_candidates(include_superusers=True)
                supers = set(self.schema_controller.list_superusers())
            except Exception as e:
                logger.error(f"Falha ao listar candidatos a owner: {e}")
        decorated = []
        for r in roles:
            if r in supers:
                decorated.append((0, f"[{r}]", r))
            else:
                decorated.append((1, r, r))
        decorated.sort()
        display_items = [d[1] for d in decorated]
        new_owner, ok = QInputDialog.getItem(
            self,
            "Alterar Owner",
            "Novo owner – superusuários entre []:",
            display_items,
            0,
            False,
        )
        if ok and new_owner and new_owner.startswith("[") and new_owner.endswith("]"):
            new_owner = new_owner[1:-1]
        if not ok or not new_owner:
            return
        try:
            if self.schema_controller:
                self.schema_controller.change_owner(name, new_owner)
            QMessageBox.information(self, "Sucesso", f"Owner de '{name}' alterado.")
            self._populate_privileges()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível alterar owner:\n{e}")
            logger.error(f"Falha ao alterar owner de '{name}': {e}")

    def _get_state(self, role: str, schema: str) -> PrivilegesState:
        state = self._priv_cache.get((role, schema))
        if not state:
            state = PrivilegesState()
            self._priv_cache[(role, schema)] = state
        return state

    def _update_schema_priv(self, role: str, schema: str, priv: str, checked: bool):
        state = self._get_state(role, schema)
        before = set(state.schema_privs)
        if checked:
            state.schema_privs.add(priv)
        else:
            state.schema_privs.discard(priv)
        if before != state.schema_privs:
            state.dirty_schema = True
            logger.debug("[PrivilegesView] schema_priv_changed role=%s schema=%s priv=%s now=%s", role, schema, priv, state.schema_privs)
            self._refresh_schema_dirty_indicators()
            self._update_save_all_state()

    def _update_default_priv(self, role: str, schema: str, priv: str, checked: bool):
        state = self._get_state(role, schema)
        before = set(state.default_privs)
        if checked:
            state.default_privs.add(priv)
        else:
            state.default_privs.discard(priv)
        if before != state.default_privs:
            state.dirty_default = True
            logger.debug("[PrivilegesView] default_priv_changed role=%s schema=%s priv=%s now=%s", role, schema, priv, state.default_privs)
            self._refresh_schema_dirty_indicators()
            self._update_save_all_state()

    def _on_table_priv_changed(self, item: QTreeWidgetItem, column: int):
        """Atualiza cache ao marcar/desmarcar privilégios de tabela."""
        # Ignora se não há grupo selecionado ou item inválido
        if not self.current_group or not item:
            return
        parent = item.parent()
        # Somente processa linhas de tabelas (que possuem pai = schema)
        if parent is None:
            return
        schema = parent.text(0)
        role = self.current_group
        state = self._get_state(role, schema)
        table = item.text(0)
        col_map = {1: "SELECT", 2: "INSERT", 3: "UPDATE", 4: "DELETE"}
        # Calcula conjunto após mudança
        new_perms = set()
        for col, label in col_map.items():
            if item.checkState(col) == Qt.CheckState.Checked:
                new_perms.add(label)
        old_perms = state.table_privs.get(table, set())
        if new_perms != old_perms:
            state.table_privs[table] = new_perms
            state.dirty_table = True
            logger.debug("[PrivilegesView] table_priv_changed role=%s schema=%s table=%s old=%s new=%s", role, schema, table, old_perms, new_perms)
            self._refresh_schema_dirty_indicators()
            self._update_save_all_state()

    def _on_db_priv_changed(self, item: QTreeWidgetItem, column: int):
        """Atualiza cache para privilégios de banco."""
        if not self.current_group or not item:
            return
        priv = item.text(0)
        checked = item.checkState(0) == Qt.CheckState.Checked
        if checked:
            self._db_privs.add(priv)
        else:
            self._db_privs.discard(priv)
        self._db_dirty = True
        self._update_save_all_state()

    def _on_group_selected(self, current, previous):
        if previous and not self._check_dirty_for_group(previous.text()):
            self.lstGroups.blockSignals(True)
            self.lstGroups.setCurrentItem(previous)
            self.lstGroups.blockSignals(False)
            return
        if not current:
            # Limpa estado quando nada selecionado
            self.current_group = None
            self.treeDbPrivileges.setEnabled(False)
            self.schema_group.setEnabled(False)
            self.treePrivileges.setEnabled(False)
            self.btnApplyTemplate.setEnabled(False)
            self.btnSaveDb.setEnabled(False)
            self.btnSaveSchema.setEnabled(False)
            self.btnSaveDefaults.setEnabled(False)
            self.btnSaveTables.setEnabled(False)
            self.btnSweep.setEnabled(False)
            self.members_box.setEnabled(False)
            self.members_box.setChecked(False)
            self.lstMembers.clear()
            self.schema_list.clear()
            self._clear_layout(self.schema_details_layout)
            return

        # Novo grupo selecionado
        self.current_group = current.text()
        for w in [
            self.treeDbPrivileges,
            self.schema_group,
            self.treePrivileges,
            self.btnApplyTemplate,
            self.btnSaveDb,
            self.btnSaveSchema,
            self.btnSaveDefaults,
            self.btnSaveTables,
            self.btnReloadTables,
            self.btnSweep,
            self.members_box,
        ]:
            w.setEnabled(True)
        self._populate_privileges()
        self._refresh_members()

    # ------------------------------------------------------------------
    def _toggle_members_panel(self, checked: bool):
        self.lstMembers.setVisible(checked)
        self.btnManageMembers.setVisible(checked)

    def _open_members_manager(self):
        if not self.controller or not self.current_group:
            return
        from gerenciador_postgres.gui.users_view import UsersView

        self._members_window = UsersView(
            controller=self.controller, initial_group=self.current_group
        )
        self._members_window.show()

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
        # Garante que usamos sempre o nome base (sem asterisco) para lookup
        schema = self._strip_dirty_marker(schema)
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
        schema_base = self._strip_dirty_marker(schema)
        state = self._priv_cache.get((role, schema_base))
        if not state:
            return True
        ok1 = self.controller.grant_schema_privileges(
            role, schema_base, state.schema_privs, emit_signal=False
        )
        ok2 = self.controller.alter_default_privileges(
            role, schema_base, "tables", state.default_privs, emit_signal=False
        )
        ok3 = self.controller.apply_group_privileges(
            role, {schema_base: state.table_privs}, defaults_applied=True, emit_signal=False
        )
        if ok1 and ok2 and ok3:
            state.dirty_schema = state.dirty_default = state.dirty_table = False
            return True
        return False

    def _fetch_db_privs(self, role: str) -> set[str]:
        try:
            conn = self.controller.role_manager.dao.conn
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT a.privilege_type, a.is_grantable
                    FROM pg_database d
                    CROSS JOIN LATERAL aclexplode(
                        COALESCE(d.datacl, acldefault('d', d.datdba))
                    ) AS a
                    JOIN pg_roles gr ON gr.oid = a.grantee
                    WHERE d.datname = current_database()
                      AND gr.rolname = %s
                    """,
                    (role,),
                )
                return {priv for priv, _ in cur.fetchall()}
        except Exception:
            return set()

    def _populate_privileges(self):
        if not self.controller or not self.current_group:
            return
        role = self.current_group
        try:
            self.schema_tables = self.controller.get_schema_tables()
            table_privs = self.controller.get_group_privileges(role)
            db_privs = self._fetch_db_privs(role)
        except Exception as e:  # pragma: no cover
            logging.exception("Erro ao ler privilégios do grupo")
            QMessageBox.warning(
                self,
                "Erro",
                f"Não foi possível ler os privilégios.\nMotivo: {e}",
            )
            self.schema_tables, table_privs, db_privs = {}, {}, set()

        self.schema_list.blockSignals(True)
        self.schema_list.clear()
        for schema in sorted(self.schema_tables.keys()):
            item = QListWidgetItem(schema)
            item.setData(Qt.ItemDataRole.UserRole, schema)
            self.schema_list.addItem(item)
        self.schema_list.blockSignals(False)
        if self.schema_list.count() > 0:
            self.schema_list.setCurrentRow(0)
        self._refresh_schema_dirty_indicators()

        # Popula privilégios de banco
        self.treeDbPrivileges.blockSignals(True)
        self.treeDbPrivileges.clear()
        for priv in sorted(PRIVILEGE_WHITELIST["DATABASE"]):
            item = QTreeWidgetItem([priv])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            state = (
                Qt.CheckState.Checked if priv in db_privs else Qt.CheckState.Unchecked
            )
            item.setCheckState(0, state)
            self.treeDbPrivileges.addTopLevelItem(item)
        self.treeDbPrivileges.blockSignals(False)
        self._db_privs = set(db_privs)
        self._db_dirty = False

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
        has_item = current_item is not None
        self.btnSchemaDelete.setEnabled(has_item)
        self.btnSchemaOwner.setEnabled(has_item)
        if previous_item and not self._check_dirty_for_schema(self.current_group, self._strip_dirty_marker(previous_item.text())):
            self.schema_list.blockSignals(True)
            self.schema_list.setCurrentItem(previous_item)
            self.schema_list.blockSignals(False)
            return
        if not current_item or not self.controller or not self.current_group:
            return
        # Nome exibido pode conter marcador de sujo; usamos base para operações e cache
        schema_name_display = current_item.text()
        schema_name = self._strip_dirty_marker(schema_name_display)
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
            logger.debug(
                "[PrivilegesView] _update_schema_details role=%s schema=%s db_schema_privs=%s db_default_privs=%s cached_schema=%s cached_default=%s",
                role,
                schema_name,
                schema_privs_db,
                default_privs_db,
                schema_privs,
                default_privs,
            )
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
        try:
            self.cb_usage.setTristate(False)
        except Exception:
            pass
        usage_create_layout.addWidget(self.cb_usage)
        self.cb_create = QCheckBox("CREATE")
        self.cb_create.setChecked("CREATE" in schema_privs)
        try:
            self.cb_create.setTristate(False)
        except Exception:
            pass
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
            lambda st, r=role, s=schema_name: self._update_schema_priv(
                r,
                s,
                "USAGE",
                Qt.CheckState(st) == Qt.CheckState.Checked,
            )
        )
        self.cb_usage.toggled.connect(
            lambda checked, r=role, s=schema_name: logger.debug(
                "[PrivilegesView] usage.toggled role=%s schema=%s checked=%s", r, s, checked
            )
        )
        self.cb_create.stateChanged.connect(
            lambda st, r=role, s=schema_name: self._update_schema_priv(
                r,
                s,
                "CREATE",
                Qt.CheckState(st) == Qt.CheckState.Checked,
            )
        )
        self.cb_create.toggled.connect(
            lambda checked, r=role, s=schema_name: logger.debug(
                "[PrivilegesView] create.toggled role=%s schema=%s checked=%s", r, s, checked
            )
        )
        self.cb_default_select.stateChanged.connect(
            lambda st, r=role, s=schema_name: self._update_default_priv(
                r,
                s,
                "SELECT",
                Qt.CheckState(st) == Qt.CheckState.Checked,
            )
        )
        self.cb_default_insert.stateChanged.connect(
            lambda st, r=role, s=schema_name: self._update_default_priv(
                r,
                s,
                "INSERT",
                Qt.CheckState(st) == Qt.CheckState.Checked,
            )
        )
        self.cb_default_update.stateChanged.connect(
            lambda st, r=role, s=schema_name: self._update_default_priv(
                r,
                s,
                "UPDATE",
                Qt.CheckState(st) == Qt.CheckState.Checked,
            )
        )
        self.cb_default_delete.stateChanged.connect(
            lambda st, r=role, s=schema_name: self._update_default_priv(
                r,
                s,
                "DELETE",
                Qt.CheckState(st) == Qt.CheckState.Checked,
            )
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
        return self.current_group, self._schema_item_name(item)

    def _save_db_privileges(self):
        if not self.current_group:
            QMessageBox.warning(self, "Atenção", "Selecione um grupo primeiro.")
            return
        role = self.current_group
        privs = {
            self.treeDbPrivileges.topLevelItem(i).text(0)
            for i in range(self.treeDbPrivileges.topLevelItemCount())
            if self.treeDbPrivileges.topLevelItem(i).checkState(0)
            == Qt.CheckState.Checked
        }

        def task():
            return self.controller.grant_database_privileges(role, privs)

        def on_success(success):
            if success:
                self._db_privs = set(privs)
                self._db_dirty = False
                QMessageBox.information(self, "Sucesso", "Privilégios de banco atualizados.")
            else:
                QMessageBox.critical(self, "Erro", "Falha ao salvar privilégios de banco.")
            self._update_save_all_state()

        def on_error(e: Exception):
            QMessageBox.critical(self, "Erro", f"Falha ao salvar privilégios de banco: {e}")

        self._execute_async(task, on_success, on_error, "Salvando privilégios de banco...")

    def _save_schema_privileges(self):
        role, schema = self._current_schema_checked()
        if not role:
            return
        state = self._priv_cache.get((role, schema))
        schema_perms = set(state.schema_privs) if state else set()
        # Consulta estado atual no banco para feedback ao usuário
        try:
            current_db = self.controller.get_schema_level_privileges(role).get(schema, set())
        except Exception:
            current_db = set()
        if not schema_perms and not current_db:
            QMessageBox.information(
                self,
                "Nada a salvar",
                "Nenhum privilégio selecionado e o schema já não possui USAGE/CREATE para este grupo.",
            )
            logger.debug(
                "[PrivilegesView] Abort save (nothing to do) role=%s schema=%s perms_ui=%s perms_db=%s",
                role,
                schema,
                schema_perms,
                current_db,
            )
            return
        logger.debug(
            "[PrivilegesView] _save_schema_privileges role=%s schema=%s to_save=%s state=%s",
            role,
            schema,
            schema_perms,
            state.schema_privs if state else None,
        )

        def task():
            return self.controller.grant_schema_privileges(role, schema, schema_perms, emit_signal=False)

        def on_success(success):
            if success:
                if state:
                    state.dirty_schema = False
                QMessageBox.information(self, "Sucesso", f"Schema '{schema}' atualizado (USAGE/CREATE).")
                logger.debug(
                    "[PrivilegesView] Saved schema privileges ok role=%s schema=%s saved=%s",
                    role,
                    schema,
                    schema_perms,
                )
                # Re-read from DB to confirm and refresh panel
                try:
                    fresh = self.controller.get_schema_level_privileges(role)
                    new_set = fresh.get(schema, set())
                    logger.debug(
                        "[PrivilegesView] Post-save recheck role=%s schema=%s db_now=%s",
                        role,
                        schema,
                        new_set,
                    )
                    if state:
                        state.schema_privs = set(new_set)
                    # Force refresh of detail panel (without losing selection)
                    current_item = self.schema_list.currentItem()
                    if current_item and current_item.text() == schema:
                        self._update_schema_details(current_item, None)
                except Exception as e2:
                    logger.debug("[PrivilegesView] Post-save refresh failed: %s", e2)
            else:
                QMessageBox.critical(self, "Erro", "Falha ao salvar privilégios de schema.")
                logger.debug(
                    "[PrivilegesView] Failed saving schema privileges role=%s schema=%s intended=%s",
                    role,
                    schema,
                    schema_perms,
                )
            self._update_save_all_state()

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
            self._update_save_all_state()

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
            self._update_save_all_state()

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

    def _save_all_privileges(self):
        if not self.current_group:
            QMessageBox.warning(self, "Atenção", "Selecione um grupo primeiro.")
            return
        role = self.current_group
        dirty_keys = [k for k, st in self._priv_cache.items() if k[0] == role and st.dirty]
        db_dirty = self._db_dirty
        if not dirty_keys and not db_dirty:
            QMessageBox.information(self, "Nada a salvar", "Não há alterações pendentes para este grupo.")
            return

        def task():
            ok_all = True
            if db_dirty:
                ok_all = self.controller.grant_database_privileges(role, self._db_privs) and ok_all
                if ok_all:
                    self._db_dirty = False
            for _, schema in dirty_keys:
                if not self._save_state_sync(role, schema):
                    ok_all = False
            return ok_all
        def on_success(success):
            if success:
                QMessageBox.information(self, "Sucesso", "Todas as alterações foram salvas.")
            else:
                QMessageBox.warning(self, "Parcial", "Algumas alterações não puderam ser salvas.")
            self._refresh_schema_dirty_indicators()
            self._update_save_all_state()
        def on_error(e: Exception):
            QMessageBox.critical(self, "Erro", f"Falha ao salvar tudo: {e}")
        self._execute_async(task, on_success, on_error, "Salvando tudo...")

    # Mantém método antigo para compatibilidade interna, chamando os três (se necessário)
    def _save_privileges(self):  # legacy
        self._save_db_privileges()
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
                # Após sincronizar no banco, descartamos cache antigo para o grupo
                removed_any = False
                for key in list(self._priv_cache.keys()):
                    if key[0] == group_name:
                        self._priv_cache.pop(key, None)
                        removed_any = True
                # Se ainda estamos visualizando este grupo, repopula privilégios
                if self.current_group == group_name:
                    self._populate_privileges()
                    current_item = self.schema_list.currentItem()
                    if current_item:
                        self._update_schema_details(current_item, None)
                self._refresh_schema_dirty_indicators()
                QMessageBox.information(
                    self, "Concluído", f"Privilégios do grupo '{group_name}' sincronizados." + (" (cache atualizado)" if removed_any else "")
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
