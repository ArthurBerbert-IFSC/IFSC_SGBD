"""
Sistema de auditoria automática
"""
import functools
from datetime import datetime
from typing import Callable, Any, Dict, Optional
from ..core.models import AuditEntry
from ..core.logging import get_logger

logger = get_logger(__name__)

class AuditContext:
    """Contexto de auditoria com informações do usuário"""
    
    def __init__(self):
        self.current_user: Optional[str] = None
        self.session_id: Optional[str] = None
        self.client_ip: Optional[str] = None
        
    def set_user(self, username: str) -> None:
        """Define usuário atual"""
        self.current_user = username
        
    def set_session(self, session_id: str) -> None:
        """Define sessão atual"""
        self.session_id = session_id
        
    def set_client_ip(self, ip: str) -> None:
        """Define IP do cliente"""
        self.client_ip = ip
        
    def get_context_dict(self) -> Dict[str, Any]:
        """Retorna contexto como dicionário"""
        return {
            'user': self.current_user,
            'session_id': self.session_id,
            'client_ip': self.client_ip
        }

class AuditLogger:
    """Logger de auditoria"""
    
    def __init__(self, context: AuditContext):
        self.context = context
        self.entries: list[AuditEntry] = []
        
    def log_operation(self, 
                     operation: str,
                     object_type: str,
                     object_name: str,
                     success: bool,
                     details: Optional[str] = None) -> None:
        """Registra operação de auditoria"""
        
        entry = AuditEntry(
            timestamp=datetime.now(),
            user=self.context.current_user or "unknown",
            operation=operation,
            object_type=object_type,
            object_name=object_name,
            success=success,
            details=details
        )
        
        self.entries.append(entry)
        
        # Log estruturado
        logger.info(
            f"audit_operation",
            operation=operation,
            object_type=object_type,
            object_name=object_name,
            success=success,
            user=entry.user,
            details=details
        )
        
    def get_recent_entries(self, limit: int = 100) -> list[AuditEntry]:
        """Retorna entradas recentes"""
        return self.entries[-limit:]
        
    def clear_entries(self) -> None:
        """Limpa entradas (usar com cuidado)"""
        self.entries.clear()

def audit_operation(operation: str, object_type: str):
    """
    Decorator para auditoria automática de operações
    
    Args:
        operation: Nome da operação (e.g., "create_user", "delete_group")
        object_type: Tipo do objeto (e.g., "user", "group", "schema")
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Obtém audit logger do contexto
            audit_logger = get_audit_logger()
            
            # Tenta extrair nome do objeto dos argumentos
            object_name = "unknown"
            if args:
                # Primeiro argumento é geralmente 'self', segundo pode ser nome/id
                if len(args) > 1:
                    if isinstance(args[1], str):
                        object_name = args[1]
                    elif hasattr(args[1], 'name'):
                        object_name = args[1].name
                    elif hasattr(args[1], 'username'):
                        object_name = args[1].username
                        
            # Pode sobrescrever com kwargs
            if 'audit_object_name' in kwargs:
                object_name = kwargs.pop('audit_object_name')
                
            success = False
            error_details = None
            
            try:
                # Executa função original
                result = func(*args, **kwargs)
                success = True
                
                # Se resultado tem atributo success, usa ele
                if hasattr(result, 'success'):
                    success = result.success
                    
                return result
                
            except Exception as e:
                success = False
                error_details = str(e)
                raise
                
            finally:
                # Registra auditoria
                details = error_details if not success else None
                audit_logger.log_operation(
                    operation=operation,
                    object_type=object_type,
                    object_name=object_name,
                    success=success,
                    details=details
                )
                
        return wrapper
    return decorator

# Decorators específicos para operações comuns
def audit_user_operation(operation: str):
    """Decorator para operações de usuário"""
    return audit_operation(operation, "user")

def audit_group_operation(operation: str):
    """Decorator para operações de grupo"""
    return audit_operation(operation, "group")

def audit_schema_operation(operation: str):
    """Decorator para operações de schema"""
    return audit_operation(operation, "schema")

def audit_privilege_operation(operation: str):
    """Decorator para operações de privilégio"""
    return audit_operation(operation, "privilege")

# Decorators pré-configurados
create_user = audit_user_operation("create_user")
update_user = audit_user_operation("update_user")
delete_user = audit_user_operation("delete_user")

create_group = audit_group_operation("create_group")
update_group = audit_group_operation("update_group")
delete_group = audit_group_operation("delete_group")

grant_privilege = audit_privilege_operation("grant_privilege")
revoke_privilege = audit_privilege_operation("revoke_privilege")

# Singleton instances
_audit_context_instance = None
_audit_logger_instance = None

def get_audit_context() -> AuditContext:
    """Retorna o contexto de auditoria"""
    global _audit_context_instance
    if _audit_context_instance is None:
        _audit_context_instance = AuditContext()
    return _audit_context_instance

def get_audit_logger() -> AuditLogger:
    """Retorna o logger de auditoria"""
    global _audit_logger_instance
    if _audit_logger_instance is None:
        context = get_audit_context()
        _audit_logger_instance = AuditLogger(context)
    return _audit_logger_instance

def set_audit_user(username: str) -> None:
    """Define usuário para auditoria (helper function)"""
    get_audit_context().set_user(username)
