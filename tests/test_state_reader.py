import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from gerenciador_postgres import state_reader


class DummyCursor:
    def __init__(self):
        self.result = [("public", "USAGE"), ("broken",), None]
        self.fetchone_values = [(True,), (False,), (False,), (False,)]
        self.idx = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def execute(self, sql, params=None):
        pass

    def fetchall(self):
        return self.result

    def fetchone(self):
        val = self.fetchone_values[self.idx]
        self.idx += 1
        return val


class DummyConn:
    def cursor(self):
        return DummyCursor()


def test_get_schema_privileges_handles_short_rows():
    conn = DummyConn()
    privs = state_reader.get_schema_privileges(conn, "grp")
    assert privs == {"public": {"USAGE"}}


class DummyCursorDeps:
    def __init__(self):
        self.executed = []
        self.result = [
            ("public", "view1"),
            ("other", "view2"),
            ("broken",),
            None,
        ]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return self.result


class DummyConnDeps:
    def __init__(self):
        self.cursors = []

    def cursor(self):
        cur = DummyCursorDeps()
        self.cursors.append(cur)
        return cur


def test_get_dependencies_filters_rows():
    conn = DummyConnDeps()
    deps = state_reader.get_dependencies(conn, "public", "tbl")
    assert deps == [("public", "view1"), ("other", "view2")]
    cur = conn.cursors[0]
    assert cur.executed[0][1] == ("public", "tbl")


class DummyCursorDefaults:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def execute(self, sql, params=None):
        self._sql = sql

    def fetchall(self):
        return self.rows


class DummyConnDefaults:
    def __init__(self, rows):
        self.rows = rows

    def cursor(self):
        return DummyCursorDefaults(self.rows)


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
    conn = DummyConnDefaults(rows)
    res = state_reader.get_default_privileges(conn, owner="postgres")
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


class DummyCursorRoles:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def execute(self, sql, params=None):
        pass

    def fetchall(self):
        return [("turma_teste",), ("monitores_abc",), ("outro",)]


class DummyConnRoles:
    def cursor(self):
        return DummyCursorRoles()


def test_list_roles_filters_managed():
    conn = DummyConnRoles()
    roles = state_reader.list_roles(conn)
    assert roles == ["turma_teste", "monitores_abc"]
