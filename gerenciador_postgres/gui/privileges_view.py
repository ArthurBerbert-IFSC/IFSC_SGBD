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
)
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

        # Permissões granulares
        self.treePrivileges = QTreeWidget()
        self.treePrivileges.setHeaderLabels(
            ["Schema/Tabela", "SELECT", "INSERT", "UPDATE", "DELETE"]
        )
        layout.addWidget(self.treePrivileges)

        self.btnSave = QPushButton("Salvar Permissões Granulares")
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

    def _populate_tree(self):
        """Lista schemas e tabelas disponíveis para atribuição de privilégios."""
        if not self.controller:
            return
        data = self.controller.get_schema_tables()
        self.treePrivileges.clear()
        for schema, tables in data.items():
            schema_item = QTreeWidgetItem([schema])
            self.treePrivileges.addTopLevelItem(schema_item)
            for table in tables:
                table_item = QTreeWidgetItem([table, "", "", "", ""])
                table_item.setFlags(
                    table_item.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsSelectable
                )
                for col in range(1, 5):
                    table_item.setCheckState(col, Qt.CheckState.Unchecked)
                schema_item.addChild(table_item)
        self.treePrivileges.expandAll()

    # ------------------------------------------------------------------
    # Ações
    # ------------------------------------------------------------------
    def _apply_template(self):
        """Aplica um template de permissões ao papel selecionado."""
        if not self.controller:
            return
        role = self.cmbRole.currentText()
        template = self.cmbTemplates.currentText()
        perms = self.templates.get(template, set())
        try:
            success = self.controller.apply_template_to_group(role, template)
            if success:
                # Atualiza árvore para refletir o template
                self._populate_tree()
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
        privileges: dict[str, dict[str, set[str]]] = {}
        for i in range(self.treePrivileges.topLevelItemCount()):
            schema_item = self.treePrivileges.topLevelItem(i)
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
                    privileges.setdefault(schema, {})[table] = perms
        try:
            success = self.controller.apply_group_privileges(role, privileges)
            if success:
                QMessageBox.information(
                    self, "Sucesso", "Permissões salvas com sucesso."
                )
            else:
                QMessageBox.critical(
                    self, "Erro", "Falha ao salvar as permissões."
                )
        except Exception as e:
            QMessageBox.critical(
                self, "Erro", f"Não foi possível salvar as permissões: {e}"
            )

