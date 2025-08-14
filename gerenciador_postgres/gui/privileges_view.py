from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QComboBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QLabel,
    QHBoxLayout,
    QMessageBox,
    QGroupBox,
    QCheckBox,
    QProgressDialog,
    QApplication)

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from pathlib import Path
from config.permission_templates import PERMISSION_TEMPLATES


class PrivilegesView(QWidget):
    """Tela para gerenciamento de privilégios de usuários/grupos."""

    def __init__(self, parent=None, controller=None):
        super().__init__(parent)
        assets_dir = Path(__file__).resolve().parents[2] / "assets"
        self.setWindowIcon(QIcon(str(assets_dir / "icone.png")))

        self.controller = controller
        self.templates = PERMISSION_TEMPLATES
        self.schema_checkboxes: dict[str, dict] = {}

        self._setup_ui()
        self._connect_signals()
        self._load_roles()
        self._load_templates()
        self._populate_tree()

        if self.controller:
            self.controller.data_changed.connect(self._populate_tree)

    # ------------------------------------------------------------------
    # Configuração de interface
    # ------------------------------------------------------------------
    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Seleção de usuário/grupo + template
        topLayout = QHBoxLayout()
        self.cmbRole = QComboBox()
        self.cmbTemplates = QComboBox()
        self.btnApplyTemplate = QPushButton("Aplicar")

        topLayout.addWidget(QLabel("Usuário/Grupo:"))
        topLayout.addWidget(self.cmbRole)
        topLayout.addWidget(QLabel("Template:"))
        topLayout.addWidget(self.cmbTemplates)
        topLayout.addWidget(self.btnApplyTemplate)

        layout.addLayout(topLayout)

        # Privilégios de banco
        self.treeDbPrivileges = QTreeWidget()
        self.treeDbPrivileges.setHeaderLabels(["Banco", "CONNECT", "CREATE", "TEMP"])
        layout.addWidget(self.treeDbPrivileges)

        # Privilégios de schema e padrões futuros
        self.schemaGroup = QGroupBox("Privilégios de Schema e Padrões")
        self.schemaLayout = QVBoxLayout()
        self.schemaGroup.setLayout(self.schemaLayout)
        layout.addWidget(self.schemaGroup)

        # Privilégios de tabela
        self.treeTablePrivileges = QTreeWidget()
        self.treeTablePrivileges.setHeaderLabels(
            ["Schema/Tabela", "SELECT", "INSERT", "UPDATE", "DELETE"]
        )
        layout.addWidget(self.treeTablePrivileges)

        self.btnSave = QPushButton("Salvar Permissões")
        layout.addWidget(self.btnSave)

        self.setLayout(layout)

    def _connect_signals(self):
        self.btnApplyTemplate.clicked.connect(self._apply_template)
        self.btnSave.clicked.connect(self._save_privileges)
        self.cmbRole.currentIndexChanged.connect(self._populate_tree)

    # ------------------------------------------------------------------
    # Carregamento de dados
    # ------------------------------------------------------------------
    def _load_roles(self):
        """Carrega usuários e grupos para o combo."""
        if not self.controller:
            return
        try:
            users, groups = self.controller.list_entities()
            self.cmbRole.clear()
            for user in users:
                self.cmbRole.addItem(user)
            for group in groups:
                self.cmbRole.addItem(group)
        except Exception as e:
            QMessageBox.critical(
                self, "Erro", f"Falha ao carregar usuários/grupos: {e}"
            )

    def _load_templates(self):
        self.cmbTemplates.clear()
        self.cmbTemplates.addItems(sorted(self.templates.keys()))

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            elif item.layout() is not None:
                self._clear_layout(item.layout())

    def _populate_tree(self):
        """Lista schemas e tabelas disponíveis para atribuição de privilégios."""
        if not self.controller:
            return

        role = self.cmbRole.currentText()
        data = self.controller.get_schema_tables()
        schema_privs = self.controller.get_schema_level_privileges(role)
        default_privs = self.controller.get_default_table_privileges(role)

        # Banco
        self.treeDbPrivileges.clear()
        db_name = (
            self.controller.get_current_database()
            if hasattr(self.controller, "get_current_database")
            else "database"
        )
        db_item = QTreeWidgetItem([db_name, "", "", ""])
        db_item.setFlags(db_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        for col in range(1, 4):
            db_item.setCheckState(col, Qt.CheckState.Unchecked)
        self.treeDbPrivileges.addTopLevelItem(db_item)

        # Schemas - caixas de seleção
        self._clear_layout(self.schemaLayout)
        self.schema_checkboxes.clear()
        for schema in data.keys():
            box = QGroupBox(schema)
            box_layout = QVBoxLayout()

            row1 = QHBoxLayout()
            cb_usage = QCheckBox("USAGE")
            cb_usage.setChecked("USAGE" in schema_privs.get(schema, set()))
            row1.addWidget(cb_usage)
            cb_create = QCheckBox("CREATE")
            cb_create.setChecked("CREATE" in schema_privs.get(schema, set()))
            row1.addWidget(cb_create)
            box_layout.addLayout(row1)

            row2 = QHBoxLayout()
            row2.addWidget(QLabel("Padrão para Novas Tabelas:"))
            cb_select = QCheckBox("SELECT")
            cb_select.setChecked("SELECT" in default_privs.get(schema, set()))
            row2.addWidget(cb_select)
            cb_insert = QCheckBox("INSERT")
            cb_insert.setChecked("INSERT" in default_privs.get(schema, set()))
            row2.addWidget(cb_insert)
            cb_update = QCheckBox("UPDATE")
            cb_update.setChecked("UPDATE" in default_privs.get(schema, set()))
            row2.addWidget(cb_update)
            cb_delete = QCheckBox("DELETE")
            cb_delete.setChecked("DELETE" in default_privs.get(schema, set()))
            row2.addWidget(cb_delete)
            box_layout.addLayout(row2)

            box.setLayout(box_layout)
            self.schemaLayout.addWidget(box)
            self.schema_checkboxes[schema] = {
                "USAGE": cb_usage,
                "CREATE": cb_create,
                "DEFAULT": {
                    "SELECT": cb_select,
                    "INSERT": cb_insert,
                    "UPDATE": cb_update,
                    "DELETE": cb_delete,
                },
            }

        self.schemaLayout.addStretch()

        # Tabelas existentes
        self.treeTablePrivileges.clear()
        for schema, tables in data.items():
            schema_tables_item = QTreeWidgetItem([schema])
            self.treeTablePrivileges.addTopLevelItem(schema_tables_item)
            for table in tables:
                table_item = QTreeWidgetItem([table, "", "", "", ""])
                table_item.setFlags(
                    table_item.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsSelectable
                )
                for col in range(1, 5):
                    table_item.setCheckState(col, Qt.CheckState.Unchecked)
                schema_tables_item.addChild(table_item)

        self.treeDbPrivileges.expandAll()
        self.treeTablePrivileges.expandAll()

    # ------------------------------------------------------------------
    # Ações
    # ------------------------------------------------------------------
    def _apply_template(self):
        """Aplica um template de permissões ao papel selecionado."""
        if not self.controller:
            return
        role = self.cmbRole.currentText()
        template = self.cmbTemplates.currentText()
        tpl = self.templates.get(template, {})
        try:
            success = self.controller.apply_template_to_group(role, template)
            if success:
                self._populate_tree()

                db_item = self.treeDbPrivileges.topLevelItem(0)
                dbname = (
                    self.controller.get_current_database()
                    if hasattr(self.controller, "get_current_database")
                    else "database"
                )
                db_perms = tpl.get("database", {}).get(
                    dbname, tpl.get("database", {}).get("*", [])
                )
                for col, label in enumerate(["CONNECT", "CREATE", "TEMP"], start=1):
                    state = (
                        Qt.CheckState.Checked
                        if label in db_perms
                        else Qt.CheckState.Unchecked
                    )
                    db_item.setCheckState(col, state)

                schema_tpl = tpl.get("schemas", {})
                future_tpl = tpl.get("future", {})
                for schema, boxes in self.schema_checkboxes.items():
                    perms = schema_tpl.get(schema, [])
                    boxes["USAGE"].setChecked("USAGE" in perms)
                    boxes["CREATE"].setChecked("CREATE" in perms)
                    future_perms = future_tpl.get(schema, {}).get("tables", [])
                    for label, cb in boxes["DEFAULT"].items():
                        cb.setChecked(label in future_perms)

                tables_tpl = tpl.get("tables", {})
                for i in range(self.treeTablePrivileges.topLevelItemCount()):
                    schema_item = self.treeTablePrivileges.topLevelItem(i)
                    schema = schema_item.text(0)
                    for j in range(schema_item.childCount()):
                        table_item = schema_item.child(j)
                        table_name = table_item.text(0)
                        if schema in tables_tpl:
                            schema_def = tables_tpl[schema]
                        elif "*" in tables_tpl:
                            schema_def = tables_tpl["*"]
                        else:
                            schema_def = []
                        if isinstance(schema_def, dict):
                            perms = schema_def.get(table_name, [])
                        else:
                            perms = schema_def
                        for col, label in enumerate(
                            ["SELECT", "INSERT", "UPDATE", "DELETE"], start=1
                        ):
                            state = (
                                Qt.CheckState.Checked
                                if label in perms
                                else Qt.CheckState.Unchecked
                            )
                            table_item.setCheckState(col, state)

                QMessageBox.information(
                    self, "Sucesso", "Template aplicado com sucesso."
                )
            else:
                QMessageBox.critical(
                    self, "Erro", "Falha ao aplicar template de permissões."
                )
        except Exception as e:
            QMessageBox.critical(
                self, "Erro", f"Não foi possível aplicar o template: {e}"
            )

    def _save_privileges(self):
        """Salva privilégios configurados manualmente."""
        if not self.controller:
            return
        role = self.cmbRole.currentText()

        progress = QProgressDialog(
            "Salvando permissões...", None, 0, 0, self
        )
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setCancelButton(None)
        progress.show()
        QApplication.processEvents()

        db_privs = set()
        db_item = self.treeDbPrivileges.topLevelItem(0)
        if db_item:
            for col, label in enumerate(["CONNECT", "CREATE", "TEMP"], start=1):
                if db_item.checkState(col) == Qt.CheckState.Checked:
                    db_privs.add(label)

        schema_privs: dict[str, set[str]] = {}
        default_privs: dict[str, set[str]] = {}
        for schema, boxes in self.schema_checkboxes.items():
            perms = set()
            if boxes["USAGE"].isChecked():
                perms.add("USAGE")
            if boxes["CREATE"].isChecked():
                perms.add("CREATE")
            if perms:
                schema_privs[schema] = perms

            dperms = {label for label, cb in boxes["DEFAULT"].items() if cb.isChecked()}
            default_privs[schema] = dperms

        table_privileges: dict[str, dict[str, set[str]]] = {}
        for i in range(self.treeTablePrivileges.topLevelItemCount()):
            schema_item = self.treeTablePrivileges.topLevelItem(i)
            schema = schema_item.text(0)
            for j in range(schema_item.childCount()):
                table_item = schema_item.child(j)
                table = table_item.text(0)
                perms = set()
                for col, label in enumerate(
                    ["SELECT", "INSERT", "UPDATE", "DELETE"], start=1
                ):
                    if table_item.checkState(col) == Qt.CheckState.Checked:
                        perms.add(label)
                if perms:
                    table_privileges.setdefault(schema, {})[table] = perms

        try:
            ok = True
            if db_privs:
                ok &= self.controller.grant_database_privileges(role, db_privs)
            for schema, perms in schema_privs.items():
                ok &= self.controller.grant_schema_privileges(role, schema, perms)
            for schema, perms in default_privs.items():
                ok &= self.controller.alter_default_privileges(
                    role, schema, "tables", perms
                )
            ok &= self.controller.apply_group_privileges(role, table_privileges)
            if ok:
                QMessageBox.information(
                    self, "Sucesso", "Permissões salvas com sucesso."
                )
                self._populate_tree()
            else:
                QMessageBox.critical(
                    self, "Erro", "Falha ao salvar as permissões."
                )
        except Exception as e:
            QMessageBox.critical(
                self, "Erro", f"Não foi possível salvar as permissões: {e}"
            )
        finally:
            progress.close()

