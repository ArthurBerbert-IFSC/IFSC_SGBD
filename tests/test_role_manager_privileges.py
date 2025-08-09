import logging
import unittest
from contextlib import contextmanager

from gerenciador_postgres.role_manager import RoleManager


class DummyDAO:
    def __init__(self, privileges):
        self.conn = DummyConn()
        self.privileges = privileges

    def get_group_privileges(self, group):
        return self.privileges.get(group, {})

    @contextmanager
    def transaction(self):
        try:
            yield
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise


class DummyConn:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class RoleManagerPrivilegesTests(unittest.TestCase):
    def setUp(self):
        privs = {"grp_a": {"public": {"t1": {"SELECT"}}}}
        self.dao = DummyDAO(privs)
        self.rm = RoleManager(self.dao, logging.getLogger("test"))

    def test_get_group_privileges(self):
        expected = {"public": {"t1": {"SELECT"}}}
        self.assertEqual(self.rm.get_group_privileges("grp_a"), expected)
        self.assertEqual(self.rm.get_group_privileges("grp_b"), {})


if __name__ == "__main__":
    unittest.main()
