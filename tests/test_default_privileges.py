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
        sql_str = str(sql)
        if "SHOW server_version_num" in sql_str:
            self.result = [(str(self.conn.version),)]
        else:
            self.result = self.conn.rows
    def fetchall(self):
        return self.result
    def fetchone(self):
        return self.result[0]


class DummyConn:
    def __init__(self, version, rows):
        self.version = version
        self.rows = rows
    def cursor(self):
        return DummyCursor(self)
    def commit(self):
        pass
    def rollback(self):
        pass


def test_get_default_privileges_pg12():
    rows = [
        ("geo2", "postgres", "grp_Geo2_2025-2", ["DELETE", "INSERT", "SELECT", "UPDATE"]),
        ("public", "postgres", "grp_Geo2_2025-2", ["SELECT"]),
        ("Teste_001_Esquema", "postgres", "grp_Geo2_2025-2", ["INSERT", "SELECT", "UPDATE"]),
    ]
    conn = DummyConn(150000, rows)
    db = DBManager(conn)
    res = db.get_default_privileges("grp_Geo2_2025-2")
    assert res["geo2"]["grp_Geo2_2025-2"] == {"DELETE", "INSERT", "SELECT", "UPDATE"}
    assert res["public"]["grp_Geo2_2025-2"] == {"SELECT"}
    assert res["Teste_001_Esquema"]["grp_Geo2_2025-2"] == {"INSERT", "SELECT", "UPDATE"}
    assert res["_meta"]["owner_roles"]["geo2"] == "postgres"


def test_get_default_privileges_fallback():
    rows = [
        ("geo2", "postgres", "grp_Geo2_2025-2", ["a", "r", "w", "d"]),
        ("public", "postgres", "grp_Geo2_2025-2", ["r"]),
    ]
    conn = DummyConn(110000, rows)
    db = DBManager(conn)
    res = db.get_default_privileges("grp_Geo2_2025-2")
    assert res["geo2"]["grp_Geo2_2025-2"] == {"INSERT", "SELECT", "UPDATE", "DELETE"}
    assert res["public"]["grp_Geo2_2025-2"] == {"SELECT"}
