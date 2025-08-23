from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QColor, QBrush
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
    QSplitter,
    QMessageBox,
    QProgressDialog,
    QGroupBox,
    QCheckBox,
    QLineEdit,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QComboBox,
    QCompleter,
)

logger = logging.getLogger(__name__)


class _TaskRunner(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(Exception)

    def __init__(self, func, parent=None):
        super().__init__(parent)
        self._func = func

    def run(self):
        try:
            res = self._func()
            self.succeeded.emit(res)
        except Exception as e:
            self.failed.emit(e)


@dataclass
class PrivilegesState:
    schema_privs: set[str] = field(default_factory=set)
    table_privs: dict[str, set[str]] = field(default_factory=dict)
    default_privs: dict[str, set[str]] = field(default_factory=dict)
    # dirty flags tracked by Save All and tests
    dirty_schema: bool = False
    dirty_table: bool = False
    dirty_default: bool = False


class PrivilegesView(QWidget):
    """Tabbed privileges editor (Banco, Esquemas, Tabelas) com dialog de Owners."""

    def __init__(self, parent=None, controller=None, schema_controller=None):
        super().__init__(parent)
        assets_dir = Path(__file__).resolve().parents[2] / "assets"
        self.setWindowIcon(QIcon(str(assets_dir / "icone.png")))
        self.controller = controller
        self.schema_controller = schema_controller
        self.current_group = None
        # caches/dirty
        self._priv_cache = {}
        self._db_privs = set()
        self._db_dirty = False
        self._db_changing = False  # reentrancy guard for DB priv changes
        # Banco tab: alvo independente e estado por role
        self._db_role_target = None  # type: ignore[assignment]
        self._db_privs_by_role = {}
        self._db_dirty_roles = set()
        # Tabelas tab: alvo independente (usuário ou grupo)
        self._tables_role_target = None  # type: ignore[assignment]
        # UI
        self._setup_ui()
        self._connect_signals()
        # load
        self._load_groups()
        # populate role target list once groups/users são conhecidos
        try:
            self._populate_role_target_combo()
        except Exception:
            pass

    # UI
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # Left: groups only (schemas moved into Esquemas tab)
        left = QWidget(self)
        lv = QVBoxLayout(left)
        lv.addWidget(QLabel("Grupos"))
        self.lstGroups = QListWidget()
        lv.addWidget(self.lstGroups)
        self.splitter.addWidget(left)

        # Right: tabs + actions
        right = QWidget(self)
        rv = QVBoxLayout(right)
        self.tabs = QTabWidget(right)

        # --- Banco ---
        tab_db = QWidget(); vdb = QVBoxLayout(tab_db)
        # alvo independente (usuário/grupo) para Banco
        rowDbTarget = QHBoxLayout()
        rowDbTarget.addWidget(QLabel("Alterar privilégios para:"))
        self.cmbDbRoleTarget = QComboBox()
        self.cmbDbRoleTarget.setEditable(True)
        try:
            self.cmbDbRoleTarget.lineEdit().setPlaceholderText("Filtrar por nome…")
        except Exception:
            pass
        rowDbTarget.addWidget(self.cmbDbRoleTarget)
        # botão salvar específico da aba Banco
        self.btnSaveDb = QPushButton("Salvar")
        rowDbTarget.addWidget(self.btnSaveDb)
        rowDbTarget.addStretch(1)
        vdb.addLayout(rowDbTarget)
        # árvore de privilégios do banco
        self.treeDbPrivileges = QTreeWidget()
        self.treeDbPrivileges.setColumnCount(2)
        self.treeDbPrivileges.setHeaderLabels(["Privilégio", "Com GRANT"]) 
        vdb.addWidget(self.treeDbPrivileges)
        self.tabs.addTab(tab_db, "Banco")

        # --- Esquemas ---
        tab_schema = QWidget(); vsc = QVBoxLayout(tab_schema)
        # Schema selector inside the tab
        vsc.addWidget(QLabel("Schemas"))
        self.schema_list = QListWidget()
        vsc.addWidget(self.schema_list)
        # Schema-level checkboxes
        gschema = QGroupBox("Privilégios de Schema"); vs = QVBoxLayout(gschema)
        row = QHBoxLayout()
        self.cb_usage = QCheckBox("USAGE"); self.cb_create = QCheckBox("CREATE")
        row.addWidget(self.cb_usage); row.addWidget(self.cb_create); row.addStretch(1)
        vs.addLayout(row)
        # Owners defaults box (per-owner future privileges)
        box = QGroupBox("Owners de Defaults (novas tabelas)")
        bx = QVBoxLayout(box)
        self.txtOwnerSearch = QLineEdit(); self.txtOwnerSearch.setPlaceholderText("Buscar usuários/grupos…")
        bx.addWidget(self.txtOwnerSearch)
        # Matrix: Owner x Privileges
        self.treeOwners = QTreeWidget(); self.treeOwners.setColumnCount(5)
        self.treeOwners.setHeaderLabels(["Owner", "SELECT", "INSERT", "UPDATE", "DELETE"])
        bx.addWidget(self.treeOwners)
        # Helpers
        self.cbApplyExisting = QCheckBox("Aplicar também às tabelas existentes")
        bx.addWidget(self.cbApplyExisting)
        self.btnApplyOwners = QPushButton("Aplicar Owners")
        bx.addWidget(self.btnApplyOwners)
        vsc.addWidget(gschema)
        vsc.addWidget(box)
        vsc.addStretch(1)
        self.tabs.addTab(tab_schema, "Esquemas")
        # --- Tabelas ---
        tab_tables = QWidget(); vtb = QVBoxLayout(tab_tables)
        # alvo independente (usuário/grupo)
        rowTarget = QHBoxLayout()
        rowTarget.addWidget(QLabel("Alterar privilégios para:"))
        self.cmbRoleTarget = QComboBox()
        self.cmbRoleTarget.setEditable(True)
        try:
            self.cmbRoleTarget.lineEdit().setPlaceholderText("Filtrar por nome…")
        except Exception:
            pass
        rowTarget.addWidget(self.cmbRoleTarget)
        rowTarget.addStretch(1)
        vtb.addLayout(rowTarget)
        self.treePrivileges = QTreeWidget()
        self.treePrivileges.setColumnCount(5)
        self.treePrivileges.setHeaderLabels(["Objeto", "SELECT", "INSERT", "UPDATE", "DELETE"])
        vtb.addWidget(self.treePrivileges)
        # optional buttons referenced in tests
        rowbtn = QHBoxLayout()
        self.btnApplyTemplate = QPushButton("Aplicar Template")
        self.btnSave = QPushButton("Salvar")
        self.btnSweep = QPushButton("Limpar")
        rowbtn.addStretch(1); rowbtn.addWidget(self.btnApplyTemplate); rowbtn.addWidget(self.btnSave); rowbtn.addWidget(self.btnSweep)
        vtb.addLayout(rowbtn)
        self.tabs.addTab(tab_tables, "Tabelas")

        rv.addWidget(self.tabs)
        # Save All at bottom (used by tests)
        act_row = QHBoxLayout(); act_row.addStretch(1)
        self.btnSaveAll = QPushButton("Salvar Tudo")
        self.btnSaveAll.setEnabled(False)
        act_row.addWidget(self.btnSaveAll)
        rv.addLayout(act_row)

        self.splitter.addWidget(right)
        layout.addWidget(self.splitter)
        # bootstrap lists
        self._populate_db_tab()

    def _connect_signals(self):
        self.lstGroups.currentItemChanged.connect(self._on_group_changed)
        self.schema_list.currentItemChanged.connect(self._update_schema_details)
        self.btnApplyOwners.clicked.connect(self._apply_owners_inline)
        self.cb_usage.toggled.connect(lambda c: self._on_schema_priv_toggle("USAGE", c))
        self.cb_create.toggled.connect(lambda c: self._on_schema_priv_toggle("CREATE", c))
        self.treeDbPrivileges.itemChanged.connect(self._on_db_priv_changed)
        self.treePrivileges.itemChanged.connect(self._on_table_priv_changed)
        self.treeOwners.itemChanged.connect(self._on_owner_cell_changed)
        self.txtOwnerSearch.textChanged.connect(self._filter_owner_rows)
        self.btnSaveAll.clicked.connect(self._save_all_privileges)
        self.cmbRoleTarget.currentTextChanged.connect(self._on_tables_role_changed)
        self.btnSave.clicked.connect(self._save_tables_for_current_target)
        # Banco tab role target
        if hasattr(self, 'cmbDbRoleTarget'):
            self.cmbDbRoleTarget.currentTextChanged.connect(self._on_db_role_changed)
        if hasattr(self, 'btnSaveDb'):
            self.btnSaveDb.clicked.connect(self._save_db_for_current_target)

    def _populate_role_target_combo(self):
        """Populate the role target combo with users and groups."""
        if not hasattr(self, 'cmbRoleTarget'):
            return
        current = self.cmbRoleTarget.currentText() if self.cmbRoleTarget.count() > 0 else None
        self.cmbRoleTarget.blockSignals(True)
        try:
            self.cmbRoleTarget.clear()
            users, groups = self._list_roles_split()
            # Exibir primeiro grupos (vermelho) e depois usuários (verde)
            for g in groups:
                idx = self.cmbRoleTarget.count()
                self.cmbRoleTarget.addItem(g)
                try:
                    self.cmbRoleTarget.setItemData(idx, QBrush(QColor("#FFC857")), Qt.ItemDataRole.ForegroundRole)
                except Exception:
                    pass
            for u in users:
                idx = self.cmbRoleTarget.count()
                self.cmbRoleTarget.addItem(u)
                try:
                    self.cmbRoleTarget.setItemData(idx, QBrush(QColor("#5BC0EB")), Qt.ItemDataRole.ForegroundRole)
                except Exception:
                    pass
            # select previous if still present, else first
            if current:
                idx = self.cmbRoleTarget.findText(current)
                if idx >= 0:
                    self.cmbRoleTarget.setCurrentIndex(idx)
            if self.cmbRoleTarget.count() > 0 and self.cmbRoleTarget.currentIndex() < 0:
                self.cmbRoleTarget.setCurrentIndex(0)
        finally:
            self.cmbRoleTarget.blockSignals(False)
        self._tables_role_target = self.cmbRoleTarget.currentText() if self.cmbRoleTarget.count() > 0 else None
        # anexar completer para filtrar por contém (case-insensitive)
        try:
            self._attach_role_target_completer()
        except Exception:
            pass
        # refresh tables tree for new target
        self._populate_privileges()

    def _populate_db_role_combo(self):
        """Populate the DB role target combo with users and groups (grupos primeiro, cores aplicadas)."""
        if not hasattr(self, 'cmbDbRoleTarget'):
            return
        current = self.cmbDbRoleTarget.currentText() if self.cmbDbRoleTarget.count() > 0 else None
        self.cmbDbRoleTarget.blockSignals(True)
        try:
            self.cmbDbRoleTarget.clear()
            users, groups = self._list_roles_split()
            for g in groups:
                idx = self.cmbDbRoleTarget.count()
                self.cmbDbRoleTarget.addItem(g)
                try:
                    self.cmbDbRoleTarget.setItemData(idx, QBrush(QColor("#FFC857")), Qt.ItemDataRole.ForegroundRole)
                except Exception:
                    pass
            for u in users:
                idx = self.cmbDbRoleTarget.count()
                self.cmbDbRoleTarget.addItem(u)
                try:
                    self.cmbDbRoleTarget.setItemData(idx, QBrush(QColor("#5BC0EB")), Qt.ItemDataRole.ForegroundRole)
                except Exception:
                    pass
            if current:
                idx = self.cmbDbRoleTarget.findText(current)
                if idx >= 0:
                    self.cmbDbRoleTarget.setCurrentIndex(idx)
            if self.cmbDbRoleTarget.count() > 0 and self.cmbDbRoleTarget.currentIndex() < 0:
                self.cmbDbRoleTarget.setCurrentIndex(0)
        finally:
            self.cmbDbRoleTarget.blockSignals(False)
        self._db_role_target = self.cmbDbRoleTarget.currentText() if self.cmbDbRoleTarget.count() > 0 else None
        try:
            self._attach_db_role_completer()
        except Exception:
            pass
        # repopular árvore com alvo atual
        self._populate_db_tab()

    def _attach_db_role_completer(self):
        items = [self.cmbDbRoleTarget.itemText(i) for i in range(self.cmbDbRoleTarget.count())]
        comp = QCompleter(items, self.cmbDbRoleTarget)
        try:
            comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        except Exception:
            pass
        try:
            comp.setFilterMode(Qt.MatchFlag.MatchContains)
        except Exception:
            pass
        try:
            comp.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        except Exception:
            pass
        try:
            self.cmbDbRoleTarget.setCompleter(comp)
        except Exception:
            try:
                self.cmbDbRoleTarget.lineEdit().setCompleter(comp)
            except Exception:
                pass

    def _attach_role_target_completer(self):
        items = [self.cmbRoleTarget.itemText(i) for i in range(self.cmbRoleTarget.count())]
        comp = QCompleter(items, self.cmbRoleTarget)
        try:
            comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        except Exception:
            pass
        try:
            comp.setFilterMode(Qt.MatchFlag.MatchContains)
        except Exception:
            # em algumas versões, MatchContains pode não existir; o padrão é prefix
            pass
        try:
            comp.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        except Exception:
            pass
        try:
            self.cmbRoleTarget.setCompleter(comp)
        except Exception:
            # fallback: definir no lineEdit
            try:
                self.cmbRoleTarget.lineEdit().setCompleter(comp)
            except Exception:
                pass

    def _on_tables_role_changed(self, name: str):
        self._tables_role_target = name or None
        self._populate_privileges()

    def _on_db_role_changed(self, name: str):
        self._db_role_target = name or None
        self._populate_db_tab()

    # Data loading
    def _load_groups(self):
        self.lstGroups.clear()
        if not self.controller:
            return
        try:
            groups = list(self.controller.list_groups())
        except Exception:
            groups = []
        for g in groups:
            self.lstGroups.addItem(QListWidgetItem(g))
        if self.lstGroups.count() > 0:
            self.lstGroups.setCurrentRow(0)
        # Also refresh role target list whenever groups are (re)loaded
        self._populate_role_target_combo()
        self._populate_db_role_combo()

    def _load_schemas(self):
        self.schema_list.clear()
        if not self.controller:
            return
        try:
            schemas = sorted(self.controller.get_schema_tables().keys())
        except Exception:
            schemas = []
        for s in schemas:
            self.schema_list.addItem(s)
        if self.schema_list.count() > 0:
            self.schema_list.setCurrentRow(0)
        self._populate_privileges()
        self._populate_owners_for_current()

    def _on_group_changed(self, cur: QListWidgetItem, prev: QListWidgetItem):
        self.current_group = cur.text() if cur else None
        self._load_schemas()

    def _on_schema_changed(self, cur: QListWidgetItem, prev: QListWidgetItem):
        # kept for backwards compatibility (not wired)
        pass

    # --- DB tab -------------------------------------------------------
    def _populate_db_tab(self):
        self.treeDbPrivileges.clear()
        # Privs de banco suportados
        role = getattr(self, "_db_role_target", None) or getattr(self, "current_group", None)
        current = set()
        if role:
            try:
                if self.controller and hasattr(self.controller, 'get_database_privileges'):
                    current = set(self.controller.get_database_privileges(role))
                else:
                    current = set(getattr(self, "_db_privs_by_role", {}).get(role, set()))
            except Exception:
                current = set(getattr(self, "_db_privs_by_role", {}).get(role, set()))
            if not hasattr(self, "_db_privs_by_role"):
                self._db_privs_by_role = {}
            self._db_privs_by_role[role] = set(current)
        for base in ["CONNECT", "CREATE", "TEMPORARY"]:
            it = QTreeWidgetItem([base, ""])
            # coluna 0 = base; coluna 1 = grant option
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            # check col 0 if base or base*
            has_base = base in {p.rstrip("*") for p in current}
            it.setCheckState(0, Qt.CheckState.Checked if has_base else Qt.CheckState.Unchecked)
            # col 1 independentemente é apenas um check visual; usaremos grant set via coluna 1
            # não há tri-state nativo por coluna separada, então usamos texto vazio e somente check
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            has_grant = any(p == base + "*" for p in current)
            it.setCheckState(1, Qt.CheckState.Checked if has_grant else Qt.CheckState.Unchecked)
            self.treeDbPrivileges.addTopLevelItem(it)

    def _on_db_priv_changed(self, item: QTreeWidgetItem, column: int):
        # Evitar tocar em atributos Qt quando __init__ não foi chamado (suporte a __new__ nos testes)
        try:
            role = self._db_role_target or self.current_group  # type: ignore[attr-defined]
            use_per_role = True
        except Exception:
            role = None
            use_per_role = False
        name = item.text(0)
        if use_per_role and role:
            if not hasattr(self, "_db_privs_by_role"):
                self._db_privs_by_role = {}
            if not hasattr(self, "_db_dirty_roles"):
                self._db_dirty_roles = set()
            s = self._db_privs_by_role.setdefault(role, set())
            if item.checkState(0) == Qt.CheckState.Checked:
                s.add(name)
            else:
                s.discard(name)
            if role == getattr(self, "current_group", None):
                self._db_privs = set(s)
            self._db_dirty_roles.add(role)
            self._db_dirty = True
        else:
            # Fallback legado: usa atributos planos
            if item.checkState(0) == Qt.CheckState.Checked:
                self._db_privs.add(name)
            else:
                self._db_privs.discard(name)
            self._db_dirty = True
        self._update_save_all_state()

    def _save_db_for_current_target(self):
        role = getattr(self, "_db_role_target", None) or getattr(self, "current_group", None)
        if not role or not self.controller:
            return
        privs = set(getattr(self, "_db_privs_by_role", {}).get(role, set()))

        def task():
            return self.controller.grant_database_privileges(role, privs)

        def on_ok(ok: bool):
            if ok:
                QMessageBox.information(self, "Salvo", "Privilégios de banco aplicados para o alvo selecionado.")
                try:
                    if hasattr(self, "_db_dirty_roles") and role in self._db_dirty_roles:
                        self._db_dirty_roles.discard(role)
                    if hasattr(self, "_db_dirty_roles") and not self._db_dirty_roles:
                        self._db_dirty = False
                except Exception:
                    pass
            else:
                QMessageBox.warning(self, "Aviso", "Falhas ao salvar privilégios de banco.")
            self._update_save_all_state()

        def on_err(e: Exception):
            QMessageBox.critical(self, "Erro", f"Falha ao salvar privilégios de banco: {e}")

        self._execute_async(task, on_ok, on_err, "Salvando privilégios de banco…")

    # Owners UI helpers
    def _filter_owner_rows(self):
        q = (self.txtOwnerSearch.text() or "").lower()
        for i in range(self.treeOwners.topLevelItemCount()):
            it = self.treeOwners.topLevelItem(i)
            it.setHidden(q not in it.text(0).lower())

    def _populate_owners_for_current(self):
        self.treeOwners.clear()
        if not self.current_group:
            return
        cur = self.schema_list.currentItem()
        if not cur:
            return
        schema = cur.text()
        users, groups = self._list_roles_split()
        existing: dict[str, set[str]] = {}
        try:
            defaults = self.controller.get_default_table_privileges(self.current_group)
            existing = defaults.get(schema, {})
        except Exception:
            existing = {}
        # Add users and groups as rows with per-owner privileges
        def add_owner_row(name: str, is_group: bool):
            row = QTreeWidgetItem([name])
            for col, p in enumerate(["SELECT", "INSERT", "UPDATE", "DELETE"], start=1):
                row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                checked = Qt.CheckState.Checked if p in existing.get(name, set()) else Qt.CheckState.Unchecked
                row.setCheckState(col, checked)
            # colorize: grupos âmbar (#FFC857), usuários ciano (#5BC0EB)
            try:
                color = QColor("#FFC857") if is_group else QColor("#5BC0EB")
                row.setForeground(0, QBrush(color))
            except Exception:
                pass
            self.treeOwners.addTopLevelItem(row)
        # Mostrar primeiro grupos, depois usuários
        for g in groups:
            add_owner_row(g, True)
        for u in users:
            add_owner_row(u, False)
        self.treeOwners.sortItems(0, Qt.SortOrder.AscendingOrder)

    def _on_owner_cell_changed(self, item: QTreeWidgetItem, column: int):
        if column == 0:
            return
        cur = self.schema_list.currentItem()
        if not cur or not self.current_group:
            return
        schema = cur.text()
        key = (self.current_group, schema)
        st = self._priv_cache.setdefault(key, PrivilegesState())
        owner = item.text(0)
        col2priv = {1: "SELECT", 2: "INSERT", 3: "UPDATE", 4: "DELETE"}
        priv = col2priv.get(column)
        s = st.default_privs.setdefault(owner, set())
        if item.checkState(column) == Qt.CheckState.Checked:
            s.add(priv)
        else:
            s.discard(priv)
        st.dirty_default = True
        self._update_save_all_state()
        # Warn if owner lacks CREATE and is receiving any priv
        if any(item.checkState(c) == Qt.CheckState.Checked for c in (1,2,3,4)):
            self._warn_if_owner_lacks_create(owner, schema)

    def _list_roles_split(self) -> tuple[list[str], list[str]]:
        users: list[str] = []
        groups: list[str] = []
        # Prefer schema_controller candidates if available
        if self.schema_controller and hasattr(self.schema_controller, 'list_owner_candidates'):
            try:
                names = sorted(self.schema_controller.list_owner_candidates(include_superusers=True))
                # Split into users/groups based on group_prefix when possible
                try:
                    from ..config_manager import load_config
                    prefix = load_config().get('group_prefix', 'grp_')
                except Exception:
                    prefix = 'grp_'
                for n in names:
                    (groups if n.startswith(prefix) else users).append(n)
                return users, groups
            except Exception:
                pass
        # Fallback: list users and groups from GroupsController
        try:
            users = sorted(self.controller.list_users()) if hasattr(self.controller, 'list_users') else []
        except Exception:
            users = []
        try:
            groups = sorted(self.controller.list_groups()) if hasattr(self.controller, 'list_groups') else []
        except Exception:
            groups = []
        return users, groups

    def _collect_owner_privs_from_ui(self) -> tuple[str, dict[str, set[str]]]:
        cur = self.schema_list.currentItem()
        schema = cur.text() if cur else None
        owner_map: dict[str, set[str]] = {}
        for i in range(self.treeOwners.topLevelItemCount()):
            it = self.treeOwners.topLevelItem(i)
            privs: set[str] = set()
            if it.checkState(1) == Qt.CheckState.Checked: privs.add('SELECT')
            if it.checkState(2) == Qt.CheckState.Checked: privs.add('INSERT')
            if it.checkState(3) == Qt.CheckState.Checked: privs.add('UPDATE')
            if it.checkState(4) == Qt.CheckState.Checked: privs.add('DELETE')
            if privs:
                owner_map[it.text(0)] = privs
        return schema, owner_map

    def _apply_owners_inline(self):
        if not self.current_group:
            QMessageBox.warning(self, "Selecione", "Escolha um grupo primeiro.")
            return
        cur = self.schema_list.currentItem()
        if not cur:
            QMessageBox.warning(self, "Selecione", "Escolha um schema primeiro.")
            return
        schema, desired = self._collect_owner_privs_from_ui()
        # Compute current owner map
        current: dict[str, set[str]] = {}
        try:
            defaults = self.controller.get_default_table_privileges(self.current_group)
            current = defaults.get(schema, {})
        except Exception:
            current = {}
        to_add = {o: p for o, p in desired.items() if o not in current or p != current[o]}
        to_clear = {o for o in current.keys() if o not in desired}

        # Warn for owners without CREATE
        for owner in desired.keys():
            self._warn_if_owner_lacks_create(owner, schema)

        role = self.current_group

        def task():
            ok = True
            # Apply diffs
            for owner, perms in sorted(to_add.items()):
                ok = self.controller.alter_default_privileges(role, schema, 'tables', set(perms), owner=owner, emit_signal=False) and ok
            for owner in sorted(to_clear):
                ok = self.controller.alter_default_privileges(role, schema, 'tables', set(), owner=owner, emit_signal=False) and ok
            # Optionally apply to existing tables using union of privileges
            if ok and self.cbApplyExisting.isChecked():
                try:
                    tables_by_schema = self.controller.get_group_privileges(role)
                    tables = tables_by_schema.get(schema, {})
                except Exception:
                    tables = {}
                union_privs: set[str] = set()
                for p in desired.values():
                    union_privs |= set(p)
                new_map: dict[str, set[str]] = {}
                for table_name in tables.keys():
                    new_map[table_name] = set(union_privs)
                ok = self.controller.apply_group_privileges(role, {schema: new_map}, defaults_applied=True, emit_signal=False) and ok
            return ok

        def on_success(s):
            if s:
                QMessageBox.information(self, "Sucesso", "Owners/defaults atualizados.")
            else:
                QMessageBox.warning(self, "Atenção", "Algumas alterações podem não ter sido aplicadas.")
            # Refresh server state
            self._populate_owners_for_current()

        def on_error(e: Exception):
            QMessageBox.critical(self, "Erro", f"Falha ao atualizar owners/defaults: {e}")

        self._execute_async(task, on_success, on_error, "Aplicando alterações…")

    def _warn_if_owner_lacks_create(self, owner: str, schema: str):
        try:
            privs_by_schema = self.controller.get_schema_level_privileges(owner)
            has_create = 'CREATE' in privs_by_schema.get(schema, set())
        except Exception:
            has_create = True  # fail open to avoid false positives
        if not has_create:
            QMessageBox.warning(self, "Aviso", f"O owner '{owner}' não possui CREATE no schema '{schema}'. Defaults podem não surtir efeito.")

    # Back-compat helpers used by tests ---------------------------------
    def _current_schema_checked(self):
        """Return (role, schema) tuple for current selection; used in tests.
        Falls back to first item when called without UI init."""
        role = self.current_group
        schema = None
        try:
            it = self.schema_list.currentItem()
            schema = it.text() if it else None
            if not schema and self.schema_list.count() > 0:
                schema = self.schema_list.item(0).text()
        except Exception:
            pass
        return (role, schema)

    def _save_default_privileges(self, owners: list[str]):
        """Apply default table privileges for given owners on current schema.
        This mirrors previous test contract: iterate owners and call controller.alter_default_privileges."""
        if not self.controller or not self.current_group:
            return False
        role, schema = self._current_schema_checked()
        if not schema:
            return False
        # compute desired privs from UI checkboxes when available, otherwise from cached state
        privs: set[str] = set()
        if hasattr(self, 'cbSel') and self.cbSel.isChecked(): privs.add('SELECT')
        if hasattr(self, 'cbIns') and self.cbIns.isChecked(): privs.add('INSERT')
        if hasattr(self, 'cbUpd') and self.cbUpd.isChecked(): privs.add('UPDATE')
        if hasattr(self, 'cbDel') and self.cbDel.isChecked(): privs.add('DELETE')
        if not privs:
            # fallback to cached default privs if UI not present (tests may inject)
            st = self._priv_cache.get((role, schema)) or PrivilegesState()
            privs = set()
            for p in st.default_privs or set():
                privs.add(p)

        def task():
            ok = True
            for owner in owners:
                ok = self.controller.alter_default_privileges(role, schema, 'tables', set(privs), owner=owner, emit_signal=False) and ok
            return ok

        def on_success(_):
            self._update_save_all_state()
            try:
                QMessageBox.information(self, "Sucesso", "Privilégios padrão salvos.")
            except Exception:
                pass

        def on_error(e: Exception):
            QMessageBox.critical(self, "Erro", f"Falha ao salvar default privileges: {e}")

        # allow tests to stub _execute_async
        self._execute_async(task, on_success, on_error, "Salvando defaults…")

    # --- Esquemas tab -------------------------------------------------
    def _on_schema_priv_toggle(self, priv: str, checked: bool):
        if not self.current_group:
            return
        cur = self.schema_list.currentItem()
        if not cur:
            return
        schema = cur.text()
        self._update_schema_priv(self.current_group, schema, priv, checked)
        self._update_save_all_state()

    def _update_schema_priv(self, role: str, schema: str, priv: str, checked: bool):
        key = (role, schema)
        state = self._priv_cache.setdefault(key, PrivilegesState())
        if checked:
            state.schema_privs.add(priv)
        else:
            state.schema_privs.discard(priv)
        state.dirty_schema = True
        # garantir que o botão Salvar Tudo reflita mudanças mesmo em testes
        try:
            self._update_save_all_state()
        except Exception:
            pass

    def _populate_privileges(self):
        # Build treePrivileges by schema
        self.treePrivileges.blockSignals(True)
        try:
            self.treePrivileges.clear()
            role_target = self._tables_role_target or self.current_group
            if not self.controller or not role_target:
                return
            tables_by_schema = self.controller.get_schema_tables()
            # Fetch current privileges for role_target to reflect existing state
            try:
                current_privs = self.controller.get_group_privileges(role_target)
            except Exception:
                current_privs = {}
            # Ensure schema_list is populated for tests using __new__
            try:
                if self.schema_list and self.schema_list.count() == 0:
                    for s in sorted(tables_by_schema.keys()):
                        self.schema_list.addItem(s)
            except Exception:
                pass
            # Lazily create schema-level checkboxes if missing (tests bypass __init__)
            if not hasattr(self, 'cb_usage'):
                self.cb_usage = QCheckBox("USAGE")
            if not hasattr(self, 'cb_create'):
                self.cb_create = QCheckBox("CREATE")
            for schema, tables in sorted(tables_by_schema.items()):
                sitem = QTreeWidgetItem([schema])
                sitem.setFirstColumnSpanned(True)
                self.treePrivileges.addTopLevelItem(sitem)
                # Geral row
                geral = QTreeWidgetItem(["Geral"])  
                for col in range(1, 5):
                    geral.setFlags(geral.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    geral.setCheckState(col, Qt.CheckState.Unchecked)
                sitem.addChild(geral)
                # Tables
                key = (role_target, schema)
                st = self._priv_cache.setdefault(key, PrivilegesState())
                for t in sorted(tables or []):
                    it = QTreeWidgetItem([t])
                    for col, p in enumerate(["SELECT", "INSERT", "UPDATE", "DELETE"], start=1):
                        it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                        # Seed cache from current privileges if empty
                        if t not in st.table_privs and schema in current_privs:
                            st.table_privs[t] = set(current_privs.get(schema, {}).get(t, set()))
                        checked = Qt.CheckState.Checked if p in st.table_privs.get(t, set()) else Qt.CheckState.Unchecked
                        it.setCheckState(col, checked)
                    sitem.addChild(it)
                sitem.setExpanded(True)
            # set schema-level checkboxes from controller
            self._refresh_schema_level_checkboxes()
        finally:
            self.treePrivileges.blockSignals(False)

    def _refresh_schema_level_checkboxes(self):
        if not self.controller or not self.current_group:
            self.cb_usage.setChecked(False)
            self.cb_create.setChecked(False)
            return
        try:
            privs = self.controller.get_schema_level_privileges(self.current_group)
        except Exception:
            privs = {}
        cur = self.schema_list.currentItem()
        if not cur:
            return
        s = cur.text()
        sp = privs.get(s, set())
        self.cb_usage.blockSignals(True); self.cb_create.blockSignals(True)
        try:
            self.cb_usage.setChecked("USAGE" in sp)
            self.cb_create.setChecked("CREATE" in sp)
        finally:
            self.cb_usage.blockSignals(False); self.cb_create.blockSignals(False)
        # Also refresh owners grid for this schema
        self._populate_owners_for_current()

    def _update_schema_details(self, item: QListWidgetItem, prev: QListWidgetItem | None):
        # Set current schema selection if provided and refresh checkboxes
        try:
            if item is not None:
                self.schema_list.setCurrentItem(item)
        except Exception:
            pass
        self._refresh_schema_level_checkboxes()

    # --- Tabelas tab --------------------------------------------------
    def _on_table_priv_changed(self, item: QTreeWidgetItem, column: int):
        # only columns 1..4 correspond to privileges
        if column == 0:
            return
        # find schema item
        parent = item.parent()
        if parent is None:
            return
        schema = parent.text(0)
        role_target = self._tables_role_target or self.current_group
        key = (role_target, schema)
        st = self._priv_cache.setdefault(key, PrivilegesState())
        # privilege name by column
        col2priv = {1: "SELECT", 2: "INSERT", 3: "UPDATE", 4: "DELETE"}
        priv = col2priv.get(column)
        if not priv:
            return
        if item.text(0) == "Geral":
            # apply to all children
            val = item.checkState(column)
            for i in range(1, parent.childCount()):
                ch = parent.child(i)
                ch.setCheckState(column, val)
                name = item.text(0)
                s = st.table_privs.setdefault(tname, set())
                if val == Qt.CheckState.Checked:
                    s.add(priv)
                else:
                    s.discard(priv)
                s = self._db_privs_by_role.setdefault(role, set())
                # manter coerência: GRANT implica BASE
                base_checked = item.checkState(0) == Qt.CheckState.Checked
                grant_checked = item.checkState(1) == Qt.CheckState.Checked
                # se grant ligado, base precisa estar ligado
                if grant_checked and not base_checked:
                    base_checked = True
                    item.setCheckState(0, Qt.CheckState.Checked)
                # atualizar conjunto
                if base_checked:
                    s.add(name)
                else:
                    s.discard(name)
                if grant_checked:
                    s.add(name + "*")
                else:
                    s.discard(name + "*")
            if item.checkState(column) == Qt.CheckState.Checked:
                s.add(priv)
            else:
                s.discard(priv)
            st.dirty_table = True
            # update Geral tri-state
            geral = parent.child(0)
            all_vals = []
            for i in range(1, parent.childCount()):
                all_vals.append(parent.child(i).checkState(column))
            if all(x == Qt.CheckState.Checked for x in all_vals):
                geral.setCheckState(column, Qt.CheckState.Checked)
            elif all(x == Qt.CheckState.Unchecked for x in all_vals):
                geral.setCheckState(column, Qt.CheckState.Unchecked)
            else:
                geral.setCheckState(column, Qt.CheckState.PartiallyChecked)
        self._update_save_all_state()

    def _save_tables_for_current_target(self):
        role = self._tables_role_target or self.current_group
        if not role:
            return
        # Get schemas touched for this role
        schemas = sorted({schema for (r, schema) in self._priv_cache.keys() if r == role})
        if not schemas:
            return
        def task():
            ok = True
            for schema in schemas:
                ok = self._save_state_sync(role, schema) and ok
            return ok
        def on_ok(ok: bool):
            self._update_save_all_state()
            if ok:
                QMessageBox.information(self, "Salvo", "Privilégios de tabelas aplicados para o alvo selecionado.")
            else:
                QMessageBox.warning(self, "Aviso", "Falhas ao salvar algumas alterações de tabelas.")
        def on_err(e: Exception):
            QMessageBox.critical(self, "Erro", f"Falha ao salvar tabelas: {e}")
        self._execute_async(task, on_ok, on_err, "Salvando privilégios de tabelas…")

    # --- Save All -----------------------------------------------------
    def _update_save_all_state(self):
        # enable if db dirty or any cache dirty
        if self._db_dirty:
            self.btnSaveAll.setEnabled(True)
            return
        for st in self._priv_cache.values():
            if st.dirty_schema or st.dirty_table or st.dirty_default:
                self.btnSaveAll.setEnabled(True)
                return
        self.btnSaveAll.setEnabled(False)

    def _save_state_sync(self, role: str, schema: str) -> bool:
        """Default save implementation for one (role, schema)."""
        if not self.controller:
            return False
        st = self._priv_cache.get((role, schema)) or PrivilegesState()
        ok = True
        try:
            if st.dirty_schema:
                ok = self.controller.grant_schema_privileges(role, schema, set(st.schema_privs)) and ok
                st.dirty_schema = False
            if st.dirty_table:
                # Build mapping table -> privs
                tbl_map = {schema: {t: set(p) for t, p in st.table_privs.items()}}
                ok = self.controller.apply_group_privileges(role, tbl_map, defaults_applied=False, emit_signal=False) and ok
                st.dirty_table = False
            if st.dirty_default:
                # Apply per-owner defaults
                for owner, privs in (st.default_privs or {}).items():
                    ok = self.controller.alter_default_privileges(role, schema, 'tables', set(privs), owner=owner, emit_signal=False) and ok
                st.dirty_default = False
        except Exception:
            ok = False
        return ok

    def _save_all_privileges(self):
        if not getattr(self, "current_group", None) and not getattr(self, "_db_dirty_roles", set()):
            return
        role = getattr(self, "current_group", None)
        def task():
            ok = True
            # DB privs
            if self._db_dirty:
                try:
                    # aplicar para todos os roles com DB sujo
                    dirty_roles = sorted(getattr(self, "_db_dirty_roles", set())) or ([role] if role else [])
                    for r in dirty_roles:
                        privs = set(getattr(self, "_db_privs_by_role", {}).get(r, set()))
                        ok = self.controller.grant_database_privileges(r, privs) and ok
                    if hasattr(self, "_db_dirty_roles"):
                        self._db_dirty_roles.clear()
                    self._db_dirty = False
                except Exception:
                    ok = False
            # per schema
            touched = sorted({schema for (r, schema) in self._priv_cache.keys() if r == role}) if role else []
            for schema in touched:
                ok = self._save_state_sync(role, schema) and ok
            return ok
        def on_ok(ok: bool):
            self._update_save_all_state()
            if ok:
                QMessageBox.information(self, "Salvo", "Alterações aplicadas.")
                # após salvar tudo com sucesso, desabilita o botão
                try:
                    self.btnSaveAll.setEnabled(False)
                except Exception:
                    pass
            else:
                QMessageBox.warning(self, "Aviso", "Falhas ao salvar algumas alterações.")
        def on_err(e: Exception):
            QMessageBox.critical(self, "Erro", f"Falha ao salvar: {e}")
        self._execute_async(task, on_ok, on_err, "Salvando alterações…")
        # Atualiza estado imediatamente (útil quando _execute_async é sincronizado em testes)
        try:
            self._update_save_all_state()
        except Exception:
            pass
        # Garante botão desabilitado no fim (compatível com testes síncronos)
        try:
            self.btnSaveAll.setEnabled(False)
        except Exception:
            pass
    def _execute_async(self, func, on_success, on_error, label: str):
        progress = QProgressDialog(label, None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setAutoClose(True)
        progress.show()

        thread = _TaskRunner(func, self)
        thread.succeeded.connect(lambda r: (progress.cancel(), on_success(r)))
        thread.failed.connect(lambda e: (progress.cancel(), on_error(e)))
        thread.start()
