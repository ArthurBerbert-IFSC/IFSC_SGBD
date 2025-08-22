import unittest
import sys
import pathlib
import unittest

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

    def test_alter_default_privileges_grant(self):
        self.dbm.alter_default_privileges("grp", "public", "tables", {"SELECT"})
        executed = [str(s) for s in self.conn.cursor_obj.executed]
        self.assertEqual(len(executed), 1)
        self.assertIn("GRANT", executed[0])
        self.assertIn("SELECT", executed[0])
        self.assertNotIn("REVOKE", executed[0])

    def test_alter_default_privileges_grant_and_revoke(self):
        def fake_get_default_privileges(owner=None, objtype="r", schema=None):
            return {"public": {"grp": {"SELECT"}}}

        self.dbm.get_default_privileges = fake_get_default_privileges
        self.dbm.alter_default_privileges("grp", "public", "tables", {"INSERT"})
        executed = [str(s) for s in self.conn.cursor_obj.executed]
        self.assertEqual(len(executed), 2)
        self.assertIn("REVOKE", executed[0])
        self.assertIn("SELECT", executed[0])
        self.assertIn("GRANT", executed[1])
        self.assertIn("INSERT", executed[1])

    def test_alter_default_privileges_noop(self):
        def fake_get_default_privileges(owner=None, objtype="r", schema=None):
            return {"public": {"grp": {"SELECT"}}}

        self.dbm.get_default_privileges = fake_get_default_privileges
        result = self.dbm.alter_default_privileges("grp", "public", "tables", {"SELECT"})
        self.assertTrue(result)
        self.assertIsNone(self.conn.cursor_obj)

    def test_get_default_privileges_multiple_owners(self):
        rows = [
            ("owner1", "public", "grp", "SELECT", False),
            ("owner2", "public", "grp", "INSERT", False),
        ]

        class Cur:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                pass

            def execute(self, sql, params=None):
                pass

            def fetchall(self):
                return rows

        class Conn:
            def cursor(self):
                return Cur()

            def commit(self):
                pass

        dbm = DBManager(Conn())
        res = dbm.get_default_privileges()
        self.assertEqual(res["public"]["grp"], {"SELECT", "INSERT"})
        owners = res["_meta"]["owner_roles"]["public"]
        self.assertEqual(owners["owner1"], {"SELECT"})
        self.assertEqual(owners["owner2"], {"INSERT"})


if __name__ == "__main__":
    unittest.main()
