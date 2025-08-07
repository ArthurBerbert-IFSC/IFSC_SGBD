from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QComboBox,
    QPushButton,
    QLabel,
    QHBoxLayout,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from pathlib import Path


class GroupsView(QWidget):
    """Interface para edição de privilégios de grupos."""

    def __init__(self, parent=None, controller=None, group_name: str = ""):
        super().__init__(parent)
        assets_dir = Path(__file__).resolve().parents[2] / "assets"
        self.setWindowIcon(QIcon(str(assets_dir / "icone.png")))
        self.controller = controller
        self.group_name = group_name
        self.templates = {}
        self._setup_ui()
        self._load_templates()
        self._populate_tree()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Template:"))
        self.cmbTemplates = QComboBox()
        self.btnApplyTemplate = QPushButton("Aplicar")
        top.addWidget(self.cmbTemplates)
        top.addWidget(self.btnApplyTemplate)
        layout.addLayout(top)

        self.treePrivileges = QTreeWidget()
        self.treePrivileges.setHeaderLabels(
            ["Schema/Tabela", "SELECT", "INSERT", "UPDATE", "DELETE"]
        )
        layout.addWidget(self.treePrivileges)

        self.btnSave = QPushButton("Salvar")
        layout.addWidget(self.btnSave)
        self.setLayout(layout)

        self.btnApplyTemplate.clicked.connect(self._apply_template)
        self.btnSave.clicked.connect(self._save_privileges)

    def _load_templates(self):
        if not self.controller:
            return
        self.templates = self.controller.list_privilege_templates()
        self.cmbTemplates.addItems(self.templates.keys())

    def _populate_tree(self):
        if not self.controller:
            return
        data = self.controller.get_schema_tables()
        self.treePrivileges.clear()
        for schema, tables in data.items():
            schema_item = QTreeWidgetItem([schema])
            schema_item.setFlags(schema_item.flags() | Qt.ItemFlag.Tristate)
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
        name = self.cmbTemplates.currentText()
        perms = self.templates.get(name, set())
        for i in range(self.treePrivileges.topLevelItemCount()):
            schema_item = self.treePrivileges.topLevelItem(i)
            for j in range(schema_item.childCount()):
                table_item = schema_item.child(j)
                for col, label in enumerate(["SELECT", "INSERT", "UPDATE", "DELETE"], start=1):
                    state = Qt.CheckState.Checked if label in perms else Qt.CheckState.Unchecked
                    table_item.setCheckState(col, state)

    def _save_privileges(self):
        if not self.controller or not self.group_name:
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
        self.controller.apply_group_privileges(self.group_name, privileges)
