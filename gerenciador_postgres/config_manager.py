import yaml
from .path_config import CONFIG_DIR

CONFIG_FILE = CONFIG_DIR / 'config.yml'

def load_config():
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def save_config(data):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, allow_unicode=True)
