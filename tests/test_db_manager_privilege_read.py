import sys
import pathlib
import unittest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from gerenciador_postgres.db_manager import DBManager


class DummyCursor:
    def __init__(self, db_privs, schema_privs):
        self.db_privs = db_privs
        self.schema_privs = schema_privs
        self.result = []
        self.last_query = ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def execute(self, sql, params=None):
        self.last_query = sql
        if "has_database_privilege" in sql:
            role, priv = params
            priv = "TEMP" if priv == "TEMPORARY" else priv
            self.result = [(priv in self.db_privs.get(role, set()),)]
        elif "information_schema.schema_privileges" in sql:
            role = params[0]
            rows = []
            for schema, privs in self.schema_privs.get(role, {}).items():
                for p in privs:
                    rows.append((schema, p))
            self.result = rows
        else:
            self.result = []

    def fetchone(self):
        return self.result[0] if self.result else None

    def fetchall(self):
        return self.result


class DummyConn:
    def __init__(self, db_privs, schema_privs):
        self.db_privs = db_privs
        self.schema_privs = schema_privs

    def cursor(self):
        return DummyCursor(self.db_privs, self.schema_privs)

    def get_dsn_parameters(self):
        return {"dbname": "testdb"}


class DBManagerPrivilegeReadTests(unittest.TestCase):
    def setUp(self):
        db_privs = {"role1": {"CONNECT", "TEMP"}}
        schema_privs = {"role1": {"public": {"USAGE"}}}
        self.dbm = DBManager(DummyConn(db_privs, schema_privs))

    def test_get_database_privileges(self):
        self.assertEqual(self.dbm.get_database_privileges("role1"), {"CONNECT", "TEMP"})

    def test_get_schema_privileges(self):
        expected = {"public": {"USAGE"}}
        self.assertEqual(self.dbm.get_schema_privileges("role1"), expected)


if __name__ == "__main__":
    unittest.main()
