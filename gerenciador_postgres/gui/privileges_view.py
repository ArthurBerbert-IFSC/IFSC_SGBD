from PyQt6.QtWidgets import QWidget, QVBoxLayout, QComboBox, QPushButton, QTreeWidget, QTreeWidgetItem, QLabel, QHBoxLayout
from PyQt6.QtGui import QIcon
from pathlib import Path

class PrivilegesView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        assets_dir = Path(__file__).resolve().parents[2] / "assets"
        self.setWindowIcon(QIcon(str(assets_dir / "icone.png")))
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        # Seleção de usuário/grupo
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
        self.treePrivileges.setHeaderLabels(["Schema/Tabela", "SELECT", "INSERT", "UPDATE", "DELETE"])
        layout.addWidget(self.treePrivileges)
        self.btnSave = QPushButton("Salvar Permissões Granulares")
        layout.addWidget(self.btnSave)
        self.setLayout(layout)
