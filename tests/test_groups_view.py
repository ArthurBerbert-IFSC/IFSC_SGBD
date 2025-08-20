import types
from types import SimpleNamespace
import pytest
pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtWidgets import QMessageBox

from gerenciador_postgres.gui.groups_view import PrivilegesView


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


def _make_view(controller):
    view = PrivilegesView.__new__(PrivilegesView)
    view.controller = controller
    view.lstGroups = SimpleNamespace(
        currentItem=lambda: SimpleNamespace(text=lambda: "grp_test")
    )
    return view


def test_delete_group_without_removing_members(monkeypatch):
    controller = DummyController()
    view = _make_view(controller)
    monkeypatch.setattr(
        "gerenciador_postgres.gui.groups_view.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.No,
    )
    monkeypatch.setattr(
        "gerenciador_postgres.gui.groups_view.QMessageBox.information",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "gerenciador_postgres.gui.groups_view.QMessageBox.critical",
        lambda *a, **k: None,
    )

    view._on_delete_group()
    assert controller.deleted == "grp_test"
    assert controller.deleted_with_members is None
