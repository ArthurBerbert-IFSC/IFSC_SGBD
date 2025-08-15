import logging
import yaml
import importlib
import pytest


def load_module():
    import gerenciador_postgres.config_manager as cm
    importlib.reload(cm)
    return cm


def test_load_config_creates_file(tmp_path, monkeypatch):
    cm = load_module()
    config_dir = tmp_path / "config"
    config_file = config_dir / "config.yml"
    monkeypatch.setattr(cm, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(cm, "CONFIG_FILE", config_file)

    data = cm.load_config()

    assert config_file.exists()
    assert data["log_level"] == "INFO"
    assert "log_path" in data
    assert data["group_prefix"] == "turma_"
    assert data["user_prefix"] == "monitores_"
    assert data["schema_creation_group"] == "Professores"
    assert data["connect_timeout"] == 5


def test_load_config_yaml_error(tmp_path, monkeypatch, caplog):
    cm = load_module()
    config_dir = tmp_path / "config"
    config_file = config_dir / "config.yml"
    config_dir.mkdir()
    config_file.write_text("log_level: [INFO", encoding="utf-8")
    monkeypatch.setattr(cm, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(cm, "CONFIG_FILE", config_file)

    with caplog.at_level(logging.WARNING):
        data = cm.load_config()
    assert "Failed to parse" in caplog.text

    assert data == cm.DEFAULT_CONFIG
    assert yaml.safe_load(config_file.read_text()) == cm.DEFAULT_CONFIG


def test_env_config_file_override(tmp_path, monkeypatch):
    env_file = tmp_path / "custom.yml"
    env_file.write_text("log_level: DEBUG\n", encoding="utf-8")
    monkeypatch.setenv("IFSC_SGBD_CONFIG_FILE", str(env_file))
    cm = load_module()
    data = cm.load_config()
    assert data["log_level"] == "DEBUG"


def test_relative_log_path_resolved(tmp_path, monkeypatch):
    cm = load_module()
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "config.yml"
    config_file.write_text("log_path: logs/test.log\n", encoding="utf-8")
    monkeypatch.setattr(cm, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(cm, "CONFIG_FILE", config_file)

    data = cm.load_config()
    expected = cm.BASE_DIR / "logs" / "test.log"
    assert data["log_path"] == str(expected)


def test_validate_config(monkeypatch):
    cm = load_module()
    invalid = {"databases": [{"name": "A", "host": "h"}]}
    with pytest.raises(ValueError):
        cm.validate_config(invalid)

