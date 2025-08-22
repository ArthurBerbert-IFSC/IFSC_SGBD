import os
import sys
import pathlib
import pytest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

pytest.importorskip("PyQt6.QtWidgets")
from gerenciador_postgres.db_manager import DBManager
from gerenciador_postgres.gui.privileges_view import PrivilegesView
from PyQt6.QtWidgets import (
    QApplication,
    QTreeWidget,
    QListWidget,
    QPushButton,
    QWidget,
    QVBoxLayout,
)
from PyQt6.QtCore import Qt

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class DummyCursor:
    def __init__(self, conn):
        self.conn = conn
        self.result = []
        self.commands = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def execute(self, sql, params=None):
        self.commands.append(sql)
        sql_str = str(sql)
        if "FROM pg_namespace" in sql_str:
            role, schema = params
            privs = self.conn.grants.get(schema, set())
            self.result = [(priv.rstrip("*"), priv.endswith("*")) for priv in sorted(privs)]
        else:
            self.result = []

    def fetchall(self):
        return self.result


class DummyConn:
    def __init__(self):
        self.grants = {}
        self.last_cursor = None

    def cursor(self):
        self.last_cursor = DummyCursor(self)
        return self.last_cursor


def test_grant_and_display_schema_privileges():
    app = QApplication.instance() or QApplication([])
    conn = DummyConn()
    dbm = DBManager(conn)
    dbm.grant_schema_privileges("grp_role", "public", {"USAGE", "CREATE"})
    assert len(conn.last_cursor.commands) == 2
    conn.grants = {"public": {"USAGE", "CREATE"}}
    privs = dbm.get_schema_privileges("grp_role")
    assert privs == {"public": {"USAGE", "CREATE"}}

    class DummyController:
        def get_schema_tables(self):
            return {"public": []}

        def get_group_privileges(self, group):
            return {}

        def get_schema_level_privileges(self, group):
            return privs

        def get_default_table_privileges(self, group):
            return {}

    view = PrivilegesView.__new__(PrivilegesView)
    view.controller = DummyController()
    view.current_group = "grp_role"
    view.schema_list = QListWidget()
    view.schema_details_panel = QWidget()
    view.schema_details_layout = QVBoxLayout()
    view.schema_details_panel.setLayout(view.schema_details_layout)
    view.treePrivileges = QTreeWidget()
    view.btnApplyTemplate = QPushButton()
    view.btnSave = QPushButton()
    view.btnSweep = QPushButton()
    view.lstMembers = QListWidget()

    view._populate_privileges()
    item = view.schema_list.item(0)
    view._update_schema_details(item, None)

    assert view.cb_usage.isChecked()
    assert view.cb_create.isChecked()


def test_general_item_controls_table_privileges():
    app = QApplication.instance() or QApplication([])

    class DummyController:
        def get_schema_tables(self):
            return {"public": ["t1", "t2"]}

        def get_group_privileges(self, group):
            return {}

        def get_schema_level_privileges(self, group):
            return {}

        def get_default_table_privileges(self, group):
            return {}

    view = PrivilegesView.__new__(PrivilegesView)
    view.controller = DummyController()
    view.current_group = "grp"
    view.schema_list = QListWidget()
    view.schema_details_panel = QWidget()
    view.schema_details_layout = QVBoxLayout()
    view.schema_details_panel.setLayout(view.schema_details_layout)
    view.treePrivileges = QTreeWidget()
    view.treeDbPrivileges = QTreeWidget()
    view.btnApplyTemplate = QPushButton()
    view.btnSave = QPushButton()
    view.btnSweep = QPushButton()
    view.lstMembers = QListWidget()

    view._populate_privileges()
    schema_item = view.treePrivileges.topLevelItem(0)
    geral = schema_item.child(0)
    assert geral.text(0) == "Geral"
    for col in range(1, 5):
        assert geral.checkState(col) == Qt.CheckState.Unchecked

    # Marca SELECT em "Geral" e aplica a todas as tabelas
    geral.setCheckState(1, Qt.CheckState.Checked)
    view._on_table_priv_changed(geral, 1)
    for i in range(1, schema_item.childCount()):
        assert schema_item.child(i).checkState(1) == Qt.CheckState.Checked
    state = view._priv_cache[(view.current_group, "public")]
    assert state.table_privs["t1"] == {"SELECT"}
    assert state.table_privs["t2"] == {"SELECT"}

    # Desmarca SELECT em uma tabela e verifica estado parcial
    t2 = schema_item.child(2)
    t2.setCheckState(1, Qt.CheckState.Unchecked)
    view._on_table_priv_changed(t2, 1)
    assert geral.checkState(1) == Qt.CheckState.PartiallyChecked
    assert state.table_privs["t2"] == set()

    # Reverte mudança e confere estado consistente
    t2.setCheckState(1, Qt.CheckState.Checked)
    view._on_table_priv_changed(t2, 1)
    assert geral.checkState(1) == Qt.CheckState.Checked
