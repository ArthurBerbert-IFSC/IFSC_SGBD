import logging
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from gerenciador_postgres.role_manager import RoleManager


class DummyDAO:
    def __init__(self):
        self.conn = DummyConn()
        self.groups = set()

    def list_groups(self):
        return list(self.groups)

    def create_group(self, name):
        self.groups.add(name)

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


class RoleManagerGroupPrefixTests(unittest.TestCase):
    def setUp(self):
        self.dao = DummyDAO()
        self.rm = RoleManager(self.dao, logging.getLogger("test"))

    def test_create_group_auto_prefix(self):
        # Se usuário não passa prefixo, ele deve ser adicionado
        with patch("gerenciador_postgres.role_manager.load_config", return_value={"group_prefix": "grp_"}):
            created = self.rm.create_group("analise_dados")
            self.assertTrue(created.startswith("grp_"))
            self.assertIn(created, self.dao.groups)

    def test_create_group_keeps_prefix(self):
        with patch("gerenciador_postgres.role_manager.load_config", return_value={"group_prefix": "grp_"}):
            created = self.rm.create_group("grp_ciencias")
            self.assertEqual(created, "grp_ciencias")
            self.assertIn("grp_ciencias", self.dao.groups)


if __name__ == "__main__":
    unittest.main()

