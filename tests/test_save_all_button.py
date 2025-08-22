import os
import sys
import pathlib
import pytest
pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtWidgets import QApplication, QPushButton, QTreeWidget, QTreeWidgetItem, QListWidget, QMessageBox
from PyQt6.QtCore import Qt

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from gerenciador_postgres.gui.privileges_view import PrivilegesView, PrivilegesState

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class DummyController:
    def grant_database_privileges(self, role, privs):
        return True

    def grant_schema_privileges(self, *a, **k):
        return True

    def alter_default_privileges(self, *a, **k):
        return True

    def apply_group_privileges(self, *a, **k):
        return True


app = QApplication.instance() or QApplication([])


def _exec_sync(self, func, on_success, on_error, label):
    try:
        res = func()
        on_success(res)
    except Exception as e:
        on_error(e)


@pytest.fixture(autouse=True)
def _silent_msgboxes(monkeypatch):
    monkeypatch.setattr("gerenciador_postgres.gui.privileges_view.QMessageBox.information", lambda *a, **k: None)
    monkeypatch.setattr("gerenciador_postgres.gui.privileges_view.QMessageBox.warning", lambda *a, **k: None)
    monkeypatch.setattr("gerenciador_postgres.gui.privileges_view.QMessageBox.critical", lambda *a, **k: None)


def test_save_all_tracks_db_priv_changes():
    view = PrivilegesView.__new__(PrivilegesView)
    view.controller = DummyController()
    view.current_group = "role1"
    view._priv_cache = {}
    view._db_privs = set()
    view._db_dirty = False
    view.btnSaveAll = QPushButton()
    view.treeDbPrivileges = QTreeWidget()
    view.schema_list = QListWidget()
    view._update_save_all_state()
    assert not view.btnSaveAll.isEnabled()

    item = QTreeWidgetItem(["CONNECT"])
    item.setCheckState(0, Qt.CheckState.Checked)
    view._on_db_priv_changed(item, 0)
    assert view.btnSaveAll.isEnabled(), "Botão não habilitou após alteração de privilégio de banco"

    view._execute_async = _exec_sync.__get__(view, PrivilegesView)
    view._save_all_privileges()
    assert not view.btnSaveAll.isEnabled(), "Botão não desabilitou após salvar"


def test_save_all_tracks_schema_priv_changes():
    view = PrivilegesView.__new__(PrivilegesView)
    view.controller = DummyController()
    view.current_group = "role1"
    view.schema_list = QListWidget()
    view.btnSaveAll = QPushButton()
    view._db_dirty = False
    view._priv_cache = {("role1", "public"): PrivilegesState()}
    view._update_save_all_state()
    assert not view.btnSaveAll.isEnabled()

    view._update_schema_priv("role1", "public", "USAGE", True)
    assert view.btnSaveAll.isEnabled(), "Botão não habilitou após alteração de schema"

    def fake_save_state(role, schema):
        st = view._priv_cache[(role, schema)]
        st.dirty_schema = st.dirty_default = st.dirty_table = False
        return True

    view._save_state_sync = fake_save_state
    view._execute_async = _exec_sync.__get__(view, PrivilegesView)
    view._save_all_privileges()
    assert not view.btnSaveAll.isEnabled(), "Botão não desabilitou após salvar"
