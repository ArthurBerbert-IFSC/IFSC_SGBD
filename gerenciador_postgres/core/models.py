"""
Data Transfer Objects e modelos de dados tipados
"""
from dataclasses import dataclass, field
from typing import Optional, Set, List, Dict, Any
from datetime import datetime
from enum import Enum

class ConnectionStatus(Enum):
    """Status da conexão"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"

class UserStatus(Enum):
    """Status do usuário"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"

@dataclass(frozen=True)
class ConnectionInfo:
    """Informações de conexão"""
    host: str
    port: int
    database: str
    username: str
    status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    connected_at: Optional[datetime] = None
    error_message: Optional[str] = None

@dataclass
class User:
    """Modelo de usuário"""
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    status: UserStatus = UserStatus.ACTIVE
    groups: Set[str] = field(default_factory=set)
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    expires_at: Optional[datetime] = None

@dataclass
class Group:
    """Modelo de grupo"""
    name: str
    description: Optional[str] = None
    members: Set[str] = field(default_factory=set)
    privileges: Dict[str, Set[str]] = field(default_factory=dict)
    created_at: Optional[datetime] = None

@dataclass
class Schema:
    """Modelo de schema"""
    name: str
    owner: str
    description: Optional[str] = None
    table_count: int = 0
    size_mb: Optional[float] = None
    created_at: Optional[datetime] = None

@dataclass
class Privilege:
    """Modelo de privilégio"""
    object_type: str  # 'table', 'schema', 'database'
    object_name: str
    privilege_type: str  # 'SELECT', 'INSERT', etc.
    grantee: str
    grantor: str
    is_grantable: bool = False

@dataclass
class OperationResult:
    """Resultado de uma operação"""
    success: bool
    message: str
    data: Optional[Any] = None
    error_details: Optional[str] = None
    
    @classmethod
    def success_result(cls, message: str, data: Any = None) -> 'OperationResult':
        """Cria resultado de sucesso"""
        return cls(success=True, message=message, data=data)
    
    @classmethod
    def error_result(cls, message: str, error_details: str = None) -> 'OperationResult':
        """Cria resultado de erro"""
        return cls(success=False, message=message, error_details=error_details)

@dataclass
class BatchResult:
    """Resultado de operação em lote"""
    total: int
    successful: int
    failed: int
    errors: List[str] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        """Taxa de sucesso (0-1)"""
        return self.successful / self.total if self.total > 0 else 0

@dataclass
class CreateUserRequest:
    """Request para criação de usuário"""
    username: str
    password: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    groups: List[str] = field(default_factory=list)
    expires_at: Optional[datetime] = None

@dataclass
class UpdateUserRequest:
    """Request para atualização de usuário"""
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    groups: Optional[List[str]] = None
    status: Optional[UserStatus] = None
    expires_at: Optional[datetime] = None

@dataclass
class DatabaseStats:
    """Estatísticas do banco"""
    user_count: int = 0
    group_count: int = 0
    schema_count: int = 0
    table_count: int = 0
    connection_count: int = 0
    database_size_mb: float = 0.0
    last_updated: Optional[datetime] = None

@dataclass
class AuditEntry:
    """Entrada de auditoria"""
    timestamp: datetime
    user: str
    operation: str
    object_type: str
    object_name: str
    success: bool
    details: Optional[str] = None
