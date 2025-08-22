"""
Core infrastructure components

This module provides the foundational infrastructure for the application:
- Event bus for decoupled communication
- Service container for dependency injection  
- Smart caching with TTL and invalidation
- Task manager for background operations
- Structured logging
- Configuration management
- Metrics and health checking
- Input validation
- Audit trail
"""

# Core infrastructure
from .event_bus import EventBus, get_event_bus
from .service_container import ServiceContainer, get_container
from .cache import SmartCache, get_cache
from .task_manager import TaskManager, get_task_manager
from .logging import StructuredLogger, get_logger, setup_logging
from .config import ConfigManager, get_config_manager, get_config
from .metrics import AppMetrics, HealthChecker, get_metrics, get_health_checker
from .constants import *
from .models import *

# Validation system
from .validation import (
    ValidationResult, ValidationError,
    RequiredValidator, LengthValidator, RegexValidator,
    EmailValidator, UsernameValidator, PasswordValidator,
    SchemaValidator, UserValidators, GroupValidators,
    ValidationSystem, get_validation_system
)

# Audit system
from .audit import (
    AuditContext, AuditLogger, get_audit_context, get_audit_logger,
    audit_operation, create_user, update_user, delete_user,
    create_group, update_group, delete_group,
    grant_privilege, revoke_privilege, set_audit_user
)

# Global initialization flag
_services_initialized = False

def initialize_core_services():
    """Inicializa todos os serviços da infraestrutura core.
    
    Esta função deve ser chamada uma vez no início da aplicação.
    """
    global _services_initialized
    
    if _services_initialized:
        return
    
    # Initialize services in correct order
    _ = get_config_manager()  # Config first
    _ = get_logger(__name__)  # Logger second
    _ = get_event_bus()       # Event bus
    _ = get_cache()           # Cache
    _ = get_metrics()         # Metrics
    _ = get_task_manager()    # Task manager
    _ = get_audit_logger()    # Audit
    
    _services_initialized = True
    
    logger = get_logger(__name__)
    logger.info("Core services initialized successfully")

def is_initialized() -> bool:
    """Verifica se os serviços core foram inicializados."""
    return _services_initialized

__all__ = [
    # Core initialization
    'initialize_core_services', 'is_initialized',
    
    # Event system
    'EventBus', 'get_event_bus',
    
    # Service container
    'ServiceContainer', 'get_container',
    
    # Caching
    'SmartCache', 'get_cache',
    
    # Task management
    'TaskManager', 'get_task_manager',
    
    # Logging
    'StructuredLogger', 'get_logger', 'setup_logging',
    
    # Configuration
    'ConfigManager', 'get_config_manager', 'get_config',
    
    # Metrics and health
    'AppMetrics', 'HealthChecker', 'get_metrics', 'get_health_checker',
    
    # Constants and models
    'DatabaseConstants', 'UIConstants', 'EventTypes', 'Messages',
    'ConnectionInfo', 'User', 'Group', 'Schema', 'OperationResult',
    
    # Validation
    'ValidationResult', 'ValidationError', 'SchemaValidator',
    'RequiredValidator', 'LengthValidator', 'EmailValidator',
    'UserValidators', 'GroupValidators', 'ValidationSystem', 'get_validation_system',
    
    # Audit
    'AuditContext', 'AuditLogger', 'get_audit_context', 'get_audit_logger',
    'audit_operation', 'create_user', 'update_user', 'delete_user',
    'set_audit_user'
]
