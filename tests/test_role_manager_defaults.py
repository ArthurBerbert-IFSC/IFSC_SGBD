import logging
import unittest
from contextlib import contextmanager

from gerenciador_postgres.role_manager import RoleManager


class DummyDAO:
    def __init__(self):
        self.conn = DummyConn()
        self.default_privs = []

    def apply_group_privileges(self, group, privileges, obj_type="TABLE", check_dependencies=True):
        pass

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
    def commit(self):
        pass

    def rollback(self):
        pass

    def get_dsn_parameters(self):
        return {"dbname": "testdb"}


class RoleManagerDefaultsTests(unittest.TestCase):
    def setUp(self):
        self.dao = DummyDAO()
        logger = logging.getLogger("test")
        self.rm = RoleManager(self.dao, logger)

    def test_skip_union_when_defaults_applied(self):
        self.rm.set_group_privileges(
            "grp",
            {"public": {"__FUTURE__": {"SELECT"}}},
        )
        initial = len(self.dao.default_privs)
        self.rm.set_group_privileges(
            "grp",
            {"public": {"t1": {"SELECT"}}},
            defaults_applied=True,
        )
        self.assertEqual(len(self.dao.default_privs), initial)


if __name__ == "__main__":
    unittest.main()
