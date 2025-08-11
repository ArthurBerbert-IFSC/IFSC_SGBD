"""Tests for dynamic profile reassignment in PrivilegePolicyService."""

import unittest
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from app.services.privilege_policy import PrivilegePolicyService

class DummyCursor:
    def __init__(self, store):
        self.store = store
    def execute(self, sql, params=None):
        self.store.append(sql)
    def close(self):
        pass
    def fetchone(self):
        return None

class DummyConn:
    def __init__(self):
        self.queries = []
    def cursor(self):
        return DummyCursor(self.queries)
    def commit(self):
        pass
    def rollback(self):
        pass

class PrivilegePolicyTests(unittest.TestCase):
    def test_set_user_profile_grants_and_revokes(self):
        svc = PrivilegePolicyService(DummyConn())
        svc.set_user_profile("geo", "alice", "AUTOR")
        expected = [
            'REVOKE "geo_leitor" FROM "alice"',
            'REVOKE "geo_autor" FROM "alice"',
            'REVOKE "geo_colab" FROM "alice"',
            'REVOKE "geo_gestor" FROM "alice"',
            'GRANT "geo_leitor" TO "alice"',
            'GRANT "geo_autor"  TO "alice"',
        ]
        self.assertEqual(svc.conn.queries, expected)

if __name__ == '__main__':
    unittest.main()
