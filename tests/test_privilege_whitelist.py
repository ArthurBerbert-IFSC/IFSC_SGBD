import unittest

from gerenciador_postgres.db_manager import DBManager


class DummyCursor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def execute(self, sql, params=None):
        pass


class DummyConn:
    def cursor(self):
        return DummyCursor()


class PrivilegeWhitelistTests(unittest.TestCase):
    def setUp(self):
        self.dbm = DBManager(DummyConn())

    def test_invalid_table_privilege(self):
        with self.assertRaises(ValueError):
            self.dbm.apply_group_privileges("grp", {"public": {"t1": {"SELECT", "BAD"}}})


if __name__ == "__main__":
    unittest.main()
