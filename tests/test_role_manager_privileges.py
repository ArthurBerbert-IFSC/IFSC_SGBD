import unittest
import logging
import unittest
import logging

from gerenciador_postgres.role_manager import RoleManager


class DummyDAO:
    def __init__(self, privileges):
        self.conn = DummyConn()
        self.privileges = privileges

    def get_group_privileges(self, group):
        return self.privileges.get(group, {})


class DummyConn:
    def commit(self):
        pass

    def rollback(self):
        pass


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
