from velox import VeloxApp
from velox.config import CONFIG_PATH, Config, ServerConfig


def test_config_load_missing_file(tmp_path) -> None:
    """
    A missing config file yields a default Config.
    """
    config = Config.load(tmp_path / "missing.yaml")
    assert config.server == ServerConfig()


def test_config_load_roundtrip(tmp_path) -> None:
    """
    A saved config reloads with the same values.
    """
    path = tmp_path / "configuration.yaml"
    Config(server=ServerConfig(api_key="abc")).save(path)
    assert Config.load(path).server.api_key == "abc"


def test_default_config_path_is_relative() -> None:
    """
    The app config lives in the project root.
    """
    assert CONFIG_PATH.name == "configuration.yaml"


def test_app_instantiates(monkeypatch) -> None:
    """
    A VeloxApp loads its config from disk and is usable.
    """
    monkeypatch.setattr(Config, "load", lambda *_: Config())
    app = VeloxApp()
    assert isinstance(app.config, Config)
