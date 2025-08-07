import unittest

from gerenciador_postgres.db_manager import DBManager


class DummyCursor:
    def __init__(self):
        self.executed = None
        self.result = [("grp1",), ("grp2",)]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def execute(self, sql, params=None):
        self.executed = (sql, params)

    def fetchall(self):
        return self.result


class DummyConn:
    def cursor(self):
        return DummyCursor()


class DBManagerUserGroupTests(unittest.TestCase):
    def test_list_user_groups(self):
        dbm = DBManager(DummyConn())
        groups = dbm.list_user_groups("bob")
        self.assertEqual(groups, ["grp1", "grp2"])


if __name__ == "__main__":
    unittest.main()
