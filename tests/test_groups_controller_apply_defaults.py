import pytest
pytest.importorskip("PyQt6.QtCore")

from gerenciador_postgres.controllers.groups_controller import GroupsController


class DummyDAO:
    def get_default_privileges(self, objtype="r"):
        return {
            "_meta": {"owner_roles": {"public": "owner1"}},
            "public": {"grp_a": {"SELECT"}},
        }


class DummyRoleManager:
    def __init__(self):
        self.dao = DummyDAO()

    def add_user_to_group(self, username, group):
        return True


def test_apply_defaults_to_user(monkeypatch):
    rm = DummyRoleManager()
    ctrl = GroupsController(rm)

    monkeypatch.setattr(ctrl, "list_user_groups", lambda u: ["grp_a"])

    calls = []

    def fake_alter(role, schema, obj_type, privileges, owner=None, emit_signal=True):
        calls.append((role, schema, obj_type, privileges, owner))
        return True

    ctrl.alter_default_privileges = fake_alter  # type: ignore

    assert ctrl.apply_defaults_to_user("bob")
    assert calls == [("bob", "public", "tables", {"SELECT"}, "owner1")]

