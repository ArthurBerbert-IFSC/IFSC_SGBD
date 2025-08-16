import unittest
import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from gerenciador_postgres.db_manager import DBManager


class DummyCursor:
    def __init__(self, conn):
        self.conn = conn
        self.commands = []
        self.result = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def execute(self, sql_query, params=None):
        from psycopg2 import sql as _sql

        def _to_str(obj):
            if isinstance(obj, _sql.Composed):
                return ''.join(_to_str(p) for p in obj._wrapped)
            if isinstance(obj, _sql.SQL):
                return obj._wrapped
            if isinstance(obj, _sql.Identifier):
                return ''.join(obj._wrapped)
            return str(obj)

        query = _to_str(sql_query)
        self.commands.append(query)
        if "FROM pg_namespace" in query:
            role, schema = params
            privs = self.conn.grants.get((role, schema), set())
            self.result = [(p.rstrip("*"), p.endswith("*")) for p in sorted(privs)]
        elif query.strip().upper().startswith("GRANT"):
            import re

            m = re.search(r"GRANT (.+) ON SCHEMA (.+) TO (.+)", query, re.IGNORECASE)
            if m:
                privs = {p.strip() for p in m.group(1).split(",")}
                schema = m.group(2).strip('"')
                role = m.group(3).strip('"')
                self.conn.grants.setdefault((role, schema), set()).update(privs)
        elif query.strip().upper().startswith("REVOKE"):
            import re

            m = re.search(r"REVOKE (.+) ON SCHEMA (.+) FROM (.+)", query, re.IGNORECASE)
            if m:
                privs_str = m.group(1)
                schema = m.group(2).strip('"')
                role = m.group(3).strip('"')
                current = self.conn.grants.setdefault((role, schema), set())
                if privs_str.upper() == "ALL PRIVILEGES":
                    current.clear()
                else:
                    privs = {p.strip() for p in privs_str.split(",")}
                    current.difference_update(privs)
        else:
            self.result = []

    def fetchall(self):
        return self.result


class DummyConn:
    def __init__(self, grants=None):
        self.grants = grants or {}
        self.autocommit = True
        self.last_cursor = None

    def cursor(self):
        self.last_cursor = DummyCursor(self)
        return self.last_cursor


class GrantSchemaPrivilegesDiffTests(unittest.TestCase):
    def test_idempotent_and_preserves_other_privileges(self):
        grants = {("grp", "public"): {"USAGE", "OTHER"}}
        conn = DummyConn(grants)
        dbm = DBManager(conn)
        dbm.grant_schema_privileges("grp", "public", {"USAGE"})
        commands = conn.last_cursor.commands
        self.assertEqual(len(commands), 1)  # Apenas SELECT executado
        self.assertEqual(conn.grants[("grp", "public")], {"USAGE", "OTHER"})

    def test_revoke_only_difference(self):
        grants = {("grp", "public"): {"USAGE", "CREATE", "OTHER"}}
        conn = DummyConn(grants)
        dbm = DBManager(conn)
        dbm.grant_schema_privileges("grp", "public", {"USAGE"})
        commands = conn.last_cursor.commands
        # Deve executar SELECT e REVOKE, preservando privilégio OTHER
        self.assertEqual(len(commands), 2)
        self.assertEqual(conn.grants[("grp", "public")], {"USAGE", "OTHER"})


if __name__ == "__main__":
    unittest.main()
