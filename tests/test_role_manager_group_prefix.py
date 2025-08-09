import logging
import unittest
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


class DummyConn:
    def commit(self):
        pass

    def rollback(self):
        pass


class RoleManagerGroupPrefixTests(unittest.TestCase):
    def setUp(self):
        self.dao = DummyDAO()
        self.rm = RoleManager(self.dao, logging.getLogger("test"))

    def test_create_group_respects_prefix(self):
        with patch("gerenciador_postgres.role_manager.load_config", return_value={"group_prefix": "grp_"}):
            created = self.rm.create_group("grp_valid")
            self.assertEqual(created, "grp_valid")
            self.assertIn("grp_valid", self.dao.groups)

    def test_create_group_invalid_prefix(self):
        with patch("gerenciador_postgres.role_manager.load_config", return_value={"group_prefix": "class_"}):
            with self.assertRaises(ValueError):
                self.rm.create_group("grp_invalid")


if __name__ == "__main__":
    unittest.main()

