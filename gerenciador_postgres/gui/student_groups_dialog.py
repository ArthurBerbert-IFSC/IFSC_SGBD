from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QPushButton,
    QLabel,
    QMessageBox,
    QComboBox,
)


class StudentGroupsDialog(QDialog):
    def __init__(self, parent=None, controller=None, username: str = ""):
        super().__init__(parent)
        self.controller = controller
        self.username = username
        self.setWindowTitle("Gerir Turmas")
        self._setup_ui()
        self._connect_signals()
        self.refresh_students()
        if username:
            idx = self.cmbStudents.findText(username)
            if idx >= 0:
                self.cmbStudents.setCurrentIndex(idx)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        student_layout = QHBoxLayout()
        student_layout.addWidget(QLabel("Aluno"))
        self.cmbStudents = QComboBox()
        student_layout.addWidget(self.cmbStudents)
        layout.addLayout(student_layout)

        lists_layout = QHBoxLayout()

        # Student groups
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Turmas do Aluno"))
        self.lstStudentGroups = QListWidget()
        left_layout.addWidget(self.lstStudentGroups)
        lists_layout.addLayout(left_layout)

        # Buttons between lists
        middle_layout = QVBoxLayout()
        self.btnAdd = QPushButton("Adicionar >>")
        self.btnRemove = QPushButton("<< Remover")
        self.btnTransfer = QPushButton("Transferir")
        middle_layout.addStretch()
        middle_layout.addWidget(self.btnAdd)
        middle_layout.addWidget(self.btnRemove)
        middle_layout.addWidget(self.btnTransfer)
        middle_layout.addStretch()
        lists_layout.addLayout(middle_layout)

        # Available groups
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("Turmas Disponíveis"))
        self.lstAvailableGroups = QListWidget()
        right_layout.addWidget(self.lstAvailableGroups)
        lists_layout.addLayout(right_layout)

        layout.addLayout(lists_layout)
        self.setLayout(layout)

    def _connect_signals(self):
        self.btnAdd.clicked.connect(self._on_add_clicked)
        self.btnRemove.clicked.connect(self._on_remove_clicked)
        self.btnTransfer.clicked.connect(self._on_transfer_clicked)
        self.cmbStudents.currentTextChanged.connect(self.refresh_lists)

    def refresh_students(self):
        if not self.controller:
            return
        self.cmbStudents.clear()
        for user in sorted(self.controller.list_users()):
            self.cmbStudents.addItem(user)
        self.refresh_lists()

    # ------------------------------------------------------------------
    def refresh_lists(self):
        if not self.controller:
            return
        self.username = self.cmbStudents.currentText()
        student_groups = set(self.controller.list_user_groups(self.username))
        all_groups = set(self.controller.list_groups())

        self.lstStudentGroups.clear()
        for group in sorted(student_groups):
            self.lstStudentGroups.addItem(group)

        self.lstAvailableGroups.clear()
        for group in sorted(all_groups - student_groups):
            self.lstAvailableGroups.addItem(group)

    def _on_add_clicked(self):
        item = self.lstAvailableGroups.currentItem()
        if not item:
            return
        group = item.text()
        if self.controller.add_user_to_group(self.username, group):
            QMessageBox.information(self, "Sucesso", f"Aluno adicionado à turma '{group}'.")
        else:
            QMessageBox.critical(
                self, "Erro", f"Não foi possível adicionar o aluno à turma '{group}'."
            )
        self.refresh_lists()

    def _on_remove_clicked(self):
        item = self.lstStudentGroups.currentItem()
        if not item:
            return
        group = item.text()
        if self.controller.remove_user_from_group(self.username, group):
            QMessageBox.information(self, "Sucesso", f"Aluno removido da turma '{group}'.")
        else:
            QMessageBox.critical(
                self, "Erro", f"Não foi possível remover o aluno da turma '{group}'."
            )
        self.refresh_lists()

    def _on_transfer_clicked(self):
        item_old = self.lstStudentGroups.currentItem()
        item_new = self.lstAvailableGroups.currentItem()
        if not item_old or not item_new:
            return
        old_group = item_old.text()
        new_group = item_new.text()
        if self.controller.transfer_user_group(self.username, old_group, new_group):
            QMessageBox.information(
                self,
                "Sucesso",
                f"Aluno transferido de '{old_group}' para '{new_group}'.",
            )
        else:
            QMessageBox.critical(
                self,
                "Erro",
                f"Não foi possível transferir o aluno de '{old_group}' para '{new_group}'.",
            )
        self.refresh_lists()
