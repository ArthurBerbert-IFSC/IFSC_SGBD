import unittest
import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from gerenciador_postgres.db_manager import DBManager


class DummyCursor:
    def __init__(self):
        self.executed = []
        self.connection = None
        self.result = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def execute(self, sql, params=None):
        sql_str = str(sql)
        self.executed.append(sql_str)
        if "server_version_num" in sql_str:
            self.result = [(150000,)]
        else:
            self.result = []

    def fetchone(self):
        return self.result[0] if self.result else None

    def fetchall(self):
        return self.result


class DummyConn:
    def __init__(self):
        self.autocommit = True
        self.cursor_obj = None

    def cursor(self):
        self.cursor_obj = DummyCursor()
        return self.cursor_obj

    def commit(self):
        pass


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

    def test_alter_default_privileges_noop(self):
        def fake_get_default_privileges(role, code):
            return {"public": {"grp": {"SELECT"}}}

        self.dbm.get_default_privileges = fake_get_default_privileges
        result = self.dbm.alter_default_privileges("grp", "public", "tables", {"SELECT"})
        self.assertTrue(result)
        self.assertIsNone(self.conn.cursor_obj)


if __name__ == "__main__":
    unittest.main()
