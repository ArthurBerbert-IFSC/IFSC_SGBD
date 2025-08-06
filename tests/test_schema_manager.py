import logging
import unittest
import sys
import pathlib

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

            def execute(self_inner, *args, **kwargs):
                pass

            def fetchone(self_inner):
                return (None,)

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


class DummySchemaManager(SchemaManager):
    def __init__(self, dao, logger, perms):
        super().__init__(dao, logger)
        self._user = perms.get('user', 'alice')
        self._is_super = perms.get('super', False)
        self._in_prof = perms.get('professor', False)
        self._owner = perms.get('owner', None)

    def _current_user(self):
        return self._user

    def _has_role(self, username, role):
        return self._in_prof if role == 'Professores' else False

    def _is_superuser(self, username):
        return self._is_super

    def _get_schema_owner(self, schema):
        return self._owner


class TestSchemaManagerPermissions(unittest.TestCase):
    def setUp(self):
        logger = logging.getLogger('test')
        logger.addHandler(logging.NullHandler())
        self.dao = DummyDAO()
        self.logger = logger

    def test_create_schema_authorized(self):
        mgr = DummySchemaManager(self.dao, self.logger, {'professor': True})
        mgr.create_schema('novo')
        self.assertEqual(self.dao.created, [('novo', None)])
        self.assertTrue(self.dao.conn.committed)

    def test_create_schema_unauthorized(self):
        mgr = DummySchemaManager(self.dao, self.logger, {'professor': False})
        with self.assertRaises(PermissionError):
            mgr.create_schema('novo')
        self.assertEqual(self.dao.created, [])
        self.assertFalse(self.dao.conn.committed)
        self.assertFalse(self.dao.conn.rolled_back)  # Permission check occurs before transaction

    def test_delete_schema_authorized_owner(self):
        perms = {'owner': 'alice'}
        mgr = DummySchemaManager(self.dao, self.logger, perms)
        mgr.delete_schema('teste')
        self.assertEqual(self.dao.dropped, [('teste', False)])
        self.assertTrue(self.dao.conn.committed)

    def test_delete_schema_unauthorized(self):
        perms = {'owner': 'other'}
        mgr = DummySchemaManager(self.dao, self.logger, perms)
        with self.assertRaises(PermissionError):
            mgr.delete_schema('teste')
        self.assertEqual(self.dao.dropped, [])
        self.assertFalse(self.dao.conn.committed)
        self.assertFalse(self.dao.conn.rolled_back)

