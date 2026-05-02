from unittest.mock import MagicMock, patch

import pytest

from core.exceptions import ConfigError
from core.llm_client import LLMClient


@pytest.fixture(autouse=True)
def reset_singleton():
    LLMClient._instance = None
    yield
    LLMClient._instance = None


def test_singleton_returns_same_instance():
    a = LLMClient()
    b = LLMClient()
    assert a is b


def test_not_initialized_by_default():
    client = LLMClient()
    assert not client.is_initialized


@patch("core.llm_client.get_api_key", return_value="")
@patch("core.llm_client.get_provider", return_value="minimax")
def test_initialize_without_api_key(mock_provider, mock_get_key):
    client = LLMClient()
    client.initialize()
    assert not client.is_initialized


@patch("core.llm_client.get_api_key", return_value="sk-test")
@patch("core.llm_client.get_base_url", return_value="https://api.minimaxi.com/v1")
@patch("core.llm_client.get_model", return_value="MiniMax-M2.7")
@patch("core.llm_client.get_provider", return_value="minimax")
@patch("core.llm_client.OpenAI")
def test_initialize_with_api_key(mock_openai, mock_provider, mock_model, mock_url, mock_key):
    client = LLMClient()
    client.initialize()
    assert client.is_initialized
    assert client.provider == "minimax"
    assert client.base_url == "https://api.minimaxi.com/v1"


def test_chat_completion_raises_when_not_initialized():
    client = LLMClient()
    with pytest.raises(ConfigError):
        client.chat_completion(messages=[{"role": "user", "content": "hi"}])


@patch("core.llm_client.get_api_key", return_value="sk-test")
@patch("core.llm_client.get_base_url", return_value="https://api.openai.com/v1")
@patch("core.llm_client.get_model", return_value="gpt-4o-mini")
@patch("core.llm_client.get_provider", return_value="openai")
@patch("core.llm_client.OpenAI")
def test_chat_completion_success(mock_openai_cls, mock_provider, mock_model, mock_url, mock_key):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Hello back"
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai_cls.return_value = mock_client

    client = LLMClient()
    client.initialize()
    result = client.chat_completion(messages=[{"role": "user", "content": "hi"}])
    assert result == "Hello back"
