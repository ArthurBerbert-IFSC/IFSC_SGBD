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

    def test_create_group_respects_prefix(self):
        with patch("gerenciador_postgres.role_manager.load_config", return_value={"group_prefix": "turma_"}):
            created = self.rm.create_group("turma_valid")
            self.assertEqual(created, "turma_valid")
            self.assertIn("turma_valid", self.dao.groups)

    def test_create_group_invalid_prefix(self):
        with patch("gerenciador_postgres.role_manager.load_config", return_value={"group_prefix": "class_"}):
            with self.assertRaises(ValueError):
                self.rm.create_group("turma_invalid")


if __name__ == "__main__":
    unittest.main()

