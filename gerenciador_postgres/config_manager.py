import logging
import yaml
from .path_config import CONFIG_DIR, BASE_DIR

CONFIG_FILE = CONFIG_DIR / 'config.yml'
DEFAULT_CONFIG = {
    'log_path': str(BASE_DIR / 'logs' / 'app.log'),
    'log_level': 'INFO',
    'group_prefix': 'grp_'
}

logger = logging.getLogger(__name__)

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
    return {**DEFAULT_CONFIG, **data}

def save_config(data):
    CONFIG_DIR.mkdir(exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, allow_unicode=True)
