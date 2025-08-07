from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QToolBar,
    QPushButton,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
)
from PyQt6.QtCore import Qt


class GroupsView(QWidget):
    """Interface simples para gestão de turmas (grupos)."""

    def __init__(self, parent=None, controller=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Gestão de Turmas")
        self._setup_ui()
        self._connect_signals()
        if self.controller:
            self.controller.data_changed.connect(self.refresh_groups)
        self.refresh_groups()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.toolbar = QToolBar()
        self.btnNewGroup = QPushButton("Nova Turma")
        self.btnDeleteGroup = QPushButton("Excluir Turma")
        self.btnDeleteGroup.setEnabled(False)
        self.toolbar.addWidget(self.btnNewGroup)
        self.toolbar.addWidget(self.btnDeleteGroup)
        layout.addWidget(self.toolbar)

        lists_layout = QHBoxLayout()
        self.lstGroups = QListWidget()
        self.lstMembers = QListWidget()
        lists_layout.addWidget(self.lstGroups)
        lists_layout.addWidget(self.lstMembers)
        layout.addLayout(lists_layout)

        self.infoLabel = QLabel("Selecione uma turma para ver os alunos.")
        layout.addWidget(self.infoLabel)

        self.setLayout(layout)

    def _connect_signals(self):
        self.lstGroups.currentItemChanged.connect(self.on_group_selected)
        self.btnNewGroup.clicked.connect(self.on_new_group_clicked)
        self.btnDeleteGroup.clicked.connect(self.on_delete_group_clicked)

    def refresh_groups(self):
        self.lstGroups.clear()
        self.lstMembers.clear()
        if not self.controller:
            return
        try:
            _, groups = self.controller.list_entities()
            for group in groups:
                item = QListWidgetItem(group)
                item.setData(Qt.ItemDataRole.UserRole, group)
                self.lstGroups.addItem(item)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível listar turmas: {e}")

    def on_group_selected(self, current, previous):
        self.lstMembers.clear()
        if not current:
            self.infoLabel.setText("Selecione uma turma para ver os alunos.")
            self.btnDeleteGroup.setEnabled(False)
            return
        group_name = current.data(Qt.ItemDataRole.UserRole)
        self.btnDeleteGroup.setEnabled(True)
        try:
            members = self.controller.list_group_members(group_name)
            for m in members:
                self.lstMembers.addItem(m)
            self.infoLabel.setText(f"Alunos na turma '{group_name}':")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível listar alunos: {e}")

    def on_new_group_clicked(self):
        from PyQt6.QtWidgets import QInputDialog

        group_name, ok = QInputDialog.getText(
            self, "Nova Turma", "Nome da turma (prefixo grp_):"
        )
        if not ok or not group_name:
            return
        try:
            self.controller.create_group(group_name)
            QMessageBox.information(
                self, "Sucesso", f"Turma '{group_name}' criada com sucesso!"
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Erro", f"Não foi possível criar a turma.\nMotivo: {e}"
            )

    def on_delete_group_clicked(self):
        current_item = self.lstGroups.currentItem()
        if not current_item:
            return
        group_name = current_item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(
            self,
            "Confirmar",
            f"Excluir turma '{group_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                success = self.controller.delete_group(group_name)
                if success:
                    QMessageBox.information(
                        self, "Sucesso", f"Turma '{group_name}' excluída."
                    )
                else:
                    QMessageBox.critical(
                        self, "Erro", "Falha ao excluir a turma. Verifique os logs."
                    )
            except Exception as e:
                QMessageBox.critical(
                    self, "Erro", f"Não foi possível excluir a turma.\nMotivo: {e}"
                )
