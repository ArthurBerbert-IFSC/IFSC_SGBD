"""
Sistema de configuração centralizado
"""
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from ..core.constants import Paths, DatabaseConstants, UIConstants
from ..core.logging import get_logger

logger = get_logger(__name__)

@dataclass
class DatabaseConfig:
    """Configuração de banco de dados"""
    default_port: int = DatabaseConstants.DEFAULT_PORT
    connection_timeout: int = DatabaseConstants.CONNECTION_TIMEOUT
    query_timeout: int = DatabaseConstants.QUERY_TIMEOUT
    pool_min_size: int = DatabaseConstants.POOL_MIN_SIZE
    pool_max_size: int = DatabaseConstants.POOL_MAX_SIZE

@dataclass
class UIConfig:
    """Configuração de interface"""
    window_width: int = UIConstants.DEFAULT_WINDOW_WIDTH
    window_height: int = UIConstants.DEFAULT_WINDOW_HEIGHT
    dashboard_width: int = UIConstants.DASHBOARD_MIN_WIDTH
    auto_refresh_enabled: bool = False
    refresh_interval_ms: int = UIConstants.REFRESH_INTERVAL_MS
    theme: str = "default"

@dataclass
class LoggingConfig:
    """Configuração de logging"""
    level: str = "INFO"
    file_enabled: bool = True
    file_name: str = "app.log"
    max_file_size_mb: int = 10
    backup_count: int = 5

@dataclass
class AppConfig:
    """Configuração principal da aplicação"""
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    group_prefix: str = "grp_"
    debug_mode: bool = False

class ConfigManager:
    """
    Gerenciador de configurações da aplicação
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path or Paths.CONFIG_FILE)
        self.config: AppConfig = AppConfig()
        self._load_config()
        
    def _load_config(self) -> None:
        """Carrega configuração do arquivo"""
        if not self.config_path.exists():
            logger.info(f"Arquivo de configuração não encontrado: {self.config_path}")
            self._save_config()  # Cria arquivo padrão
            return
            
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                
            # Atualiza configuração com valores do arquivo
            self._update_config_from_dict(data)
            logger.info(f"Configuração carregada de: {self.config_path}")
            
        except Exception as e:
            logger.error(f"Erro ao carregar configuração: {e}")
            
    def _update_config_from_dict(self, data: Dict[str, Any]) -> None:
        """Atualiza configuração a partir de dicionário"""
        
        # Database config
        if 'database' in data:
            db_data = data['database']
            self.config.database.default_port = db_data.get('default_port', self.config.database.default_port)
            self.config.database.connection_timeout = db_data.get('connection_timeout', self.config.database.connection_timeout)
            self.config.database.query_timeout = db_data.get('query_timeout', self.config.database.query_timeout)
            self.config.database.pool_min_size = db_data.get('pool_min_size', self.config.database.pool_min_size)
            self.config.database.pool_max_size = db_data.get('pool_max_size', self.config.database.pool_max_size)
            
        # UI config
        if 'ui' in data:
            ui_data = data['ui']
            self.config.ui.window_width = ui_data.get('window_width', self.config.ui.window_width)
            self.config.ui.window_height = ui_data.get('window_height', self.config.ui.window_height)
            self.config.ui.dashboard_width = ui_data.get('dashboard_width', self.config.ui.dashboard_width)
            self.config.ui.auto_refresh_enabled = ui_data.get('auto_refresh_enabled', self.config.ui.auto_refresh_enabled)
            self.config.ui.refresh_interval_ms = ui_data.get('refresh_interval_ms', self.config.ui.refresh_interval_ms)
            self.config.ui.theme = ui_data.get('theme', self.config.ui.theme)
            
        # Logging config
        if 'logging' in data:
            log_data = data['logging']
            self.config.logging.level = log_data.get('level', self.config.logging.level)
            self.config.logging.file_enabled = log_data.get('file_enabled', self.config.logging.file_enabled)
            self.config.logging.file_name = log_data.get('file_name', self.config.logging.file_name)
            self.config.logging.max_file_size_mb = log_data.get('max_file_size_mb', self.config.logging.max_file_size_mb)
            self.config.logging.backup_count = log_data.get('backup_count', self.config.logging.backup_count)
            
        # General config
        self.config.group_prefix = data.get('group_prefix', self.config.group_prefix)
        self.config.debug_mode = data.get('debug_mode', self.config.debug_mode)
        
    def _save_config(self) -> None:
        """Salva configuração no arquivo"""
        try:
            # Cria diretório se não existir
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'database': {
                    'default_port': self.config.database.default_port,
                    'connection_timeout': self.config.database.connection_timeout,
                    'query_timeout': self.config.database.query_timeout,
                    'pool_min_size': self.config.database.pool_min_size,
                    'pool_max_size': self.config.database.pool_max_size
                },
                'ui': {
                    'window_width': self.config.ui.window_width,
                    'window_height': self.config.ui.window_height,
                    'dashboard_width': self.config.ui.dashboard_width,
                    'auto_refresh_enabled': self.config.ui.auto_refresh_enabled,
                    'refresh_interval_ms': self.config.ui.refresh_interval_ms,
                    'theme': self.config.ui.theme
                },
                'logging': {
                    'level': self.config.logging.level,
                    'file_enabled': self.config.logging.file_enabled,
                    'file_name': self.config.logging.file_name,
                    'max_file_size_mb': self.config.logging.max_file_size_mb,
                    'backup_count': self.config.logging.backup_count
                },
                'group_prefix': self.config.group_prefix,
                'debug_mode': self.config.debug_mode
            }
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
                
            logger.info(f"Configuração salva em: {self.config_path}")
            
        except Exception as e:
            logger.error(f"Erro ao salvar configuração: {e}")
            
    def save(self) -> None:
        """Salva configuração atual"""
        self._save_config()
        
    def get(self, key: str, default: Any = None) -> Any:
        """Obtém valor de configuração usando notação de ponto"""
        try:
            obj = self.config
            for part in key.split('.'):
                obj = getattr(obj, part)
            return obj
        except AttributeError:
            return default
            
    def set(self, key: str, value: Any) -> None:
        """Define valor de configuração usando notação de ponto"""
        try:
            obj = self.config
            parts = key.split('.')
            for part in parts[:-1]:
                obj = getattr(obj, part)
            setattr(obj, parts[-1], value)
        except AttributeError:
            logger.warning(f"Chave de configuração inválida: {key}")

# Singleton instance
_config_manager_instance = None

def get_config_manager() -> ConfigManager:
    """Retorna a instância singleton do config manager"""
    global _config_manager_instance
    if _config_manager_instance is None:
        _config_manager_instance = ConfigManager()
    return _config_manager_instance

def get_config() -> AppConfig:
    """Retorna a configuração atual"""
    return get_config_manager().config
