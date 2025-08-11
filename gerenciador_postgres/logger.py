import logging
from logging.handlers import RotatingFileHandler
from .path_config import BASE_DIR
from .config_manager import load_config
import os


def setup_logger():
    """Configure o logger raiz para arquivo e console.

    Lê as configurações de ``config.yml`` e ajusta o *logger* raiz
    (``logging.getLogger()``) para que todos os módulos do projeto possam
    obter *loggers* específicos via ``logging.getLogger(__name__)`` e ainda
    assim compartilhar a mesma configuração.
    """

    try:
        config = load_config()
    except Exception:
        config = {"log_path": str(BASE_DIR / "logs" / "app.log"), "log_level": "INFO"}

    log_path = config.get("log_path", str(BASE_DIR / "logs" / "app.log"))
    log_level = getattr(logging, config.get("log_level", "INFO").upper(), logging.INFO)

    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    logger = logging.getLogger()  # logger raiz
    logger.setLevel(log_level)

    formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s")

    file_handler = RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger


# Configure default logger on module import if not already configured
if not logging.getLogger('app').handlers:
    setup_logger()
