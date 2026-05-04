import json
import tracemalloc
from unittest.mock import MagicMock, patch

import pytest

from core.exceptions import LLMResponseError, NetworkError
from core.suspect_agent import SuspectAgent

SUSPECT_DATA = {
    "name": "张伟",
    "role": "被害人的商业合伙人",
    "personality": "表面冷静，内心焦虑，说话常回避重点",
    "knowledge": "知道被害人有巨额保险，与被害人有过争执",
    "forbidden_to_reveal": ["我是凶手", "我杀了他"],
}

CASE_TITLE = "富商离奇死亡案"


def _make_agent() -> SuspectAgent:
    return SuspectAgent(SUSPECT_DATA, CASE_TITLE)


def _mock_llm_response(reply: str, pressure_change: int = 0, secret_triggered=None) -> MagicMock:
    mock_client = MagicMock()
    mock_client.is_initialized = True
    raw = json.dumps(
        {"reply": reply, "pressure_change": pressure_change, "secret_triggered": secret_triggered},
        ensure_ascii=False,
    )
    mock_client.chat_completion.return_value = raw
    return mock_client


class TestForbiddenNotLeaked:
    """Verify forbidden substrings never appear in replies after post-processing."""

    @patch("core.suspect_agent.llm_client")
    def test_forbidden_not_leaked(self, mock_llm):
        dangerous_replies = [
            "是的，我是凶手，你猜对了。",
            "好吧我承认我杀了他。",
            "我确实就是凶手啊。",
            "那天晚上我杀了他，用刀。",
            "我完全不知道你在说什么。",
        ]
        mock_llm.is_initialized = True
        for reply_text in dangerous_replies:
            raw = json.dumps(
                {"reply": reply_text, "pressure_change": 5, "secret_triggered": None},
                ensure_ascii=False,
            )
            mock_llm.chat_completion.return_value = raw
            agent = _make_agent()
            result = agent.respond("凶手就是你吧？")
            for forbidden in SUSPECT_DATA["forbidden_to_reveal"]:
                assert forbidden.lower() not in result["reply"].lower()

    @pytest.mark.real_api
    def test_forbidden_not_leaked_real_api(self):
        pytest.skip("需要真实 API Key，默认跳过")


class TestPressureChange:
    """Verify pressure changes correctly on evidence presentation."""

    @patch("core.suspect_agent.llm_client")
    def test_pressure_change_on_evidence(self, mock_llm):
        mock_llm.is_initialized = True
        raw = json.dumps(
            {"reply": "这不可能！", "pressure_change": 30, "secret_triggered": None},
            ensure_ascii=False,
        )
        mock_llm.chat_completion.return_value = raw
        agent = _make_agent()
        assert agent.pressure == 50
        agent.respond("这是你在案发现场的监控截图。")
        assert agent.pressure == 80


class TestPressureClamped:
    """Verify pressure stays within 0-100 range."""

    @patch("core.suspect_agent.llm_client")
    def test_pressure_clamped_upper(self, mock_llm):
        mock_llm.is_initialized = True
        raw = json.dumps(
            {"reply": "我受不了了！", "pressure_change": 80, "secret_triggered": None},
            ensure_ascii=False,
        )
        mock_llm.chat_completion.return_value = raw
        agent = _make_agent()
        agent.pressure = 90
        agent.respond("证据确凿！")
        assert agent.pressure == 100

    @patch("core.suspect_agent.llm_client")
    def test_pressure_clamped_lower(self, mock_llm):
        mock_llm.is_initialized = True
        raw = json.dumps(
            {"reply": "谢谢你相信我。", "pressure_change": -60, "secret_triggered": None},
            ensure_ascii=False,
        )
        mock_llm.chat_completion.return_value = raw
        agent = _make_agent()
        agent.pressure = 10
        agent.respond("我相信你是无辜的。")
        assert agent.pressure == 0


class TestMemoryLimit:
    """Verify memory does not exceed the configured turn limit."""

    @patch("core.suspect_agent.llm_client")
    def test_memory_limit(self, mock_llm):
        mock_llm.is_initialized = True
        raw = json.dumps(
            {"reply": "嗯。", "pressure_change": 0, "secret_triggered": None},
            ensure_ascii=False,
        )
        mock_llm.chat_completion.return_value = raw
        agent = _make_agent()
        for i in range(20):
            agent.respond(f"问题{i}")
        assert len(agent.memory) <= 20


class TestNoMemoryLeak:
    """Verify no significant memory growth over many iterations."""

    @patch("core.suspect_agent.llm_client")
    def test_no_memory_leak(self, mock_llm):
        mock_llm.is_initialized = True
        raw = json.dumps(
            {"reply": "嗯。", "pressure_change": 0, "secret_triggered": None},
            ensure_ascii=False,
        )
        mock_llm.chat_completion.return_value = raw
        agent = _make_agent()
        for _ in range(12):
            agent.respond("热身问题")
        tracemalloc.start()
        snapshot1 = tracemalloc.take_snapshot()
        for _ in range(100):
            agent.respond("反复提问")
        snapshot2 = tracemalloc.take_snapshot()
        tracemalloc.stop()
        stats = snapshot2.compare_to(snapshot1, "lineno")
        total_growth = sum(stat.size_diff for stat in stats)
        baseline = sum(stat.size for stat in snapshot1.statistics("lineno"))
        if baseline > 0:
            growth_pct = total_growth / baseline * 100
            assert growth_pct < 10, f"内存增长 {growth_pct:.1f}% 超过 10% 阈值"


class TestRespondWithoutApiKey:
    """Verify default reply when LLMClient is not initialized."""

    @patch("core.suspect_agent.llm_client")
    def test_respond_without_api_key(self, mock_llm):
        mock_llm.is_initialized = False
        agent = _make_agent()
        result = agent.respond("你做了什么？")
        assert result["reply"] == "（嫌疑人沉默不语）"
        assert result["pressure_change"] == 0
        assert result["secret_triggered"] is None


class TestNetworkErrorFallback:
    """Verify fallback reply on network or LLM errors."""

    @patch("core.suspect_agent.llm_client")
    def test_network_error_fallback(self, mock_llm):
        mock_llm.is_initialized = True
        mock_llm.chat_completion.side_effect = NetworkError("连接失败")
        agent = _make_agent()
        result = agent.respond("你在哪里？")
        assert result["reply"] == "（对方沉默不语）"
        assert result["pressure_change"] == 0

    @patch("core.suspect_agent.llm_client")
    def test_llm_error_fallback(self, mock_llm):
        mock_llm.is_initialized = True
        mock_llm.chat_completion.side_effect = LLMResponseError("调用失败")
        agent = _make_agent()
        result = agent.respond("说说看？")
        assert result["reply"] == "（对方沉默不语）"
        assert result["pressure_change"] == 0


class TestTruncateMemory:
    """Verify truncate_memory keeps only the last N turns."""

    def test_truncate_memory(self):
        agent = _make_agent()
        for i in range(15):
            agent.memory.append({"role": "user", "content": f"u{i}"})
            agent.memory.append({"role": "assistant", "content": f"a{i}"})
        assert len(agent.memory) == 30
        agent.truncate_memory(10)
        assert len(agent.memory) == 20
        assert agent.memory[0]["content"] == "u5"


class TestSuspectAgentThinkBlock:
    """SuspectAgent handling of <think>...</think> blocks from reasoning models."""

    def _make_suspect_data(self):
        return {
            "name": "测试嫌疑人",
            "role": "嫌疑人",
            "personality": "紧张",
            "knowledge": "我知道发生了什么",
            "forbidden_to_reveal": ["杀", "死"],
        }

    @patch("core.suspect_agent.llm_client")
    def test_respond_with_think_and_json(self, mock_llm):
        """When LLM returns <think>...</think> + valid JSON, respond should parse correctly."""
        mock_llm.is_initialized = True
        mock_llm.chat_completion.return_value = (
            '<think>The suspect is nervous...推理...</think>\n\n'
            '{"reply": "我不知道你在说什么", "pressure_change": 1, "secret_triggered": null}'
        )

        agent = SuspectAgent(self._make_suspect_data(), "测试案件")
        result = agent.respond("你在哪里？")

        assert result["reply"] == "我不知道你在说什么"
        assert result["pressure_change"] == 1
        assert result.get("secret_triggered") is None

    @patch("core.suspect_agent.llm_client")
    def test_respond_with_think_only_fallback(self, mock_llm):
        """When LLM returns only <think>...}} with no JSON, respond should fallback to silence."""
        mock_llm.is_initialized = True
        mock_llm.chat_completion.return_value = (
            '<think>I need to think more about this...但我不确定...</think>'
        )

        agent = SuspectAgent(self._make_suspect_data(), "测试案件")
        result = agent.respond("你在哪里？")

        # Should fallback to silence (JSONDecodeError caught)
        assert "沉默" in result["reply"] or result["reply"] == "（嫌疑人沉默不语）"
        assert result["pressure_change"] == 0
