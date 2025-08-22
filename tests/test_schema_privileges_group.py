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
    view.lstMembers = QListWidget()

    view._populate_privileges()
    item = view.schema_list.item(0)
    view._update_schema_details(item, None)

    assert view.cb_usage.isChecked()
    assert view.cb_create.isChecked()
