from unittest.mock import patch

from core.config import (
    get_api_key,
    get_base_url,
    get_model,
    get_provider,
    get_settings,
    save_settings,
    set_api_key,
    set_base_url,
    set_model,
    set_provider,
)


@patch("core.config.keyring")
def test_get_api_key_returns_key(mock_keyring):
    mock_keyring.get_password.return_value = "sk-test123"
    assert get_api_key(provider_id="minimax") == "sk-test123"


@patch("core.config.keyring")
def test_get_api_key_returns_empty_when_none(mock_keyring):
    mock_keyring.get_password.return_value = None
    assert get_api_key(provider_id="minimax") == ""


@patch("core.config.keyring")
def test_set_api_key(mock_keyring):
    set_api_key("sk-new-key", provider_id="minimax")
    mock_keyring.set_password.assert_called_once_with(
        "thebox_minimax", "api_key", "sk-new-key"
    )


def test_get_model_default(tmp_path, monkeypatch):
    monkeypatch.delenv("THEBOX_MODEL", raising=False)
    monkeypatch.delenv("THEBOX_PROVIDER", raising=False)
    config_file = tmp_path / ".thebox_config.json"
    monkeypatch.setattr("core.config.CONFIG_FILE", config_file)
    assert get_model() == "MiniMax-M2.7"


def test_set_and_get_model(tmp_path, monkeypatch):
    config_file = tmp_path / ".thebox_config.json"
    monkeypatch.setattr("core.config.CONFIG_FILE", config_file)
    monkeypatch.delenv("THEBOX_MODEL", raising=False)
    set_model("gpt-4")
    assert get_model() == "gpt-4"


def test_get_model_from_env(monkeypatch):
    monkeypatch.setenv("THEBOX_MODEL", "gpt-3.5-turbo")
    assert get_model() == "gpt-3.5-turbo"


def test_provider_default_is_minimax(tmp_path, monkeypatch):
    monkeypatch.delenv("THEBOX_PROVIDER", raising=False)
    config_file = tmp_path / ".thebox_config.json"
    monkeypatch.setattr("core.config.CONFIG_FILE", config_file)
    assert get_provider() == "minimax"


def test_set_and_get_provider(tmp_path, monkeypatch):
    config_file = tmp_path / ".thebox_config.json"
    monkeypatch.setattr("core.config.CONFIG_FILE", config_file)
    monkeypatch.delenv("THEBOX_PROVIDER", raising=False)
    set_provider("deepseek")
    assert get_provider() == "deepseek"
    assert get_model() == "deepseek-chat"


def test_get_base_url_default(tmp_path, monkeypatch):
    monkeypatch.delenv("THEBOX_BASE_URL", raising=False)
    monkeypatch.delenv("THEBOX_PROVIDER", raising=False)
    config_file = tmp_path / ".thebox_config.json"
    monkeypatch.setattr("core.config.CONFIG_FILE", config_file)
    assert get_base_url() == "https://api.minimaxi.com/v1"


def test_get_base_url_from_env(monkeypatch):
    monkeypatch.setenv("THEBOX_BASE_URL", "https://custom.endpoint/v1")
    assert get_base_url() == "https://custom.endpoint/v1"


def test_set_and_get_base_url(tmp_path, monkeypatch):
    config_file = tmp_path / ".thebox_config.json"
    monkeypatch.setattr("core.config.CONFIG_FILE", config_file)
    monkeypatch.delenv("THEBOX_BASE_URL", raising=False)
    set_base_url("https://my.custom.url/v1")
    assert get_base_url() == "https://my.custom.url/v1"


def test_get_settings(tmp_path, monkeypatch):
    monkeypatch.delenv("THEBOX_MODEL", raising=False)
    monkeypatch.delenv("THEBOX_PROVIDER", raising=False)
    monkeypatch.delenv("THEBOX_BASE_URL", raising=False)
    config_file = tmp_path / ".thebox_config.json"
    monkeypatch.setattr("core.config.CONFIG_FILE", config_file)
    settings = get_settings()
    assert settings["provider"] == "minimax"
    assert settings["base_url"] == "https://api.minimaxi.com/v1"
    assert settings["model"] == "MiniMax-M2.7"


def test_save_settings(tmp_path, monkeypatch):
    monkeypatch.delenv("THEBOX_MODEL", raising=False)
    monkeypatch.delenv("THEBOX_PROVIDER", raising=False)
    monkeypatch.delenv("THEBOX_BASE_URL", raising=False)
    config_file = tmp_path / ".thebox_config.json"
    monkeypatch.setattr("core.config.CONFIG_FILE", config_file)
    save_settings("openai", "https://api.openai.com/v1", "gpt-4o")
    settings = get_settings()
    assert settings["provider"] == "openai"
    assert settings["base_url"] == "https://api.openai.com/v1"
    assert settings["model"] == "gpt-4o"
