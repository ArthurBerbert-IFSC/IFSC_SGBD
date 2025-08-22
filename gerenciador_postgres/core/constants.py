"""
Constantes centralizadas do sistema
"""
from enum import Enum
from typing import Dict, Set, Any

# Database constants
class DatabaseConstants:
    DEFAULT_PORT = 5432
    CONNECTION_TIMEOUT = 30
    QUERY_TIMEOUT = 60
    POOL_MIN_SIZE = 2
    POOL_MAX_SIZE = 10

# UI Constants
class UIConstants:
    DASHBOARD_MIN_WIDTH = 180
    DASHBOARD_MAX_WIDTH = 16777215
    DEFAULT_WINDOW_WIDTH = 1200
    DEFAULT_WINDOW_HEIGHT = 800
    REFRESH_INTERVAL_MS = 5000

# Privilege constants
class PrivilegeConstants:
    SCHEMA_PRIVILEGES = {"USAGE", "CREATE"}
    TABLE_PRIVILEGES = {"SELECT", "INSERT", "UPDATE", "DELETE"}
    DATABASE_PRIVILEGES = {"CONNECT", "CREATE", "TEMPORARY"}
    
# Messages
class Messages:
    CONNECTION_SUCCESS = "Conexão realizada com sucesso"
    CONNECTION_FAILED = "Falha na conexão"
    OPERATION_SUCCESS = "Operação realizada com sucesso"
    OPERATION_FAILED = "Falha na operação"
    CONFIRM_DELETE = "Tem certeza que deseja excluir?"
    UNSAVED_CHANGES = "Há alterações não salvas. Deseja salvar?"

# Event types for event bus
class EventTypes:
    CONNECTION_ESTABLISHED = "connection_established"
    CONNECTION_LOST = "connection_lost"
    USER_CREATED = "user_created"
    USER_DELETED = "user_deleted"
    GROUP_CREATED = "group_created"
    GROUP_DELETED = "group_deleted"
    SCHEMA_CREATED = "schema_created"
    PRIVILEGES_CHANGED = "privileges_changed"
    UI_REFRESH_REQUESTED = "ui_refresh_requested"

# SQL Query categories
class QueryCategories:
    READ = "read"
    WRITE = "write"
    DDL = "ddl"
    PRIVILEGED = "privileged"

# File paths
class Paths:
    CONFIG_FILE = "config/config.yml"
    LOG_DIR = "logs"
    TEMP_DIR = "temp"
    ASSETS_DIR = "assets"

# Status codes
class StatusCode(Enum):
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    PENDING = "pending"

# Cache settings
class CacheSettings:
    DEFAULT_TTL = 300  # 5 minutes
    USER_LIST_TTL = 60
    GROUP_LIST_TTL = 60
    SCHEMA_LIST_TTL = 120
    PRIVILEGE_TTL = 30
