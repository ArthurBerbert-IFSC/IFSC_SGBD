import logging
import unittest
from contextlib import contextmanager

from gerenciador_postgres.role_manager import RoleManager
from config.permission_templates import PERMISSION_TEMPLATES


class DummyDAO:
    def __init__(self):
        self.conn = DummyConn()
        self.applied = None
        self.default_privs = []

    def list_tables_by_schema(self, **kwargs):
        return {"public": ["t1", "t2"]}

    def apply_group_privileges(self, group, privileges, obj_type="TABLE", check_dependencies=True):
        self.applied = (group, privileges, obj_type)

    def grant_database_privileges(self, group, privileges):
        self.db_privs = (group, privileges)

    def grant_schema_privileges(self, group, schema, privileges):
        self.schema_privs = (group, schema, privileges)

    def alter_default_privileges(self, group, schema, obj_type, privileges):
        self.default_privs.append((group, schema, obj_type, privileges))

    @contextmanager
    def transaction(self):
        try:
            yield
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise


class DummyConn:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def get_dsn_parameters(self):
        return {"dbname": "testdb"}


class RoleManagerTemplateTests(unittest.TestCase):
    def setUp(self):
        self.dao = DummyDAO()
        logger = logging.getLogger("test")
        self.rm = RoleManager(self.dao, logger)

    def test_apply_template_to_group(self):
        template = next(iter(PERMISSION_TEMPLATES))
        perms = set(PERMISSION_TEMPLATES[template]["tables"]["*"])
        result = self.rm.apply_template_to_group("grp_demo", template)
        self.assertTrue(result)
        group, privileges, obj_type = self.dao.applied
        expected = {"public": {"t1": perms, "t2": perms}}
        self.assertEqual(group, "grp_demo")
        self.assertEqual(privileges, expected)
        self.assertEqual(obj_type, "TABLE")
        # Default privileges
        fut = PERMISSION_TEMPLATES[template]["future"]["public"]["tables"]
        self.assertIn(("grp_demo", "public", "tables", set(fut)), self.dao.default_privs)
        self.assertTrue(self.dao.conn.committed)


if __name__ == "__main__":
    unittest.main()

