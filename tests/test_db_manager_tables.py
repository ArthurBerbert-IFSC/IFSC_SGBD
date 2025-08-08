import unittest
import pathlib
import sys
import unittest
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from gerenciador_postgres.db_manager import DBManager


class DummyCursor:
    def __init__(self, data):
        self.data = data
        self.result = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def execute(self, sql, params=None):
        if "information_schema.schemata" in sql:
            self.result = [(s,) for s in self.data["schemas"]]
        elif "FROM pg_catalog.pg_class" in sql:
            self.result = self.data["tables"]
        else:
            self.result = []

    def fetchall(self):
        return self.result


class DummyConn:
    def __init__(self, data):
        self.data = data

    def cursor(self):
        return DummyCursor(self.data)


class DBManagerTableTests(unittest.TestCase):
    def setUp(self):
        data = {
            "schemas": ["public", "empty_schema"],
            "tables": [("public", "t1"), ("public", "t2")],
        }
        self.dbm = DBManager(DummyConn(data))

    def test_list_tables_by_schema_includes_empty(self):
        expected = {"public": ["t1", "t2"], "empty_schema": []}
        self.assertEqual(self.dbm.list_tables_by_schema(), expected)


if __name__ == "__main__":
    unittest.main()
