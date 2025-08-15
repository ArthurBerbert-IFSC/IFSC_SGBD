import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from gerenciador_postgres.db_manager import DBManager


class DummyCursor:
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


class DummyConn:
    def __init__(self):
        self.cursors = []

    def cursor(self):
        cur = DummyCursor()
        self.cursors.append(cur)
        return cur


def test_get_object_dependencies_filters_rows():
    conn = DummyConn()
    dbm = DBManager(conn)
    deps = dbm.get_object_dependencies("public", "tbl")
    assert deps == [("public", "view1"), ("other", "view2")]
    cur = conn.cursors[0]
    assert cur.executed[0][1] == ("public", "tbl")
