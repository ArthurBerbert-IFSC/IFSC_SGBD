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
        if "COUNT(*)" in query:
            self._result = [(100,)]
        elif "GROUP BY operacao" in query:
            self._result = [("CREATE_USER", 10), ("DELETE_USER", 5)]
        elif "GROUP BY operador" in query:
            self._result = [("arthur", 20), ("maria", 15)]
        elif "INTERVAL '24 hours'" in query:
            self._result = [(25,)]
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
        self.mock_db_manager = MagicMock(spec=DBManager)
        self.mock_db_manager.conn = self.mock_conn
        
        self.mock_logger = MagicMock()
        
        # Patch para evitar criação real da tabela
        with patch.object(AuditManager, '_ensure_audit_table'):
            self.audit_manager = AuditManager(self.mock_db_manager, self.mock_logger)
    
    def test_log_operation_success(self):
        """Testa o registro de uma operação bem-sucedida."""
        self.audit_manager.log_operation(
            operador='arthur',
            operacao='CREATE_USER',
            objeto_tipo='USER',
            objeto_nome='joao',
            detalhes={'password_set': True},
            sucesso=True
        )
        
        # Verificar se a query foi executada
        queries = self.mock_conn.cursor_mock.executed_queries
        self.assertTrue(len(queries) > 0)
        
        # Verificar se commit foi chamado
        self.assertTrue(self.mock_conn.committed)
    
    def test_get_audit_stats(self):
        """Testa a obtenção de estatísticas de auditoria."""
        stats = self.audit_manager.get_audit_stats()
        
        expected_stats = {
            'total_registros': 100,
            'operacoes_por_tipo': {"CREATE_USER": 10, "DELETE_USER": 5},
            'atividade_operadores': {"arthur": 20, "maria": 15},
            'atividade_24h': 25
        }
        
        self.assertEqual(stats, expected_stats)
    
    def test_cleanup_old_logs(self):
        """Testa a limpeza de logs antigos."""
        deleted_count = self.audit_manager.cleanup_old_logs(90)
        
        # Verificar se retornou o número correto de linhas deletadas
        self.assertEqual(deleted_count, 5)  # rowcount do mock
        
        # Verificar se commit foi chamado
        self.assertTrue(self.mock_conn.committed)


if __name__ == '__main__':
    unittest.main()
