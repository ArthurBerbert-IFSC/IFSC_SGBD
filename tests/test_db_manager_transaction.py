import pathlib
import sys
import unittest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from gerenciador_postgres.db_manager import DBManager


class DummyConn:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        class DummyCursor:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, exc_type, exc, tb):
                pass

            def execute(self_inner, sql, params=None):
                pass

        return DummyCursor()

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class DBManagerTransactionTests(unittest.TestCase):
    def setUp(self):
        self.conn = DummyConn()
        self.dbm = DBManager(self.conn)

    def test_commit_on_success(self):
        with self.dbm.transaction():
            pass
        self.assertTrue(self.conn.committed)
        self.assertFalse(self.conn.rolled_back)

    def test_rollback_on_exception(self):
        with self.assertRaises(ValueError):
            with self.dbm.transaction():
                raise ValueError("fail")
        self.assertFalse(self.conn.committed)
        self.assertTrue(self.conn.rolled_back)


if __name__ == '__main__':
    unittest.main()
