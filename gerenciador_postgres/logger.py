import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from .path_config import BASE_DIR
from .config_manager import load_config


def setup_logger():
    """Configure o logger raiz para arquivo e console.

    Lê as configurações de ``config.yml`` e ajusta o *logger* raiz
    (``logging.getLogger()``) para que todos os módulos do projeto possam
    obter *loggers* específicos via ``logging.getLogger(__name__)`` e ainda
    assim compartilhar a mesma configuração.
    """

    try:
        cfg = load_config()
    except Exception:
        cfg = {"log_path": str(BASE_DIR / "logs" / "app.log"), "log_level": "INFO"}

    log_path = Path(cfg.get("log_path", BASE_DIR / "logs" / "app.log"))
    log_path = log_path if log_path.is_absolute() else BASE_DIR / log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_level = getattr(logging, cfg.get("log_level", "INFO").upper(), logging.INFO)

    logger = logging.getLogger()  # logger raiz
    logger.setLevel(log_level)

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    file_handler = RotatingFileHandler(
        log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(log_level)
    stream_handler.setFormatter(formatter)

    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    # Suprimir verborragia de bibliotecas muito detalhadas (ex: pdfminer)
    noisy_modules = [
        "pdfminer",
        "pdfminer.psparser",
        "pdfminer.pdfinterp",
        "pdfminer.pdfparser",
        "pdfminer.pdfdocument",
        "pdfminer.pdfpage",
    ]
    for mod in noisy_modules:
        logging.getLogger(mod).setLevel(logging.WARNING)

    return logger


# Configure default logger on module import if not already configured
if not logging.getLogger('app').handlers:
    setup_logger()
