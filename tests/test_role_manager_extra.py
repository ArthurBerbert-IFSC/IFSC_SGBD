import logging
import unittest

from gerenciador_postgres.role_manager import RoleManager


class DummyConn:
    def __init__(self):
        self.committed = False

    def commit(self):
        self.committed = True

    def rollback(self):
        pass


class DummyDAO:
    def __init__(self):
        self.conn = DummyConn()
        self.inserted = []
        self.granted = None
        self.revoked = None
        self.groups = {"alice": ["grp_a", "grp_b"]}

    def find_user_by_name(self, username):
        return None

    def insert_user(self, username, password):
        self.inserted.append((username, password))

    def list_user_groups(self, username):
        return self.groups.get(username, [])

    def grant_privileges(self, role, schema, table, privileges):
        self.granted = (role, schema, table, privileges)

    def revoke_privileges(self, role, schema, table, privileges):
        self.revoked = (role, schema, table, privileges)


class RoleManagerExtraTests(unittest.TestCase):
    def setUp(self):
        self.dao = DummyDAO()
        logger = logging.getLogger("test")
        self.rm = RoleManager(self.dao, logger)

    def test_bulk_create_users(self):
        users = {"u1": "p1", "u2": "p2"}
        created = self.rm.bulk_create_users(users)
        self.assertEqual(created, ["u1", "u2"])
        self.assertEqual(self.dao.inserted, [("u1", "p1"), ("u2", "p2")])
        self.assertTrue(self.dao.conn.committed)

    def test_list_user_groups(self):
        groups = self.rm.list_user_groups("alice")
        self.assertEqual(groups, ["grp_a", "grp_b"])

    def test_grant_and_revoke(self):
        privs = {"SELECT", "INSERT"}
        self.assertTrue(
            self.rm.grant_privileges("grp_a", "public", "t1", privs)
        )
        self.assertEqual(self.dao.granted, ("grp_a", "public", "t1", privs))
        self.assertTrue(self.dao.conn.committed)
        self.dao.conn.committed = False
        self.assertTrue(
            self.rm.revoke_privileges("grp_a", "public", "t1", privs)
        )
        self.assertEqual(self.dao.revoked, ("grp_a", "public", "t1", privs))
        self.assertTrue(self.dao.conn.committed)


if __name__ == "__main__":
    unittest.main()
