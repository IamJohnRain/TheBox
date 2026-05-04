"""Tests for core.case_generator.generate_case handling of LLM failures.

Covers scenarios:
1. LLM returns a non-JSON string — generator retries and eventually raises ValidationError.
2. LLM returns valid JSON that fails schema validation — generator retries.
3. LLM returns valid JSON on the second attempt — generator succeeds.
4. LLM returns empty string or None.
5. LLM (reasoning model) returns <think>...</think> + JSON — generator strips think block.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from core.case_generator import generate_case
from core.exceptions import ContentFilterError, LLMResponseError, ValidationError


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


class TestGenerateCaseEmptyResponse:
    """Scenario 4: LLM returns empty string or None."""

    @patch("core.case_generator.LLMClient")
    def test_empty_string_raises_validation_error(self, MockLLMClient):
        """When the LLM returns an empty string, generate_case should
        exhaust its retries and raise a ValidationError."""
        mock_instance = _make_mock_llm_client("")
        MockLLMClient.return_value = mock_instance

        with pytest.raises(ValidationError, match="案件生成失败"):
            generate_case("测试背景", max_retries=1)

    @patch("core.case_generator.LLMClient")
    def test_empty_string_retries_correctly(self, MockLLMClient):
        """generate_case should retry (max_retries + 1) times when LLM returns empty."""
        max_retries = 2
        mock_instance = _make_mock_llm_client("")
        MockLLMClient.return_value = mock_instance

        with pytest.raises(ValidationError):
            generate_case("测试背景", max_retries=max_retries)

        expected_calls = max_retries + 1
        assert mock_instance.chat_completion.call_count == expected_calls

    @patch("core.case_generator.LLMClient")
    def test_none_content_raises_validation_error(self, MockLLMClient):
        """When chat_completion raises LLMResponseError for None content,
        generate_case should retry and raise ValidationError."""
        mock_client = MagicMock()
        mock_client.is_initialized = True
        mock_client.chat_completion.side_effect = LLMResponseError("LLM 返回空内容")
        MockLLMClient.return_value = mock_client

        with pytest.raises(ValidationError, match="案件生成失败"):
            generate_case("测试背景", max_retries=1)

    @patch("core.case_generator.LLMClient")
    def test_empty_then_valid_succeeds(self, MockLLMClient):
        """When first attempt returns empty and second returns valid JSON,
        generate_case should succeed."""
        mock_instance = _make_sequential_mock_llm_client(
            ["", json.dumps(VALID_CASE_DICT, ensure_ascii=False)]
        )
        MockLLMClient.return_value = mock_instance

        result = generate_case("测试背景", max_retries=1)
        assert isinstance(result, dict)
        assert result["case_id"] == "gen_test_001"


class TestGenerateCaseThinkBlock:
    """Scenario 5: LLM (reasoning model) returns <think>...</think> + JSON.

    MiniMax-M2.7 and other reasoning models prepend a <think>...</think>
    reasoning block before the actual JSON content.  generate_case must
    strip this block before attempting JSON parsing.
    """

    @patch("core.case_generator.LLMClient")
    def test_think_block_plus_plain_json(self, MockLLMClient):
        """When LLM returns <think>...</think> + plain JSON, generate_case
        should strip the think block and parse correctly."""
        think = "用户要求生成一个谋杀案...推理过程...让我来设计案件..."
        valid_json = json.dumps(VALID_CASE_DICT, ensure_ascii=False)
        response = f"<think>{think}</think>\n\n{valid_json}"
        mock_instance = _make_mock_llm_client(response)
        MockLLMClient.return_value = mock_instance

        result = generate_case("测试背景", max_retries=0)
        assert isinstance(result, dict)
        assert result["case_id"] == "gen_test_001"
        assert result["title"] == "测试案件"

    @patch("core.case_generator.LLMClient")
    def test_think_block_plus_code_fence_json(self, MockLLMClient):
        """When LLM returns <think>...</think> + ```json ... ```, generate_case
        should strip both the think block and the code fence, then parse correctly."""
        think = "让我仔细想想这个案件的设计..."
        valid_json = json.dumps(VALID_CASE_DICT, ensure_ascii=False)
        response = f"<think>{think}</think>\n\n```json\n{valid_json}\n```"
        mock_instance = _make_mock_llm_client(response)
        MockLLMClient.return_value = mock_instance

        result = generate_case("测试背景", max_retries=0)
        assert isinstance(result, dict)
        assert result["case_id"] == "gen_test_001"

    @patch("core.case_generator.LLMClient")
    def test_think_only_no_json_raises_validation_error(self, MockLLMClient):
        """When LLM returns only <think>...</think> with no JSON content,
        generate_case should retry and raise ValidationError."""
        think = "我需要更长时间思考..."
        response = f"<think>{think}</think>"
        mock_instance = _make_mock_llm_client(response)
        MockLLMClient.return_value = mock_instance

        with pytest.raises(ValidationError, match="案件生成失败"):
            generate_case("测试背景", max_retries=0)


class TestGenerateCaseContentFilter:
    """Scenario 6: LLM triggers content filter (422 UnprocessableEntityError).

    When the primary prompt triggers a ContentFilterError, generate_case
    should switch to the safe prompt and retry. If the safe prompt also
    triggers the filter, it should raise ValidationError.
    """

    @patch("core.case_generator.LLMClient")
    def test_content_filter_switches_to_safe_prompt(self, MockLLMClient):
        """When the first call triggers ContentFilterError, the second call
        uses the safe prompt and succeeds."""
        mock_client = MagicMock()
        mock_client.is_initialized = True
        mock_client.chat_completion.side_effect = [
            ContentFilterError("output new_sensitive (1027)"),
            json.dumps(VALID_CASE_DICT, ensure_ascii=False),
        ]
        MockLLMClient.return_value = mock_client

        result = generate_case("测试背景", max_retries=1)
        assert isinstance(result, dict)
        assert result["case_id"] == "gen_test_001"
        assert mock_client.chat_completion.call_count == 2

    @patch("core.case_generator.LLMClient")
    def test_safe_prompt_also_filtered_raises_validation_error(self, MockLLMClient):
        """When both prompts trigger ContentFilterError, generate_case
        should raise ValidationError."""
        mock_client = MagicMock()
        mock_client.is_initialized = True
        mock_client.chat_completion.side_effect = ContentFilterError("output new_sensitive (1027)")
        MockLLMClient.return_value = mock_client

        with pytest.raises(ValidationError, match="案件生成失败"):
            generate_case("测试背景", max_retries=1)

    @patch("core.case_generator.LLMClient")
    def test_safe_prompt_uses_different_system_message(self, MockLLMClient):
        """Verify that after ContentFilterError, the second call uses a
        different (safe) system prompt."""
        mock_client = MagicMock()
        mock_client.is_initialized = True
        mock_client.chat_completion.side_effect = [
            ContentFilterError("sensitive"),
            json.dumps(VALID_CASE_DICT, ensure_ascii=False),
        ]
        MockLLMClient.return_value = mock_client

        generate_case("测试背景", max_retries=1)

        calls = mock_client.chat_completion.call_args_list
        first_messages = calls[0][1]["messages"]
        second_messages = calls[1][1]["messages"]
        assert first_messages[0]["role"] == "system"
        assert second_messages[0]["role"] == "system"
        assert first_messages[0]["content"] != second_messages[0]["content"]


class TestGenerateCaseProgressCallback:
    """Scenario 7: progress_callback is called at each stage."""

    @patch("core.case_generator.LLMClient")
    def test_progress_callback_called_on_success(self, MockLLMClient):
        """progress_callback should be called at each stage during successful generation."""
        mock_client = _make_mock_llm_client(json.dumps(VALID_CASE_DICT, ensure_ascii=False))
        MockLLMClient.return_value = mock_client

        progress_messages = []
        generate_case("测试背景", max_retries=0, progress_callback=progress_messages.append)

        assert any("打造故事场景" in m for m in progress_messages)
        assert any("构思案件" in m for m in progress_messages)
        assert any("编织线索" in m for m in progress_messages)
        assert any("校验逻辑" in m for m in progress_messages)
        assert any("构建完成" in m for m in progress_messages)

    @patch("core.case_generator.LLMClient")
    def test_progress_callback_none_by_default(self, MockLLMClient):
        """generate_case should work without progress_callback (default None)."""
        mock_client = _make_mock_llm_client(json.dumps(VALID_CASE_DICT, ensure_ascii=False))
        MockLLMClient.return_value = mock_client

        result = generate_case("测试背景", max_retries=0)
        assert result["case_id"] == "gen_test_001"

    @patch("core.case_generator.LLMClient")
    def test_progress_callback_content_filter_switch(self, MockLLMClient):
        """progress_callback should receive safe mode message on ContentFilterError."""
        mock_client = MagicMock()
        mock_client.is_initialized = True
        mock_client.chat_completion.side_effect = [
            ContentFilterError("sensitive"),
            json.dumps(VALID_CASE_DICT, ensure_ascii=False),
        ]
        MockLLMClient.return_value = mock_client

        progress_messages = []
        generate_case("测试背景", max_retries=1, progress_callback=progress_messages.append)

        assert any("安全创作模式" in m for m in progress_messages)


class TestGenerateCaseSafeMode:
    """Scenario 8: safe_mode=True forces safe prompt from the start."""

    @patch("core.case_generator.LLMClient")
    def test_safe_mode_uses_safe_prompt(self, MockLLMClient):
        """When safe_mode=True, the first call should use the safe prompt."""
        mock_client = _make_mock_llm_client(json.dumps(VALID_CASE_DICT, ensure_ascii=False))
        MockLLMClient.return_value = mock_client

        generate_case("测试背景", max_retries=0, safe_mode=True)

        call_kwargs = mock_client.chat_completion.call_args
        messages = call_kwargs[1]["messages"] if "messages" in call_kwargs[1] else call_kwargs[0][0]
        system_content = messages[0]["content"]
        assert "逻辑谜题" in system_content or "逻辑推理解谜" in system_content

    @patch("core.case_generator.LLMClient")
    def test_safe_mode_progress_shows_safe_message(self, MockLLMClient):
        """When safe_mode=True, progress should show safe creation mode message."""
        mock_client = _make_mock_llm_client(json.dumps(VALID_CASE_DICT, ensure_ascii=False))
        MockLLMClient.return_value = mock_client

        progress_messages = []
        generate_case("测试背景", max_retries=0, safe_mode=True, progress_callback=progress_messages.append)

        assert any("安全创作模式" in m for m in progress_messages)
