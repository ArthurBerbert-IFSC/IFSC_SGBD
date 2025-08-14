import pytest
import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from gerenciador_postgres.db_manager import DBManager


class DummyCursor:
    def __init__(self):
        # Include a malformed row with only one column to simulate unexpected
        # database adapter behaviour.
        self.result = [("public", "USAGE"), ("broken",)]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def execute(self, sql, params=None):
        pass

    def fetchall(self):
        return self.result


class DummyConn:
    def cursor(self):
        return DummyCursor()


def test_get_schema_privileges_handles_short_rows():
    dbm = DBManager(DummyConn())
    privs = dbm.get_schema_privileges("grp")
    assert privs == {"public": {"USAGE"}}
