import unittest
import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from gerenciador_postgres.db_manager import DBManager


class DummyCursor:
    def __init__(self, roles):
        self.roles = roles
        self.result = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def execute(self, sql, params=None):
        if "SELECT 1 FROM pg_roles" in sql:
            owner = params[0]
            self.result = [(1,)] if owner in self.roles else []
        elif "SELECT rolname FROM pg_roles" in sql:
            self.result = [(r,) for r in self.roles]
        else:
            self.result = []

    def fetchone(self):
        return self.result[0] if self.result else None

    def fetchall(self):
        return self.result


class DummyConn:
    def __init__(self, roles):
        self.roles = roles

    def cursor(self):
        return DummyCursor(self.roles)


class DBManagerSchemaTests(unittest.TestCase):
    def setUp(self):
        self.conn = DummyConn(["postgres", "Arthur"])
        self.dbm = DBManager(self.conn)

    def test_create_schema_owner_exists(self):
        # Deve executar sem levantar exceção
        self.dbm.create_schema("Lixo", "Arthur")

    def test_create_schema_owner_missing(self):
        with self.assertRaises(ValueError):
            self.dbm.create_schema("Lixo", "NaoExiste")


if __name__ == "__main__":
    unittest.main()
