import unittest
import sys
import os
from unittest.mock import MagicMock, patch
from pathlib import Path

# Adicionar o diretório do projeto ao path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gerenciador_postgres.audit_manager import AuditManager
from gerenciador_postgres.db_manager import DBManager


class MockCursor:
    def __init__(self):
        self.executed_queries = []
        self.rowcount = 5
        self._result = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def execute(self, query, params=None):
        self.executed_queries.append((query, params))
        if "SUM(CASE WHEN success" in query:
            self._result = [(100, 80)]
        else:
            self._result = []

    def fetchone(self):
        return self._result[0] if self._result else None

    def fetchall(self):
        return self._result


class MockConnection:
    def __init__(self):
        self.cursor_mock = MockCursor()
        self.committed = False
        self.rolled_back = False
    
    def cursor(self):
        return self.cursor_mock
    
    def commit(self):
        self.committed = True
    
    def rollback(self):
        self.rolled_back = True


class TestAuditManager(unittest.TestCase):
    def setUp(self):
        self.mock_conn = MockConnection()
        self.db_manager = DBManager(self.mock_conn)

        self.mock_logger = MagicMock()

        # Patch para evitar criação real da tabela
        with patch.object(AuditManager, '_ensure_audit_table'):
            self.audit_manager = AuditManager(self.db_manager, self.mock_logger)

    def test_log_operation_success(self):
        """Registra operação bem-sucedida."""
        with self.db_manager.transaction():
            self.audit_manager.log_operation(
                actor="arthur",
                database_name="db",
                schema_name="public",
                contract_json={"a": 1},
                diff_sql="GRANT",
                success=True,
            )
            # commit ainda não executado dentro do bloco
            self.assertFalse(self.mock_conn.committed)

        query, params = self.mock_conn.cursor_mock.executed_queries[0]
        self.assertIn("INSERT INTO auditoria_permissoes", query)
        self.assertEqual(params[3].adapted, {"a": 1})
        self.assertEqual(params[4], "GRANT")
        self.assertTrue(params[5])
        self.assertIsNone(params[6])
        # commit realizado após saída do contexto
        self.assertTrue(self.mock_conn.committed)

    def test_log_operation_failure(self):
        """Registra operação com falha."""
        with self.db_manager.transaction():
            self.audit_manager.log_operation(
                actor="arthur",
                database_name="db",
                schema_name="public",
                contract_json={"a": 1},
                diff_sql="GRANT",
                success=False,
                error_message="boom",
            )
            self.assertFalse(self.mock_conn.committed)

        query, params = self.mock_conn.cursor_mock.executed_queries[0]
        self.assertIn("INSERT INTO auditoria_permissoes", query)
        self.assertEqual(params[3].adapted, {"a": 1})
        self.assertEqual(params[4], "GRANT")
        self.assertFalse(params[5])  # success flag
        self.assertEqual(params[6], "boom")
        self.assertTrue(self.mock_conn.committed)

    def test_log_operation_rollback(self):
        """Garante rollback se a transação falhar após a auditoria."""
        with self.assertRaises(ValueError):
            with self.db_manager.transaction():
                self.audit_manager.log_operation(
                    actor="arthur",
                    database_name="db",
                    schema_name="public",
                    contract_json={"a": 1},
                    diff_sql="GRANT",
                    success=True,
                )
                raise ValueError("fail")

        self.assertTrue(self.mock_conn.rolled_back)
        self.assertFalse(self.mock_conn.committed)

    def test_cleanup_old_logs(self):
        """Testa a remoção de logs antigos."""
        deleted = self.audit_manager.cleanup_old_logs(90)
        self.assertEqual(deleted, 5)
        self.assertTrue(self.mock_conn.committed)


if __name__ == '__main__':
    unittest.main()
