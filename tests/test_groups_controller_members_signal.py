import pytest
pytest.importorskip("PyQt6.QtCore")

from gerenciador_postgres.controllers.groups_controller import GroupsController


class DummyRoleManager:
    def __init__(self):
        self.members = {}

    def add_user_to_group(self, username, group):
        self.members.setdefault(group, set()).add(username)
        return True

    def remove_user_from_group(self, username, group):
        self.members.get(group, set()).discard(username)
        return True

    def transfer_user_group(self, username, old_group, new_group):
        self.remove_user_from_group(username, old_group)
        self.add_user_to_group(username, new_group)
        return True

    def list_group_members(self, group):
        return sorted(self.members.get(group, []))

    # The following stubs satisfy UsersController delegation
    def list_groups(self):
        return []


def test_members_changed_signal_emitted():
    rm = DummyRoleManager()
    ctrl = GroupsController(rm)
    received = []
    ctrl.members_changed.connect(received.append)

    assert ctrl.add_user_to_group("alice", "grp_a", auto_apply_defaults=False)
    assert received == ["grp_a"]

