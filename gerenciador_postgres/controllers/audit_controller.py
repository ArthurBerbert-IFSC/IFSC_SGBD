from PyQt6.QtCore import QObject, pyqtSignal
from ..audit_manager import AuditManager
from typing import Dict, List, Optional
from datetime import datetime


class AuditController(QObject):
    """Controller para gerenciar operações de auditoria."""
    
    data_changed = pyqtSignal()
    
    def __init__(self, audit_manager: AuditManager, logger):
        super().__init__()
        self.audit_manager = audit_manager
        self.logger = logger
    
    def get_audit_logs(self, 
                      limit: int = 100,
                      offset: int = 0,
                      operador: Optional[str] = None,
                      operacao: Optional[str] = None,
                      objeto_tipo: Optional[str] = None,
                      data_inicio: Optional[datetime] = None,
                      data_fim: Optional[datetime] = None) -> List[Dict]:
        """Obtém logs de auditoria com filtros."""
        try:
            return self.audit_manager.get_audit_logs(
                limit=limit,
                offset=offset,
                operador=operador,
                operacao=operacao,
                objeto_tipo=objeto_tipo,
                data_inicio=data_inicio,
                data_fim=data_fim
            )
        except Exception as e:
            self.logger.error(f"Erro ao obter logs de auditoria: {e}")
            raise
    
    def get_audit_stats(self) -> Dict:
        """Obtém estatísticas de auditoria."""
        try:
            return self.audit_manager.get_audit_stats()
        except Exception as e:
            self.logger.error(f"Erro ao obter estatísticas de auditoria: {e}")
            raise
    
    def cleanup_old_logs(self, days_to_keep: int = 90) -> int:
        """Remove logs antigos."""
        try:
            deleted_count = self.audit_manager.cleanup_old_logs(days_to_keep)
            self.data_changed.emit()
            return deleted_count
        except Exception as e:
            self.logger.error(f"Erro na limpeza de logs: {e}")
            raise
    
    def log_operation(self, 
                     operador: str,
                     operacao: str,
                     objeto_tipo: str,
                     objeto_nome: str,
                     detalhes: Optional[Dict] = None,
                     dados_antes: Optional[Dict] = None,
                     dados_depois: Optional[Dict] = None,
                     sucesso: bool = True,
                     ip_address: Optional[str] = None):
        """Registra uma operação na auditoria."""
        try:
            self.audit_manager.log_operation(
                operador=operador,
                operacao=operacao,
                objeto_tipo=objeto_tipo,
                objeto_nome=objeto_nome,
                detalhes=detalhes,
                dados_antes=dados_antes,
                dados_depois=dados_depois,
                sucesso=sucesso,
                ip_address=ip_address
            )
            self.data_changed.emit()
        except Exception as e:
            self.logger.error(f"Erro ao registrar operação de auditoria: {e}")
            # Não propagar erro de auditoria
