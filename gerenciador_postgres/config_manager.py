import yaml
from .path_config import CONFIG_DIR, BASE_DIR

CONFIG_FILE = CONFIG_DIR / 'config.yml'
DEFAULT_CONFIG = {
    'log_path': str(BASE_DIR / 'logs' / 'app.log'),
    'log_level': 'INFO',
    'group_prefix': 'grp_'
}

def load_config():
    if not CONFIG_FILE.exists():
        CONFIG_DIR.mkdir(exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            yaml.safe_dump(DEFAULT_CONFIG, f, allow_unicode=True)
        return DEFAULT_CONFIG.copy()
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    return {**DEFAULT_CONFIG, **data}

def save_config(data):
    CONFIG_DIR.mkdir(exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, allow_unicode=True)
