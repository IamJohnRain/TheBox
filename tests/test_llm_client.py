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
def test_initialize_without_api_key(mock_get_key):
    client = LLMClient()
    client.initialize()
    assert not client.is_initialized


@patch("core.llm_client.get_api_key", return_value="sk-test")
@patch("core.llm_client.OpenAI")
@patch("core.llm_client.get_model", return_value="gpt-4o-mini")
def test_initialize_with_api_key(mock_model, mock_openai, mock_key):
    client = LLMClient()
    client.initialize()
    assert client.is_initialized


def test_chat_completion_raises_when_not_initialized():
    client = LLMClient()
    with pytest.raises(ConfigError):
        client.chat_completion(messages=[{"role": "user", "content": "hi"}])


@patch("core.llm_client.get_api_key", return_value="sk-test")
@patch("core.llm_client.OpenAI")
@patch("core.llm_client.get_model", return_value="gpt-4o-mini")
def test_chat_completion_success(mock_model, mock_openai_cls, mock_key):
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
