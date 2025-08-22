"""
Logging estruturado para o sistema
"""
import logging
import logging.config
import json
import time
from typing import Dict, Any, Optional
from pathlib import Path
from .constants import Paths

class StructuredLogger:
    """
    Logger estruturado que adiciona contexto automático
    """
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.context: Dict[str, Any] = {}
        
    def add_context(self, **kwargs) -> None:
        """Adiciona contexto persistente ao logger"""
        self.context.update(kwargs)
        
    def clear_context(self) -> None:
        """Remove todo o contexto"""
        self.context.clear()
        
    def _format_message(self, message: str, **kwargs) -> Dict[str, Any]:
        """Formata mensagem com contexto"""
        log_data = {
            'timestamp': time.time(),
            'message': message,
            'context': self.context.copy(),
            **kwargs
        }
        return log_data
        
    def info(self, message: str, **kwargs) -> None:
        """Log de informação"""
        log_data = self._format_message(message, **kwargs)
        self.logger.info(json.dumps(log_data, default=str))
        
    def error(self, message: str, **kwargs) -> None:
        """Log de erro"""
        log_data = self._format_message(message, **kwargs)
        self.logger.error(json.dumps(log_data, default=str))
        
    def warning(self, message: str, **kwargs) -> None:
        """Log de warning"""
        log_data = self._format_message(message, **kwargs)
        self.logger.warning(json.dumps(log_data, default=str))
        
    def debug(self, message: str, **kwargs) -> None:
        """Log de debug"""
        log_data = self._format_message(message, **kwargs)
        self.logger.debug(json.dumps(log_data, default=str))

def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> None:
    """
    Configura o sistema de logging
    """
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'structured': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            },
            'simple': {
                'format': '%(levelname)s - %(message)s'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': log_level,
                'formatter': 'simple',
                'stream': 'ext://sys.stdout'
            }
        },
        'loggers': {
            'gerenciador_postgres': {
                'level': log_level,
                'handlers': ['console'],
                'propagate': False
            }
        },
        'root': {
            'level': log_level,
            'handlers': ['console']
        }
    }
    
    # Adiciona handler de arquivo se especificado
    if log_file:
        log_path = Path(Paths.LOG_DIR)
        log_path.mkdir(exist_ok=True)
        
        config['handlers']['file'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': log_level,
            'formatter': 'structured',
            'filename': str(log_path / log_file),
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5
        }
        
        config['loggers']['gerenciador_postgres']['handlers'].append('file')
        config['root']['handlers'].append('file')
    
    logging.config.dictConfig(config)

def get_logger(name: str) -> StructuredLogger:
    """Retorna um logger estruturado"""
    return StructuredLogger(name)
