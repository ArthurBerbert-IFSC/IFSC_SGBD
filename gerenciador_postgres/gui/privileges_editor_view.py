from __future__ import annotations

"""Tabbed editor for managing PostgreSQL privileges.

This widget exposes a ``QTabWidget`` with four tabs:
``Esquema``
    Placeholder for schema selection.
``Objetos``
    Placeholder for object level management.
``Defaults por criador``
    Panel that lists creator roles and a matrix of default privilege
    options for future objects.
``Pré-visualização``
    Read-only preview of generated SQL statements.

The view provides ``Gerar SQL`` and ``Aplicar Alterações`` buttons.  The
former collects the selections in the *Defaults por criador* tab and
shows the resulting statements with coloured badges in the preview tab;
``Aplicar Alterações`` forwards the operations to the provided
:class:`~gerenciador_postgres.executor.Executor` instance.
"""

from typing import Iterable, Mapping

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTabWidget,
    QListWidget,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QTextEdit,
)

from ..executor import Executor


class PrivilegesEditorView(QWidget):
    """Simple tabbed interface for privilege management."""

    def __init__(self, parent: QWidget | None = None, executor: Executor | None = None):
        super().__init__(parent)
        self.executor = executor
        self._operations: list[Mapping[str, object]] = []
        self._setup_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        # --- Esquema tab -------------------------------------------------
        self.lstSchemas = QListWidget()
        self.tabs.addTab(self.lstSchemas, "Esquema")

        # --- Objetos tab -------------------------------------------------
        lbl_objects = QLabel("Gerenciamento de objetos em desenvolvimento.")
        lbl_objects.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tabs.addTab(lbl_objects, "Objetos")

        # --- Defaults por criador tab -----------------------------------
        self.treeCreators = QTreeWidget()
        self.treeCreators.setHeaderLabels(["Role", "Tables", "Sequences"])
        self.tabs.addTab(self.treeCreators, "Defaults por criador")

        # --- Pré-visualização tab ---------------------------------------
        self.txtPreview = QTextEdit()
        self.txtPreview.setReadOnly(True)
        self.tabs.addTab(self.txtPreview, "Pré-visualização")

        layout.addWidget(self.tabs)

        # --- Action buttons ---------------------------------------------
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        self.btnGenerate = QPushButton("Gerar SQL")
        self.btnApply = QPushButton("Aplicar Alterações")
        btn_layout.addWidget(self.btnGenerate)
        btn_layout.addWidget(self.btnApply)
        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------
    def _connect_signals(self):
        self.btnGenerate.clicked.connect(self._on_generate_sql)
        self.btnApply.clicked.connect(self._on_apply_changes)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_creators(self, roles: Iterable[str]):
        """Populate the creators tree with the provided roles."""
        self.treeCreators.clear()
        for role in roles:
            item = QTreeWidgetItem([role])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            # create check boxes for each privilege column
            for col in range(1, self.treeCreators.columnCount()):
                item.setCheckState(col, Qt.CheckState.Unchecked)
            self.treeCreators.addTopLevelItem(item)

    # ------------------------------------------------------------------
    def _collect_operations(self) -> list[Mapping[str, object]]:
        ops: list[Mapping[str, object]] = []
        for i in range(self.treeCreators.topLevelItemCount()):
            item = self.treeCreators.topLevelItem(i)
            role = item.text(0)
            # simplistic mapping: checked columns -> ALTER DEFAULT PRIVILEGES
            if item.checkState(1) == Qt.CheckState.Checked:
                ops.append({
                    "action": "ALTER DEFAULT PRIVILEGES",
                    "badge": "ALTER DEFAULT PRIVILEGES",
                    "target": "TABLES",
                    "schema": "public",
                    "privileges": ["ALL"],
                    "grantee": role,
                })
            if item.checkState(2) == Qt.CheckState.Checked:
                ops.append({
                    "action": "ALTER DEFAULT PRIVILEGES",
                    "badge": "ALTER DEFAULT PRIVILEGES",
                    "target": "SEQUENCES",
                    "schema": "public",
                    "privileges": ["USAGE"],
                    "grantee": role,
                })
        return ops

    # ------------------------------------------------------------------
    def _on_generate_sql(self):
        self._operations = self._collect_operations()
        self._update_preview()
        # switch to preview tab to highlight result
        self.tabs.setCurrentWidget(self.txtPreview)

    # ------------------------------------------------------------------
    def _on_apply_changes(self):
        if self.executor and self._operations:
            self.executor.apply(self._operations)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _update_preview(self):
        lines: list[str] = []
        for op in self._operations:
            badge = op.get("badge", op["action"])
            colour = self._badge_colour(badge)
            sql_line = self._format_sql(op)
            html = (
                f"<span style='background-color:{colour}; color:white; border-radius:3px;"\
                f" padding:2px'>[{badge}]</span> {sql_line}"
            )
            lines.append(html)
        self.txtPreview.setHtml("<br/>".join(lines))

    # ------------------------------------------------------------------
    def _badge_colour(self, badge: str) -> str:
        colours = {
            "GRANT": "#28a745",
            "REVOKE": "#dc3545",
            "ALTER DEFAULT PRIVILEGES": "#007bff",
            "WARN-DEPEND": "#ffc107",
            "PRESERVED-3rd-party": "#6f42c1",
        }
        return colours.get(badge, "#6c757d")

    # ------------------------------------------------------------------
    def _format_sql(self, op: Mapping[str, object]) -> str:
        action = op["action"].upper()
        grantee = op["grantee"]
        privs = ", ".join(op.get("privileges", [])) or "ALL PRIVILEGES"
        if action == "ALTER DEFAULT PRIVILEGES":
            target = op["target"].upper()
            return (
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA {op['schema']} "
                f"GRANT {privs} ON {target} TO {grantee};"
            )
        target = op["target"].upper()
        if target == "SCHEMA":
            obj = f"SCHEMA {op['schema']}"
        else:
            obj = f"{target} {op['schema']}.{op['object']}"
        keyword = "TO" if action == "GRANT" else "FROM"
        return f"{action} {privs} ON {obj} {keyword} {grantee};"


__all__ = ["PrivilegesEditorView"]
