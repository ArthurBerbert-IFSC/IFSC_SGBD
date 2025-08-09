import logging
import unittest

from gerenciador_postgres.role_manager import RoleManager
from gerenciador_postgres.controllers.users_controller import UsersController


class DummyDAO:
    def __init__(self):
        self.conn = DummyConn()
        self.members = {}
        self.users = {}

    def list_user_groups(self, username):
        return sorted(self.members.get(username, set()))

    def add_user_to_group(self, username, group):
        self.members.setdefault(username, set()).add(group)

    def remove_user_from_group(self, username, group):
        if username in self.members:
            self.members[username].discard(group)

    def list_groups(self):
        return ["grp_a", "grp_b"]

    def find_user_by_name(self, username):
        return self.users.get(username)

    def insert_user(self, username, password, valid_until=None):
        self.users[username] = {
            'password': password,
            'valid_until': valid_until,
        }


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

    def test_create_user_with_expiration(self):
        self.uc.create_user('alice', 'pw', '2025-12-31')
        self.assertEqual(self.dao.users['alice']['valid_until'], '2025-12-31')

    def test_create_users_batch(self):
        data = [
            ("111", "José Silva"),
            ("222", "José Ângelo"),
        ]
        created = self.uc.create_users_batch(data, "2024-06-30")
        self.assertEqual(set(created), {"jose", "jose.angelo"})
        self.assertEqual(self.dao.users["jose"]["password"], "111")
        self.assertEqual(self.dao.users["jose.angelo"]["valid_until"], "2024-06-30")


if __name__ == "__main__":
    unittest.main()
