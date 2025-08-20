from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QToolBar,
    QPushButton,
    QListWidget,
    QGroupBox,
    QHBoxLayout,
    QCheckBox,
    QLabel,
    QMessageBox,
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt
from pathlib import Path


class SchemaPrivilegesView(QWidget):
    """Tela unificada para gerenciamento de schemas e privilégios padrão."""

    def __init__(
        self,
        parent=None,
        schema_controller=None,
        privileges_controller=None,
        role: str | None = None,
        logger=None,
    ):
        super().__init__(parent)
        assets_dir = Path(__file__).resolve().parents[2] / "assets"
        self.setWindowIcon(QIcon(str(assets_dir / "icone.png")))
        self.schema_controller = schema_controller
        self.priv_controller = privileges_controller
        self.role = role or "public"
        self.logger = logger
        self.setWindowTitle("Schemas e Privilégios")
        self._setup_ui()
        self._connect_signals()
        if self.schema_controller:
            self.schema_controller.data_changed.connect(self.refresh_list)
        if self.priv_controller:
            self.priv_controller.data_changed.connect(self._load_privileges)
        self.refresh_list()

    # ------------------------------------------------------------------
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        # toolbar de schemas
        self.toolbar = QToolBar()
        self.btnNew = QPushButton("Novo Schema")
        self.btnDelete = QPushButton("Excluir")
        self.btnOwner = QPushButton("Alterar Owner")
        self.btnSavePriv = QPushButton("Salvar Privilégios")
        self.btnDelete.setEnabled(False)
        self.btnOwner.setEnabled(False)
        self.btnSavePriv.setEnabled(False)
        self.toolbar.addWidget(self.btnNew)
        self.toolbar.addWidget(self.btnDelete)
        self.toolbar.addWidget(self.btnOwner)
        self.toolbar.addWidget(self.btnSavePriv)
        layout.addWidget(self.toolbar)

        self.lstSchemas = QListWidget()
        layout.addWidget(self.lstSchemas)

        # grupo de privilégios
        self.grpPrivs = QGroupBox("Privilégios de Schema e Padrões")
        priv_layout = QVBoxLayout()
        row1 = QHBoxLayout()
        self.cb_usage = QCheckBox("USAGE")
        self.cb_create = QCheckBox("CREATE")
        row1.addWidget(self.cb_usage)
        row1.addWidget(self.cb_create)
        priv_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Padrão para Novas Tabelas:"))
        self.cb_select = QCheckBox("SELECT")
        self.cb_insert = QCheckBox("INSERT")
        self.cb_update = QCheckBox("UPDATE")
        self.cb_delete = QCheckBox("DELETE")
        for cb in [self.cb_select, self.cb_insert, self.cb_update, self.cb_delete]:
            row2.addWidget(cb)
        priv_layout.addLayout(row2)

        self.grpPrivs.setLayout(priv_layout)
        self.grpPrivs.setEnabled(False)
        layout.addWidget(self.grpPrivs)
        self.setLayout(layout)

    # ------------------------------------------------------------------
    def _connect_signals(self):
        self.btnNew.clicked.connect(self.on_new_schema)
        self.btnDelete.clicked.connect(self.on_delete_schema)
        self.btnOwner.clicked.connect(self.on_change_owner)
        self.btnSavePriv.clicked.connect(self.on_save_privileges)
        self.lstSchemas.currentItemChanged.connect(self.on_schema_selected)

    # ------------------------------------------------------------------
    def refresh_list(self):
        self.lstSchemas.clear()
        if not self.schema_controller:
            return
        try:
            for schema in self.schema_controller.list_schemas():
                self.lstSchemas.addItem(schema)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao listar schemas:\n{e}")
            if self.logger:
                self.logger.error(f"Falha ao listar schemas: {e}")

    # ------------------------------------------------------------------
    def on_schema_selected(self, current, previous):
        has_item = current is not None
        self.btnDelete.setEnabled(has_item)
        self.btnOwner.setEnabled(has_item)
        self.btnSavePriv.setEnabled(has_item and self.priv_controller is not None)
        self.grpPrivs.setEnabled(has_item and self.priv_controller is not None)
        if has_item:
            self._load_privileges()

    # ------------------------------------------------------------------
    def _load_privileges(self):
        item = self.lstSchemas.currentItem()
        if not item or not self.priv_controller:
            return
        schema = item.text()
        try:
            schema_privs = self.priv_controller.get_schema_level_privileges(self.role).get(schema, set())
            default_info = self.priv_controller.get_default_table_privileges(self.role).get(schema, {})
            defaults = default_info.get("privileges", set())
        except Exception as e:
            if self.logger:
                self.logger.error(f"Falha ao obter privilégios: {e}")
            schema_privs = set()
            defaults = set()
        self.cb_usage.setChecked("USAGE" in schema_privs)
        self.cb_create.setChecked("CREATE" in schema_privs)
        self.cb_select.setChecked("SELECT" in defaults)
        self.cb_insert.setChecked("INSERT" in defaults)
        self.cb_update.setChecked("UPDATE" in defaults)
        self.cb_delete.setChecked("DELETE" in defaults)

    # ------------------------------------------------------------------
    def on_new_schema(self):
        from PyQt6.QtWidgets import QInputDialog

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
                if self.logger:
                    self.logger.error(f"Falha ao listar candidatos a owner: {e}")
        from PyQt6.QtWidgets import QInputDialog

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
            self.schema_controller.create_schema(name, owner or None)
            QMessageBox.information(self, "Sucesso", f"Schema '{name}' criado.")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível criar o schema:\n{e}")
            if self.logger:
                self.logger.error(f"Falha ao criar schema '{name}': {e}")

    # ------------------------------------------------------------------
    def on_delete_schema(self):
        from PyQt6.QtWidgets import QMessageBox

        item = self.lstSchemas.currentItem()
        if not item:
            return
        name = item.text()
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
            self.schema_controller.delete_schema(name)
            QMessageBox.information(self, "Sucesso", f"Schema '{name}' removido.")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível remover o schema:\n{e}")
            if self.logger:
                self.logger.error(f"Falha ao remover schema '{name}': {e}")

    # ------------------------------------------------------------------
    def on_change_owner(self):
        from PyQt6.QtWidgets import QInputDialog

        item = self.lstSchemas.currentItem()
        if not item:
            return
        name = item.text()
        roles = []
        supers = set()
        if self.schema_controller:
            try:
                roles = self.schema_controller.list_owner_candidates(include_superusers=True)
                supers = set(self.schema_controller.list_superusers())
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Falha ao listar candidatos a owner: {e}")
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
            self.schema_controller.change_owner(name, new_owner)
            QMessageBox.information(self, "Sucesso", f"Owner de '{name}' alterado.")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível alterar owner:\n{e}")
            if self.logger:
                self.logger.error(f"Falha ao alterar owner de '{name}': {e}")

    # ------------------------------------------------------------------
    def on_save_privileges(self):
        item = self.lstSchemas.currentItem()
        if not item or not self.priv_controller:
            return
        schema = item.text()
        schema_privs = set()
        if self.cb_usage.isChecked():
            schema_privs.add("USAGE")
        if self.cb_create.isChecked():
            schema_privs.add("CREATE")
        defaults = set()
        for label, cb in [
            ("SELECT", self.cb_select),
            ("INSERT", self.cb_insert),
            ("UPDATE", self.cb_update),
            ("DELETE", self.cb_delete),
        ]:
            if cb.isChecked():
                defaults.add(label)
        try:
            ok = True
            if schema_privs:
                ok &= self.priv_controller.grant_schema_privileges(self.role, schema, schema_privs)
            else:
                ok &= self.priv_controller.grant_schema_privileges(self.role, schema, set())
            ok &= self.priv_controller.alter_default_privileges(
                self.role, schema, "tables", defaults
            )
            if ok:
                QMessageBox.information(self, "Sucesso", "Privilégios salvos com sucesso.")
            else:
                QMessageBox.critical(self, "Erro", "Falha ao salvar os privilégios.")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível salvar os privilégios:\n{e}")
            if self.logger:
                self.logger.error(f"Falha ao salvar privilégios do schema '{schema}': {e}")
