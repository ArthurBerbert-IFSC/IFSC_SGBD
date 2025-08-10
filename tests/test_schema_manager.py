
import logging
import pathlib
import sys
import unittest
from contextlib import contextmanager

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from gerenciador_postgres.schema_manager import SchemaManager


class DummyConn:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    # Context manager cursor for tests; not used because methods are overridden
    def cursor(self):
        class DummyCursor:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, exc_type, exc, tb):
                pass

            def execute(self_inner, sql, params=None):
                if "pg_has_role" in sql:
                    self_inner._result = [(True,)]
                else:
                    self_inner._result = [(None,)]

            def fetchone(self_inner):
                return self_inner._result[0]

        return DummyCursor()


class DummyDAO:
    def __init__(self):
        self.conn = DummyConn()
        self.created = []
        self.dropped = []

    def create_schema(self, name, owner=None):
        self.created.append((name, owner))

    def drop_schema(self, name, cascade=False):
        self.dropped.append((name, cascade))

    def alter_schema_owner(self, name, owner):
        pass

    def list_schemas(self):
        return []

    @contextmanager
    def transaction(self):
        try:
            yield
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise


class TestableSchemaManager(SchemaManager):
    def __init__(self, dao, logger, perms, allowed_group='Professores'):
        super().__init__(dao, logger)
        self.allowed_group = allowed_group
        self._user = perms.get('user', 'alice')
        self._is_super = perms.get('super', False)
        self._in_group = perms.get('in_group', False)
        self._owner = perms.get('owner', None)

    def _current_user(self):
        return self._user

    def _has_role(self, username, role):
        return self._in_group if role == self.allowed_group else False

    def _is_superuser(self, username):
        return self._is_super

    def _get_schema_owner(self, schema):
        return self._owner


class SchemaManagerPermissionTests(unittest.TestCase):
    def setUp(self):
        logger = logging.getLogger('test')
        logger.addHandler(logging.NullHandler())
        self.dao = DummyDAO()
        self.logger = logger

    def test_create_schema_authorized(self):
        mgr = TestableSchemaManager(self.dao, self.logger, {'in_group': True})
        mgr.create_schema('novo')
        self.assertEqual(self.dao.created, [('novo', None)])
        self.assertTrue(self.dao.conn.committed)

    def test_create_schema_unauthorized(self):
        mgr = TestableSchemaManager(self.dao, self.logger, {'in_group': False})
        with self.assertRaises(PermissionError):
            mgr.create_schema('novo')
        self.assertEqual(self.dao.created, [])
        self.assertFalse(self.dao.conn.committed)
        self.assertFalse(self.dao.conn.rolled_back)  # Permission check occurs before transaction

    def test_delete_schema_authorized_owner(self):
        perms = {'owner': 'alice'}
        mgr = TestableSchemaManager(self.dao, self.logger, perms)
        mgr.delete_schema('teste')
        self.assertEqual(self.dao.dropped, [('teste', False)])
        self.assertTrue(self.dao.conn.committed)

    def test_delete_schema_unauthorized(self):
        perms = {'owner': 'other'}
        mgr = TestableSchemaManager(self.dao, self.logger, perms)
        with self.assertRaises(PermissionError):
            mgr.delete_schema('teste')
        self.assertEqual(self.dao.dropped, [])
        self.assertFalse(self.dao.conn.committed)
        self.assertFalse(self.dao.conn.rolled_back)


if __name__ == '__main__':
    unittest.main()