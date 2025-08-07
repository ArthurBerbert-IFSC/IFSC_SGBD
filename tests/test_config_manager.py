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
