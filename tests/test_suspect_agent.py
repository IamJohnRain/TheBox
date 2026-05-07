"""Tests for SuspectAgent LLM isolation (Phase 1b)."""

import json
from unittest.mock import patch, MagicMock

import pytest


class TestCallLLM:
    """Test _call_llm method."""

    def test_call_llm_returns_correct_format(self, mock_case_simple):
        """_call_llm should return dict with reply and secret_triggered."""
        from core.suspect_agent import SuspectAgent

        suspect_data = mock_case_simple["suspects"][0]
        agent = SuspectAgent(suspect_data, mock_case_simple["title"])

        mock_response = json.dumps({"reply": "测试回复", "secret_triggered": None})

        with patch("core.suspect_agent.llm_client") as mock_llm:
            mock_llm.is_initialized = True
            mock_llm.chat_completion.return_value = mock_response

            result = agent._call_llm("测试输入")

            assert "reply" in result
            assert "secret_triggered" in result
            assert result["reply"] == "测试回复"
            assert result["secret_triggered"] is None

    def test_call_llm_no_pressure_change(self, mock_case_simple):
        """_call_llm should NOT return pressure_change."""
        from core.suspect_agent import SuspectAgent

        suspect_data = mock_case_simple["suspects"][0]
        agent = SuspectAgent(suspect_data, mock_case_simple["title"])

        mock_response = json.dumps({"reply": "测试", "secret_triggered": None, "pressure_change": 10})

        with patch("core.suspect_agent.llm_client") as mock_llm:
            mock_llm.is_initialized = True
            mock_llm.chat_completion.return_value = mock_response

            result = agent._call_llm("测试")

            # pressure_change should not be in result even if LLM returns it
            assert "pressure_change" not in result

    def test_call_llm_uninitialized_returns_silent(self, mock_case_simple):
        """When LLM is not initialized, return silent response."""
        from core.suspect_agent import SuspectAgent

        suspect_data = mock_case_simple["suspects"][0]
        agent = SuspectAgent(suspect_data, mock_case_simple["title"])

        with patch("core.suspect_agent.llm_client") as mock_llm:
            mock_llm.is_initialized = False

            result = agent._call_llm("测试")

            assert result["reply"] == "（嫌疑人沉默不语）"
            assert result["secret_triggered"] is None


class TestDynamicSystemPrompt:
    """Test dynamic pressure in system prompt."""

    def test_system_message_uses_current_pressure(self, mock_case_simple):
        """_get_system_message should use current pressure value."""
        from core.suspect_agent import SuspectAgent

        suspect_data = mock_case_simple["suspects"][0]
        agent = SuspectAgent(suspect_data, mock_case_simple["title"])

        # Set specific pressure
        agent.pressure = 75

        msg = agent._get_system_message()

        assert "75" in msg["content"]
        assert msg["role"] == "system"

    def test_system_message_updates_with_pressure(self, mock_case_simple):
        """System message should reflect pressure changes."""
        from core.suspect_agent import SuspectAgent

        suspect_data = mock_case_simple["suspects"][0]
        agent = SuspectAgent(suspect_data, mock_case_simple["title"])

        agent.pressure = 30
        msg1 = agent._get_system_message()
        assert "30" in msg1["content"]

        agent.pressure = 80
        msg2 = agent._get_system_message()
        assert "80" in msg2["content"]


class TestRespondMethod:
    """Test respond method uses _call_llm."""

    def test_respond_no_pressure_change(self, mock_case_simple):
        """respond should not return pressure_change."""
        from core.suspect_agent import SuspectAgent

        suspect_data = mock_case_simple["suspects"][0]
        agent = SuspectAgent(suspect_data, mock_case_simple["title"])

        mock_response = json.dumps({"reply": "我是无辜的", "secret_triggered": None})

        with patch("core.suspect_agent.llm_client") as mock_llm:
            mock_llm.is_initialized = True
            mock_llm.chat_completion.return_value = mock_response

            result = agent.respond("你做了什么？")

            assert "reply" in result
            assert "pressure_change" not in result
