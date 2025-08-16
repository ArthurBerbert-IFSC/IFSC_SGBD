import logging
import os
from pathlib import Path
import yaml
from .path_config import BASE_DIR, CONFIG_DIR as DEFAULT_CONFIG_DIR

CONFIG_FILE_ENV = os.getenv("IFSC_SGBD_CONFIG_FILE")
if CONFIG_FILE_ENV:
    CONFIG_FILE = Path(CONFIG_FILE_ENV)
    if not CONFIG_FILE.is_absolute():
        CONFIG_FILE = BASE_DIR / CONFIG_FILE
    CONFIG_DIR = CONFIG_FILE.parent
else:
    CONFIG_DIR = DEFAULT_CONFIG_DIR
    CONFIG_FILE = CONFIG_DIR / "config.yml"

DEFAULT_CONFIG = {
    "log_path": str(BASE_DIR / "logs" / "app.log"),
    "log_level": "INFO",
    "group_prefix": "turma_",
    "user_prefix": "monitores_*",
    "schema_creation_group": "Professores",
    "connect_timeout": 5,
}

logger = logging.getLogger(__name__)
logger.propagate = True

def load_config():
    if not CONFIG_FILE.exists():
        CONFIG_DIR.mkdir(exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            yaml.safe_dump(DEFAULT_CONFIG, f, allow_unicode=True)
        return DEFAULT_CONFIG.copy()
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        try:
            data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            logger.warning("Failed to parse %s: %s", CONFIG_FILE, e)
            with open(CONFIG_FILE, 'w', encoding='utf-8') as fw:
                yaml.safe_dump(DEFAULT_CONFIG, fw, allow_unicode=True)
            return DEFAULT_CONFIG.copy()
    result = {**DEFAULT_CONFIG, **data}
    log_path = result.get('log_path')
    if log_path:
        log_path_path = Path(log_path)
        if not log_path_path.is_absolute():
            log_path_path = BASE_DIR / log_path_path
        result['log_path'] = str(log_path_path)
    return result

def save_config(data):
    CONFIG_DIR.mkdir(exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, allow_unicode=True)


def validate_config(cfg: dict) -> None:
    """Validates configuration structure and values.

    Raises ValueError with collected errors when invalid. Emits warnings for
    non-fatal issues such as absolute log paths outside ``BASE_DIR``.
    """

    errors = []

    databases = cfg.get("databases")
    if not isinstance(databases, list) or not databases:
        errors.append("'databases' deve ser uma lista não vazia")
    else:
        names_seen = set()
        for db in databases:
            name = db.get("name")
            for key in ("name", "host", "port", "dbname", "user"):
                if key not in db:
                    errors.append(f"Perfil '{name or '?'}' sem chave obrigatória: {key}")
            if "password" in db:
                errors.append(f"Perfil '{name or '?'}' não deve conter password")
            if name:
                lname = name.lower()
                if lname in names_seen:
                    errors.append(f"Nome de perfil duplicado: {name}")
                names_seen.add(lname)

    log_path = cfg.get("log_path")
    if log_path:
        p = Path(log_path)
        if p.is_absolute() and not str(p).startswith(str(BASE_DIR)):
            logger.warning("log_path fora de BASE_DIR: %s", log_path)

    if errors:
        raise ValueError("\n".join(errors))
