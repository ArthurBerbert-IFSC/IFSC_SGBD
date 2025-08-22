import os
import pathlib
import sys
import pytest
pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtWidgets import (
    QApplication,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from gerenciador_postgres.gui.users_view import UsersView
from gerenciador_postgres.gui.privileges_view import PrivilegesView, PrivilegesState

class DummyController:
    def __init__(self):
        self.deleted = None
        self.deleted_with_members = None

    def list_group_members(self, group):
        return ["user1"]

    def delete_group(self, group):
        self.deleted = group
        return True

    def delete_group_and_members(self, group):
        self.deleted_with_members = group
        return True

    def list_groups(self):
        return ["grp_test"]


def _make_view(controller):
    view = UsersView.__new__(UsersView)
    view.controller = controller
    view._refresh_group_lists = lambda: None
    return view


def test_delete_group_without_removing_members(monkeypatch):
    controller = DummyController()
    view = _make_view(controller)
    monkeypatch.setattr(
        UsersView, "_select_groups_for_deletion", lambda self: ["grp_test"]
    )
    monkeypatch.setattr(
        "gerenciador_postgres.gui.users_view.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.No,
    )
    monkeypatch.setattr(
        "gerenciador_postgres.gui.users_view.QMessageBox.information",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "gerenciador_postgres.gui.users_view.QMessageBox.critical",
        lambda *a, **k: None,
    )

    view._on_delete_group()
    assert controller.deleted == "grp_test"
    assert controller.deleted_with_members is None
    
def test_save_default_privileges_multiple_owners(monkeypatch):
    class DummyPrivController:
        def __init__(self):
            self.calls = []

        def alter_default_privileges(self, role, schema, obj, privs, owner=None, emit_signal=False):
            self.calls.append((role, schema, owner, privs))
            return True

        def list_group_members(self, group):
            return ["u1", "u2"]

    controller = DummyPrivController()
    view = PrivilegesView.__new__(PrivilegesView)
    view.controller = controller
    view.current_group = "grp"
    st = PrivilegesState(default_privs={"SELECT"})
    view._priv_cache = {("grp", "public"): st}
    view._current_schema_checked = lambda: ("grp", "public")
    view._update_save_all_state = lambda: None
    view._execute_async = lambda func, on_success, on_error, label: on_success(func())
    monkeypatch.setattr(
        "gerenciador_postgres.gui.privileges_view.QMessageBox.information", lambda *a, **k: None
    )
    view._save_default_privileges(["u1", "u2"])
    assert [c[2] for c in controller.calls] == ["u1", "u2"]