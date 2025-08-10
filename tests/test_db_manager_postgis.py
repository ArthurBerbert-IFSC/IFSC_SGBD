import unittest
import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from gerenciador_postgres.db_manager import DBManager


class DummyCursor:
    def __init__(self, extension_exists, ext_schema="public"):
        self.extension_exists = extension_exists
        self.ext_schema = ext_schema
        self.executed = []
        self.params = []
        self.results = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def execute(self, sql, params=None):
        sql_str = str(sql)
        self.executed.append(sql_str)
        self.params.append(params)
        if "FROM pg_extension" in sql_str:
            if self.extension_exists:
                self.results = [("postgis", self.ext_schema)]
            else:
                self.results = []
        elif "current_setting('search_path')" in sql_str:
            self.results = [("public",)]
        else:
            self.results = []

    def fetchone(self):
        return self.results[0] if self.results else None


class DummyConn:
    def __init__(self, cursor_obj):
        self.cursor_obj = cursor_obj

    def cursor(self):
        return self.cursor_obj

    def get_dsn_parameters(self):
        return {"user": "testuser", "dbname": "testdb"}


class DBManagerPostgisTests(unittest.TestCase):
    def test_create_extension_when_missing(self):
        cur = DummyCursor(extension_exists=False)
        conn = DummyConn(cur)
        dbm = DBManager(conn)
        dbm.enable_postgis("gis")

        executed = cur.executed
        self.assertTrue(any("CREATE EXTENSION IF NOT EXISTS postgis" in q for q in executed))
        self.assertTrue(any("ALTER ROLE" in q for q in executed))
        self.assertTrue(any("ALTER DATABASE" in q for q in executed))

        # Verifica se o schema foi incluído no search_path
        alter_role_idx = next(i for i, q in enumerate(executed) if "ALTER ROLE" in q)
        self.assertIn("gis", cur.params[alter_role_idx][0])

    def test_use_existing_extension(self):
        cur = DummyCursor(extension_exists=True, ext_schema="gis")
        conn = DummyConn(cur)
        dbm = DBManager(conn)
        dbm.enable_postgis("other")

        executed = cur.executed
        self.assertFalse(any("CREATE EXTENSION IF NOT EXISTS postgis" in q for q in executed))
        self.assertTrue(any("ALTER ROLE" in q for q in executed))
        self.assertTrue(any("ALTER DATABASE" in q for q in executed))

        alter_role_idx = next(i for i, q in enumerate(executed) if "ALTER ROLE" in q)
        self.assertIn("gis", cur.params[alter_role_idx][0])


if __name__ == "__main__":
    unittest.main()
