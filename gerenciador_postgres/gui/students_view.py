from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QToolBar,
    QPushButton,
    QFileDialog,
    QInputDialog,
    QLineEdit,
    QMessageBox,
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt
from pathlib import Path
from datetime import datetime

from ..path_config import LOG_DIR
from config.permission_templates import DEFAULT_TEMPLATE


class StudentsView(QWidget):
    """Interface para gerenciamento de alunos."""

    def __init__(self, parent=None, controller=None):
        super().__init__(parent)
        assets_dir = Path(__file__).resolve().parents[2] / "assets"
        self.setWindowIcon(QIcon(str(assets_dir / "usuarios.jpeg")))
        self.controller = controller
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.toolbar = QToolBar()
        self.btnImport = QPushButton("Importar Alunos")
        self.toolbar.addWidget(self.btnImport)
        layout.addWidget(self.toolbar)
        self.setLayout(layout)

    def _connect_signals(self):
        self.btnImport.clicked.connect(self.on_import_students_clicked)

    # ---------------------------------------------------------------
    def on_import_students_clicked(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Arquivo", "", "Text Files (*.txt)"
        )
        if not file_name:
            return

        group_name = self._choose_group()
        if not group_name:
            return

        self._import_students(file_name, group_name)

    def _choose_group(self):
        if not self.controller:
            return None
        groups = self.controller.list_groups() or []
        groups = sorted(groups)
        groups.append("Criar nova turma")
        choice, ok = QInputDialog.getItem(
            self,
            "Selecionar Turma",
            "Escolha a turma:",
            groups,
            editable=False,
        )
        if not ok or not choice:
            return None
        if choice == "Criar nova turma":
            group_name, ok = QInputDialog.getText(
                self,
                "Nova Turma",
                "Digite o nome da turma (o prefixo 'turma_' será adicionado automaticamente):",
                QLineEdit.EchoMode.Normal,
                "",
            )
            if not ok or not group_name.strip():
                return None
            group_name = group_name.strip().lower()
            if not group_name.startswith("turma_"):
                group_name = f"turma_{group_name}"
            try:
                self.controller.create_group(group_name)
                self.controller.apply_template_to_group(group_name, DEFAULT_TEMPLATE)
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Erro",
                    f"Não foi possível criar a turma.\nMotivo: {e}",
                )
                return None
            return group_name
        return choice

    def _import_students(self, file_name: str, group_name: str):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOG_DIR / f"import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        errors = 0
        total = 0
        success = 0
        with open(log_path, "w", encoding="utf-8") as log_file:
            try:
                with open(file_name, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        total += 1
                        try:
                            parts = line.split()
                            if len(parts) < 2:
                                raise ValueError("Formato inválido")
                            matricula = parts[0]
                            name_parts = parts[1:]
                            username_base = f"{name_parts[0].lower()}.{name_parts[-1].lower()}"
                            username = username_base
                            attempt = 1
                            while True:
                                try:
                                    self.controller.create_user(username, matricula)
                                    break
                                except Exception as e:
                                    if "já existe" in str(e).lower():
                                        username = f"{username_base}{attempt}"
                                        attempt += 1
                                        continue
                                    else:
                                        raise
                            self.controller.add_user_to_group(username, group_name)
                            success += 1
                        except Exception as e:
                            errors += 1
                            log_file.write(f"Linha '{line}': {e}\n")
            except Exception as e:
                errors += 1
                log_file.write(f"Falha geral: {e}\n")

        if errors == 0:
            log_path.unlink(missing_ok=True)
            QMessageBox.information(
                self,
                "Importação Concluída",
                f"{success}/{total} alunos importados com sucesso.",
            )
        else:
            msg = QMessageBox(self)
            msg.setWindowTitle("Importação Concluída")
            msg.setText(f"{success}/{total} alunos importados.")
            msg.setInformativeText(
                f"Ocorreram falhas. Veja o <a href='file://{log_path}'>log</a>."
            )
            msg.setTextFormat(Qt.TextFormat.RichText)
            msg.exec()
