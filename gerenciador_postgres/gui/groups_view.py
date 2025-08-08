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
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from pathlib import Path


class GroupsView(QWidget):
    """Janela para gerenciamento de grupos e seus privilégios."""

    def __init__(self, parent=None, controller=None):
        super().__init__(parent)
        assets_dir = Path(__file__).resolve().parents[2] / "assets"
        self.setWindowIcon(QIcon(str(assets_dir / "icone.png")))
        self.controller = controller
        self.current_group = None
        self.templates = {}
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
        ])
        right_layout.addWidget(self.treePrivileges)
        self.btnSave = QPushButton("Salvar")
        right_layout.addWidget(self.btnSave)
        self.splitter.addWidget(right_panel)

        layout.addWidget(self.splitter)
        self.setLayout(layout)

        # Disable privilege controls until a group is selected
        self.treePrivileges.setEnabled(False)
        self.btnApplyTemplate.setEnabled(False)
        self.btnSave.setEnabled(False)

    def _connect_signals(self):
        self.btnNewGroup.clicked.connect(self._on_new_group)
        self.btnDeleteGroup.clicked.connect(self._on_delete_group)
        self.lstGroups.currentItemChanged.connect(self._on_group_selected)
        self.btnApplyTemplate.clicked.connect(self._apply_template)
        self.btnSave.clicked.connect(self._save_privileges)

    # ------------------------------------------------------------------
    def refresh_groups(self):
        self.lstGroups.clear()
        if not self.controller:
            return
        for grp in self.controller.list_groups():
            self.lstGroups.addItem(QListWidgetItem(grp))
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
            "Nome do grupo (deve começar com 'grp_'):",
            QLineEdit.EchoMode.Normal,
            "grp_",
        )
        if not ok or not name:
            return
        name = name.strip()
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
        reply = QMessageBox.question(
            self,
            "Confirmar Deleção",
            f"Tem certeza que deseja excluir o grupo '{group}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self.controller.delete_group(group):
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
            return
        self.current_group = current.text()
        self.treePrivileges.setEnabled(True)
        self.btnApplyTemplate.setEnabled(True)
        self.btnSave.setEnabled(True)
        self._populate_tree()

    def _populate_tree(self):
        if not self.controller or not self.current_group:
            return
        data = self.controller.get_schema_tables()
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
                for col in range(1, 5):
                    table_item.setCheckState(col, Qt.CheckState.Unchecked)
                schema_item.addChild(table_item)
        self.treePrivileges.expandAll()

    def _apply_template(self):
        if not self.current_group:
            return
        template_name = self.cmbTemplates.currentText()
        try:
            success = self.controller.apply_template_to_group(
                self.current_group, template_name
            )
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
        except Exception as e:
            QMessageBox.critical(
                self, "Erro", f"Não foi possível aplicar o template: {e}"
            )

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
        if self.controller.apply_group_privileges(self.current_group, privileges):
            QMessageBox.information(self, "Sucesso", "Privilégios atualizados.")
        else:
            QMessageBox.critical(
                self, "Erro", "Falha ao salvar os privilégios do grupo."
            )
