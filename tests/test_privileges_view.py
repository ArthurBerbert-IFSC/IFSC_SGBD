import os
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

from gerenciador_postgres.gui.users_view import UsersView
from gerenciador_postgres.gui.privileges_view import PrivilegesView


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


def test_update_schema_details_multiple_owners():
    app = QApplication.instance() or QApplication([])

    class Ctrl:
        def get_schema_level_privileges(self, role):
            return {"public": set()}

        def get_default_table_privileges(self, role):
            return {"public": {"owner1": {"SELECT"}, "owner2": {"INSERT"}}}

    view = PrivilegesView.__new__(PrivilegesView)
    QWidget.__init__(view)
    view.controller = Ctrl()
    view.current_group = "grp"
    view.schema_list = QListWidget()
    item = QListWidgetItem("public")
    view.schema_list.addItem(item)
    view.schema_details_layout = QVBoxLayout()
    view.btnSchemaDelete = QPushButton()
    view.btnSchemaOwner = QPushButton()
    view._priv_cache = {}

    view._update_schema_details(item, None)
    state = view._priv_cache[("grp", "public")]
    assert state.default_privs == {"owner1": {"SELECT"}, "owner2": {"INSERT"}}
    assert view.cb_default_select.isChecked()
    assert view.cb_default_insert.isChecked()
    assert not view.cb_default_update.isChecked()
    assert not view.cb_default_delete.isChecked()
