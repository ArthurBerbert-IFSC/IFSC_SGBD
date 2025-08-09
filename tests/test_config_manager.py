import logging
import yaml
from gerenciador_postgres import config_manager


def test_load_config_creates_file(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_file = config_dir / "config.yml"
    monkeypatch.setattr(config_manager, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config_manager, "CONFIG_FILE", config_file)

    data = config_manager.load_config()

    assert config_file.exists()
    assert data["log_level"] == "INFO"
    assert "log_path" in data
    assert data["group_prefix"] == "grp_"


def test_load_config_yaml_error(tmp_path, monkeypatch, caplog):
    config_dir = tmp_path / "config"
    config_file = config_dir / "config.yml"
    config_dir.mkdir()
    config_file.write_text("log_level: [INFO", encoding="utf-8")
    monkeypatch.setattr(config_manager, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config_manager, "CONFIG_FILE", config_file)

    with caplog.at_level(logging.WARNING):
        data = config_manager.load_config()
    assert "Failed to parse" in caplog.text

    assert data == config_manager.DEFAULT_CONFIG
    assert yaml.safe_load(config_file.read_text()) == config_manager.DEFAULT_CONFIG
