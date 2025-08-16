import sys
import pathlib
import pytest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from gerenciador_postgres.db_manager import DBManager


class DummyCursor:
    def __init__(self, conn):
        self.conn = conn
        self.result = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def execute(self, sql, params=None):
        self.result = self.conn.rows

    def fetchall(self):
        return self.result

    def fetchone(self):
        return self.result[0]


class DummyConn:
    def __init__(self, rows):
        self.rows = rows

    def cursor(self):
        return DummyCursor(self)

    def commit(self):
        pass

    def rollback(self):
        pass


def test_get_default_privileges_parsing():
    rows = [
        ("postgres", "geo2", "grp_Geo2_2025-2", "DELETE", False),
        ("postgres", "geo2", "grp_Geo2_2025-2", "INSERT", False),
        ("postgres", "geo2", "grp_Geo2_2025-2", "SELECT", False),
        ("postgres", "geo2", "grp_Geo2_2025-2", "UPDATE", False),
        ("postgres", "public", "grp_Geo2_2025-2", "SELECT", False),
        ("postgres", "Teste_001_Esquema", "grp_Geo2_2025-2", "INSERT", False),
        ("postgres", "Teste_001_Esquema", "grp_Geo2_2025-2", "SELECT", False),
        ("postgres", "Teste_001_Esquema", "grp_Geo2_2025-2", "UPDATE", False),
    ]
    conn = DummyConn(rows)
    db = DBManager(conn)
    res = db.get_default_privileges(owner="postgres")
    assert res["geo2"]["grp_Geo2_2025-2"] == {
        "DELETE",
        "INSERT",
        "SELECT",
        "UPDATE",
    }
    assert res["public"]["grp_Geo2_2025-2"] == {"SELECT"}
    assert res["Teste_001_Esquema"]["grp_Geo2_2025-2"] == {
        "INSERT",
        "SELECT",
        "UPDATE",
    }
    assert res["_meta"]["owner_roles"]["geo2"] == "postgres"

