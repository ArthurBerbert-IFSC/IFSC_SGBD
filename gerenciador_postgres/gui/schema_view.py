from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QToolBar,
    QPushButton,
    QListWidget,
    QInputDialog,
    QMessageBox,
)
from PyQt6.QtGui import QIcon
from pathlib import Path
import psycopg2.errors


class SchemaView(QWidget):
    def __init__(self, parent=None, controller=None, logger=None):
        super().__init__(parent)
        assets_dir = Path(__file__).resolve().parents[2] / "assets"
        self.setWindowIcon(QIcon(str(assets_dir / "icone.png")))
        self.controller = controller
        self.logger = logger
        self.setWindowTitle("Gerenciador de Schemas")
        self._setup_ui()
        self._connect_signals()
        if self.controller:
            self.controller.data_changed.connect(self.refresh_list)
        self.refresh_list()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.toolbar = QToolBar()
        self.btnNew = QPushButton("Novo Schema")
        self.btnDelete = QPushButton("Excluir")
        self.btnOwner = QPushButton("Alterar Owner")
        self.btnDelete.setEnabled(False)
        self.btnOwner.setEnabled(False)
        self.toolbar.addWidget(self.btnNew)
        self.toolbar.addWidget(self.btnDelete)
        self.toolbar.addWidget(self.btnOwner)
        layout.addWidget(self.toolbar)
        self.lstSchemas = QListWidget()
        layout.addWidget(self.lstSchemas)
        self.setLayout(layout)

    def _connect_signals(self):
        self.btnNew.clicked.connect(self.on_new_schema)
        self.btnDelete.clicked.connect(self.on_delete_schema)
        self.btnOwner.clicked.connect(self.on_change_owner)
        self.lstSchemas.currentItemChanged.connect(self.on_schema_selected)

    def refresh_list(self):
        self.lstSchemas.clear()
        if not self.controller:
            return
        try:
            for schema in self.controller.list_schemas():
                self.lstSchemas.addItem(schema)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao listar schemas:\n{e}")
            if self.logger:
                self.logger.error(f"Falha ao listar schemas: {e}")

    def on_schema_selected(self, current, previous):
        has_item = current is not None
        self.btnDelete.setEnabled(has_item)
        self.btnOwner.setEnabled(has_item)

    def on_new_schema(self):
        name, ok = QInputDialog.getText(self, "Novo Schema", "Nome do schema:")
        if not ok or not name:
            return
        owner = None
        roles = []
        if self.controller:
            try:
                roles = self.controller.list_roles()
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Falha ao listar roles: {e}")
        if roles:
            items = [""] + roles
            owner, ok2 = QInputDialog.getItem(
                self, "Proprietário", "Owner (opcional):", items, 0, False
            )
            if not ok2:
                owner = None
        else:
            owner, ok2 = QInputDialog.getText(self, "Proprietário", "Owner (opcional):")
            if not ok2:
                owner = None
        try:
            self.controller.create_schema(name, owner or None)
            QMessageBox.information(self, "Sucesso", f"Schema '{name}' criado.")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível criar o schema:\n{e}")
            if self.logger:
                self.logger.error(f"Falha ao criar schema '{name}': {e}")

    def on_delete_schema(self):
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
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.controller.delete_schema(name)
                QMessageBox.information(self, "Sucesso", f"Schema '{name}' removido.")
            except Exception as e:
                # Robustly detect dependent objects error (psycopg2 DependentObjectsStillExist / pgcode 2BP01 / message)
                def _root_exc(ex):
                    cur = ex
                    # Unwrap nested exceptions (cause/context) to find the DB error
                    while getattr(cur, "__cause__", None) is not None:
                        cur = cur.__cause__
                    return cur

                root = _root_exc(e)
                message = str(root)
                pgcode = getattr(root, "pgcode", None)
                is_deps_err = False
                try:
                    is_deps_err = isinstance(root, psycopg2.errors.DependentObjectsStillExist)
                except Exception:
                    is_deps_err = False
                if not is_deps_err:
                    # Fallbacks: PostgreSQL SQLSTATE 2BP01 and message hint
                    is_deps_err = (pgcode == "2BP01") or ("other objects depend on it" in message)

                if is_deps_err:
                    cascade_reply = QMessageBox.question(
                        self,
                        "Objetos Dependentes Encontrados",
                        f"O schema '{name}' possui objetos dependentes (tabelas, etc.).\n\n"
                        f"Deseja remover o schema e TODOS os objetos dependentes?\n\n"
                        f"ATENÇÃO: Esta ação é irreversível!",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if cascade_reply == QMessageBox.StandardButton.Yes:
                        try:
                            self.controller.delete_schema(name, cascade=True)
                            QMessageBox.information(self, "Sucesso", f"Schema '{name}' e objetos dependentes removidos.")
                        except Exception as cascade_e:
                            QMessageBox.critical(self, "Erro", f"Não foi possível remover o schema com CASCADE:\n{cascade_e}")
                            if self.logger:
                                self.logger.error(f"Falha ao remover schema '{name}' com CASCADE: {cascade_e}")
                    else:
                        # User declined CASCADE; inform original reason
                        QMessageBox.information(self, "Cancelado", "Exclusão sem CASCADE cancelada pelo usuário.")
                        if self.logger:
                            self.logger.info(f"Exclusão de schema '{name}' sem CASCADE cancelada pelo usuário devido a objetos dependentes.")
                else:
                    QMessageBox.critical(self, "Erro", f"Não foi possível remover o schema:\n{e}")
                    if self.logger:
                        self.logger.error(f"Falha ao remover schema '{name}': {e}")

    def on_change_owner(self):
        item = self.lstSchemas.currentItem()
        if not item:
            return
        name = item.text()
        roles = []
        if self.controller:
            try:
                roles = self.controller.list_roles()
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Falha ao listar roles: {e}")

        if roles:
            new_owner, ok = QInputDialog.getItem(
                self, "Alterar Owner", "Novo owner:", roles, 0, False
            )
        else:
            new_owner, ok = QInputDialog.getText(
                self, "Alterar Owner", f"Novo owner para '{name}':"
            )

        if not ok or not new_owner:
            return
        try:
            self.controller.change_owner(name, new_owner)
            QMessageBox.information(self, "Sucesso", f"Owner de '{name}' alterado.")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível alterar owner:\n{e}")
            if self.logger:
                self.logger.error(f"Falha ao alterar owner de '{name}': {e}")
