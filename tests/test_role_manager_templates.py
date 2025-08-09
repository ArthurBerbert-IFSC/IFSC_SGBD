import logging
import unittest
from contextlib import contextmanager

from gerenciador_postgres.role_manager import RoleManager
from config.permission_templates import PERMISSION_TEMPLATES


class DummyDAO:
    def __init__(self):
        self.conn = DummyConn()
        self.applied = None

    def list_tables_by_schema(self):
        return {"public": ["t1", "t2"]}

    def apply_group_privileges(self, group, privileges):
        self.applied = (group, privileges)

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


class RoleManagerTemplateTests(unittest.TestCase):
    def setUp(self):
        self.dao = DummyDAO()
        logger = logging.getLogger("test")
        self.rm = RoleManager(self.dao, logger)

    def test_apply_template_to_group(self):
        template = next(iter(PERMISSION_TEMPLATES))
        perms = PERMISSION_TEMPLATES[template]
        result = self.rm.apply_template_to_group("grp_demo", template)
        self.assertTrue(result)
        group, privileges = self.dao.applied
        expected = {"public": {"t1": set(perms), "t2": set(perms)}}
        self.assertEqual(group, "grp_demo")
        self.assertEqual(privileges, expected)
        self.assertTrue(self.dao.conn.committed)


if __name__ == "__main__":
    unittest.main()

