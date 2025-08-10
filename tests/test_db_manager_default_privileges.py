import unittest
import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from gerenciador_postgres.db_manager import DBManager


class DummyCursor:
    def __init__(self):
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def execute(self, sql, params=None):
        self.executed.append(str(sql))


class DummyConn:
    def cursor(self):
        self.cursor_obj = DummyCursor()
        return self.cursor_obj


class DBManagerDefaultPrivTests(unittest.TestCase):
    def setUp(self):
        self.conn = DummyConn()
        self.dbm = DBManager(self.conn)

    def test_alter_default_privileges(self):
        self.dbm.alter_default_privileges("grp", "public", "tables", {"SELECT"})
        executed = [str(s) for s in self.conn.cursor_obj.executed]
        self.assertEqual(len(executed), 2)
        self.assertIn("ALTER DEFAULT PRIVILEGES", executed[0])
        self.assertIn("REVOKE ALL", executed[0])
        self.assertIn("GRANT", executed[1])
        self.assertIn("SELECT", executed[1])


if __name__ == "__main__":
    unittest.main()
