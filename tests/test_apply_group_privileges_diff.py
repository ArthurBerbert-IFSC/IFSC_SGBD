import unittest
from gerenciador_postgres.db_manager import DBManager


class DummyCursor:
    def __init__(self, current_privs, record=False):
        self.current_privs = current_privs
        self.record = record
        self.executed = []
        self.result = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def execute(self, sql_query, params=None):
        query = str(sql_query)
        if "information_schema.role_table_grants" in query:
            self.result = [
                (schema, table, priv)
                for schema, objs in self.current_privs.items()
                for table, privs in objs.items()
                for priv in privs
            ]
        elif self.record and ("GRANT" in query or "REVOKE" in query):
            self.executed.append(query)

    def fetchall(self):
        return self.result


class DummyConn:
    def __init__(self, current_privs):
        self.current_privs = current_privs
        self.calls = 0
        self.last_cursor = None
        self.cursors = []

    def cursor(self):
        self.calls += 1
        record = self.calls > 1
        cur = DummyCursor(self.current_privs, record)
        self.last_cursor = cur
        self.cursors.append(cur)
        return cur


class ApplyGroupPrivilegesDiffTests(unittest.TestCase):
    def test_grant_only(self):
        conn = DummyConn({})
        dbm = DBManager(conn)
        dbm.apply_group_privileges("grp", {"public": {"t1": {"SELECT"}}})
        commands = []
        for c in conn.cursors:
            commands.extend(c.executed)
        self.assertEqual(len(commands), 1)
        self.assertIn("GRANT", commands[0])
        self.assertNotIn("REVOKE", commands[0])

    def test_revoke_only(self):
        conn = DummyConn({"public": {"t1": {"SELECT"}}})
        dbm = DBManager(conn)
        dbm.apply_group_privileges("grp", {"public": {"t1": set()}})
        commands = []
        for c in conn.cursors:
            commands.extend(c.executed)
        self.assertEqual(len(commands), 1)
        self.assertIn("REVOKE", commands[0])
        self.assertNotIn("GRANT", commands[0])

    def test_no_change(self):
        conn = DummyConn({"public": {"t1": {"SELECT"}}})
        dbm = DBManager(conn)
        dbm.apply_group_privileges("grp", {"public": {"t1": {"SELECT"}}})
        commands = []
        for c in conn.cursors:
            commands.extend(c.executed)
        self.assertEqual(commands, [])


if __name__ == "__main__":
    unittest.main()
