import logging
import unittest

from gerenciador_postgres.role_manager import RoleManager
from gerenciador_postgres.controllers.users_controller import UsersController


class DummyDAO:
    def __init__(self):
        self.conn = DummyConn()
        self.members = {}

    def list_user_groups(self, username):
        return sorted(self.members.get(username, set()))

    def add_user_to_group(self, username, group):
        self.members.setdefault(username, set()).add(group)

    def remove_user_from_group(self, username, group):
        if username in self.members:
            self.members[username].discard(group)

    def list_groups(self):
        return ["grp_a", "grp_b"]


class DummyConn:
    def commit(self):
        pass

    def rollback(self):
        pass


class UserGroupManagementTests(unittest.TestCase):
    def setUp(self):
        self.dao = DummyDAO()
        logger = logging.getLogger("test")
        self.rm = RoleManager(self.dao, logger)
        self.uc = UsersController(self.rm)

    def test_add_and_remove_groups(self):
        self.assertEqual(self.uc.list_user_groups("alice"), [])
        self.assertTrue(self.uc.add_user_to_group("alice", "grp_a"))
        self.assertEqual(self.uc.list_user_groups("alice"), ["grp_a"])
        self.assertTrue(self.uc.remove_user_from_group("alice", "grp_a"))
        self.assertEqual(self.uc.list_user_groups("alice"), [])


if __name__ == "__main__":
    unittest.main()
