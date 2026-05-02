from unittest.mock import patch

from core.config import get_api_key, get_model, set_api_key, set_model


@patch("core.config.keyring")
def test_get_api_key_returns_key(mock_keyring):
    mock_keyring.get_password.return_value = "sk-test123"
    assert get_api_key() == "sk-test123"


@patch("core.config.keyring")
def test_get_api_key_returns_empty_when_none(mock_keyring):
    mock_keyring.get_password.return_value = None
    assert get_api_key() == ""


@patch("core.config.keyring")
def test_set_api_key(mock_keyring):
    set_api_key("sk-new-key")
    mock_keyring.set_password.assert_called_once_with("thebox", "api_key", "sk-new-key")


def test_get_model_default(tmp_path, monkeypatch):
    monkeypatch.delenv("THEBOX_MODEL", raising=False)
    config_file = tmp_path / ".thebox_config.json"
    monkeypatch.setattr("core.config.CONFIG_FILE", config_file)
    assert get_model() == "gpt-4o-mini"


def test_set_and_get_model(tmp_path, monkeypatch):
    config_file = tmp_path / ".thebox_config.json"
    monkeypatch.setattr("core.config.CONFIG_FILE", config_file)
    monkeypatch.delenv("THEBOX_MODEL", raising=False)
    set_model("gpt-4")
    assert get_model() == "gpt-4"


def test_get_model_from_env(monkeypatch):
    monkeypatch.setenv("THEBOX_MODEL", "gpt-3.5-turbo")
    assert get_model() == "gpt-3.5-turbo"
