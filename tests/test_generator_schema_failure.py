"""Tests for core.case_generator.generate_case handling of LLM failures.

Covers three scenarios:
1. LLM returns a non-JSON string — generator retries and eventually raises ValidationError.
2. LLM returns valid JSON that fails schema validation — generator retries.
3. LLM returns valid JSON on the second attempt — generator succeeds.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from core.case_generator import generate_case
from core.exceptions import ValidationError


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

# A minimal valid case dict that conforms to CASE_SCHEMA.
VALID_CASE_DICT = {
    "case_id": "gen_test_001",
    "title": "测试案件",
    "victim": "张三",
    "cause_of_death": "中毒",
    "crime_scene": "书房",
    "truth": "李四因怨恨张三，深夜用毒药毒死了张三。",
    "suspects": [
        {
            "name": "李四",
            "role": "同事",
            "personality": "阴险",
            "knowledge": "我怨恨张三，深夜看到他用毒药。",
            "forbidden_to_reveal": ["我毒的", "毒药"],
        },
        {
            "name": "王五",
            "role": "邻居",
            "personality": "老实",
            "knowledge": "我那天不在场，什么都不知道。",
            "forbidden_to_reveal": ["我杀的"],
        },
    ],
    "evidences": [
        {"id": "e1", "name": "毒药瓶", "description": "书房发现毒药瓶", "related_suspect": "李四"},
    ],
    "interrogation_time_limit_sec": 300,
}


def _make_mock_llm_client(return_value: str):
    """Build a mock LLMClient whose chat_completion returns *return_value*.

    The mock is initialised (is_initialized == True) so that generate_case
    skips the real initialisation path.
    """
    mock_client = MagicMock()
    mock_client.is_initialized = True
    mock_client.chat_completion.return_value = return_value
    return mock_client


def _make_sequential_mock_llm_client(return_values: list):
    """Build a mock LLMClient whose chat_completion returns values in sequence.

    Args:
        return_values: A list of strings returned by consecutive calls.
    """
    mock_client = MagicMock()
    mock_client.is_initialized = True
    mock_client.chat_completion.side_effect = return_values
    return mock_client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGenerateCaseNonJSONResponse:
    """Scenario 1: LLM returns a non-JSON string."""

    @patch("core.case_generator.LLMClient")
    def test_raises_validation_error_after_retries(self, MockLLMClient):
        """When the LLM consistently returns non-JSON, generate_case should
        exhaust its retries and raise a ValidationError."""
        mock_instance = _make_mock_llm_client("This is not JSON at all!")
        MockLLMClient.return_value = mock_instance

        with pytest.raises(ValidationError, match="案件生成失败"):
            generate_case("测试背景", max_retries=2)

    @patch("core.case_generator.LLMClient")
    def test_retries_correct_number_of_times(self, MockLLMClient):
        """generate_case should call chat_completion (max_retries + 1) times
        before giving up."""
        max_retries = 3
        mock_instance = _make_mock_llm_client("not json")
        MockLLMClient.return_value = mock_instance

        with pytest.raises(ValidationError):
            generate_case("测试背景", max_retries=max_retries)

        expected_calls = max_retries + 1
        assert mock_instance.chat_completion.call_count == expected_calls, (
            f"Expected {expected_calls} calls, got {mock_instance.chat_completion.call_count}"
        )


class TestGenerateCaseSchemaInvalidJSON:
    """Scenario 2: LLM returns valid JSON that fails schema validation."""

    @patch("core.case_generator.LLMClient")
    def test_raises_validation_error_for_bad_schema(self, MockLLMClient):
        """When the LLM returns JSON that does not conform to CASE_SCHEMA,
        generate_case should retry and eventually raise ValidationError."""
        # Valid JSON but missing required fields (e.g. no "title", no "suspects")
        bad_case = {"case_id": "bad", "description": "missing many required fields"}
        mock_instance = _make_mock_llm_client(json.dumps(bad_case, ensure_ascii=False))
        MockLLMClient.return_value = mock_instance

        with pytest.raises(ValidationError, match="案件生成失败"):
            generate_case("测试背景", max_retries=1)

    @patch("core.case_generator.LLMClient")
    def test_retries_on_schema_failure(self, MockLLMClient):
        """generate_case should call chat_completion (max_retries + 1) times
        when each attempt returns schema-invalid JSON."""
        max_retries = 2
        bad_case = {"case_id": "bad"}  # missing many required fields
        mock_instance = _make_mock_llm_client(json.dumps(bad_case, ensure_ascii=False))
        MockLLMClient.return_value = mock_instance

        with pytest.raises(ValidationError):
            generate_case("测试背景", max_retries=max_retries)

        expected_calls = max_retries + 1
        assert mock_instance.chat_completion.call_count == expected_calls


class TestGenerateCaseSucceedsOnSecondAttempt:
    """Scenario 3: LLM returns valid JSON on the second attempt."""

    @patch("core.case_generator.LLMClient")
    def test_succeeds_after_initial_failure(self, MockLLMClient):
        """When the first attempt returns non-JSON and the second returns a
        valid case dict, generate_case should succeed and return the case."""
        first_response = "not json"
        second_response = json.dumps(VALID_CASE_DICT, ensure_ascii=False)
        mock_instance = _make_sequential_mock_llm_client([first_response, second_response])
        MockLLMClient.return_value = mock_instance

        result = generate_case("测试背景", max_retries=1)
        assert isinstance(result, dict)
        assert result["case_id"] == "gen_test_001"
        assert result["title"] == "测试案件"
        assert len(result["suspects"]) >= 2

    @patch("core.case_generator.LLMClient")
    def test_succeeds_after_schema_failure_then_valid(self, MockLLMClient):
        """When the first attempt returns schema-invalid JSON and the second
        returns a valid case dict, generate_case should succeed."""
        bad_case = {"case_id": "bad"}  # missing required fields
        first_response = json.dumps(bad_case, ensure_ascii=False)
        second_response = json.dumps(VALID_CASE_DICT, ensure_ascii=False)
        mock_instance = _make_sequential_mock_llm_client([first_response, second_response])
        MockLLMClient.return_value = mock_instance

        result = generate_case("测试背景", max_retries=1)
        assert isinstance(result, dict)
        assert result["case_id"] == "gen_test_001"

    @patch("core.case_generator.LLMClient")
    def test_calls_chat_completion_twice(self, MockLLMClient):
        """generate_case should call chat_completion exactly twice: once for
        the failed first attempt and once for the successful second attempt."""
        first_response = "not json"
        second_response = json.dumps(VALID_CASE_DICT, ensure_ascii=False)
        mock_instance = _make_sequential_mock_llm_client([first_response, second_response])
        MockLLMClient.return_value = mock_instance

        generate_case("测试背景", max_retries=1)
        assert mock_instance.chat_completion.call_count == 2
