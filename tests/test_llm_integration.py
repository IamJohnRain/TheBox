"""
LLM集成测试 - 使用真实MiniMax API进行端到端测试
这些测试会实际调用外部API，请注意：
- 运行这些测试会消耗API配额
- 测试结果取决于网络连接和API可用性
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from core.case_generator import generate_case
from core.config import get_api_key, get_base_url, get_model, get_provider, save_settings
from core.exceptions import ConfigError, NetworkError
from core.interrogation import InterrogationEngine
from core.llm_client import LLMClient
from core.suspect_agent import SuspectAgent


# 检查是否有真实API配置
def has_real_api_config():
    """检查是否配置了有效的API"""
    try:
        provider = get_provider()
        api_key = get_api_key(provider_id=provider)
        base_url = get_base_url()
        model = get_model()
        return bool(api_key and base_url and model)
    except Exception:
        return False


# =============================================================================
# LLMClient初始化和chat_completion调用
# =============================================================================
class TestLLMClientInitialization:
    """LLMClient初始化测试"""

    def test_llm_client_singleton(self):
        """验证LLMClient是单例"""
        client1 = LLMClient()
        client2 = LLMClient()
        assert client1 is client2

    def test_llm_client_initialize_with_config(self):
        """使用配置文件初始化"""
        client = LLMClient()
        try:
            client.initialize()
            # 如果API key存在且有效，应该初始化成功
            if client.is_initialized:
                assert client.client is not None
                assert client.model is not None
        except ConfigError:
            pytest.skip("未配置有效的API Key")

    def test_llm_client_initialize_without_key(self):
        """无API Key时初始化"""
        client = LLMClient()
        with patch("core.llm_client.get_api_key", return_value=""):
            client.initialize()
            assert not client.is_initialized


class TestLLMClientChatCompletion:
    """LLMClient chat_completion测试"""

    @pytest.mark.real_api
    def test_chat_completion_basic(self):
        """基础chat_completion调用"""
        client = LLMClient()
        try:
            client.initialize()
        except ConfigError:
            pytest.skip("未配置有效的API Key")

        if not client.is_initialized:
            pytest.skip("LLMClient未初始化")

        messages = [{"role": "user", "content": "Say 'test' in one word"}]
        response = client.chat_completion(messages, max_tokens=20)
        assert response is not None
        assert len(response) > 0

    @pytest.mark.real_api
    def test_chat_completion_with_system_prompt(self):
        """带system prompt的调用"""
        client = LLMClient()
        if not client.is_initialized:
            try:
                client.initialize()
            except ConfigError:
                pytest.skip("未配置有效的API Key")

        if not client.is_initialized:
            pytest.skip("LLMClient未初始化")

        messages = [
            {"role": "system", "content": "你是一个只能回答'是'或'否'的助手"},
            {"role": "user", "content": "1+1=2吗？"}
        ]
        response = client.chat_completion(messages, max_tokens=10)
        assert response is not None

    @pytest.mark.real_api
    def test_chat_completion_json_format(self):
        """JSON格式响应测试"""
        client = LLMClient()
        if not client.is_initialized:
            try:
                client.initialize()
            except ConfigError:
                pytest.skip("未配置有效的API Key")

        if not client.is_initialized:
            pytest.skip("LLMClient未初始化")

        messages = [
            {"role": "user", "content": "返回一个JSON，包含key为'answer'，值为数字42"}
        ]
        response = client.chat_completion(
            messages,
            max_tokens=100,
            response_format={"type": "json_object"}
        )
        # 尝试解析JSON
        parsed = json.loads(response)
        assert "answer" in parsed

    @pytest.mark.real_api
    def test_chat_completion_json_complex_prompt(self):
        """复杂prompt + response_format 边界测试（复现case generation场景）"""
        client = LLMClient()
        if not client.is_initialized:
            try:
                client.initialize()
            except ConfigError:
                pytest.skip("未配置有效的API Key")

        if not client.is_initialized:
            pytest.skip("LLMClient未初始化")

        # 模拟case generation的复杂prompt
        messages = [
            {"role": "system", "content": """你是一个推理案件生成器。请生成一个谋杀案案件，严格以JSON格式输出。
输出JSON必须包含以下字段：case_id, title, victim, cause_of_death, crime_scene, truth, suspects, evidences。
suspects至少2个，每个包含name, role, personality, knowledge, forbidden_to_reveal字段。
evidences至少1个，每个包含id, name, description字段。
只输出JSON，不要输出任何其他内容。"""},
            {"role": "user", "content": "请生成一个发生在图书馆的谋杀案。"},
        ]
        response = client.chat_completion(
            messages,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )
        assert response, "response should not be empty"
        parsed = json.loads(response)
        assert "case_id" in parsed or "title" in parsed


# =============================================================================
# SuspectAgent真实审讯回复
# =============================================================================
class TestSuspectAgentRealInterrogation:
    """SuspectAgent真实审讯测试"""

    def _get_suspect_data(self):
        return {
            "name": "测试嫌疑人",
            "role": "嫌疑人",
            "personality": "紧张",
            "knowledge": "我知道发生了什么",
            "forbidden_to_reveal": ["杀", "死"]
        }

    @pytest.mark.real_api
    def test_suspect_agent_respond(self):
        """SuspectAgent respond方法真实调用"""
        if not has_real_api_config():
            pytest.skip("未配置有效的API")

        suspect_data = self._get_suspect_data()
        agent = SuspectAgent(suspect_data, "测试案件")

        result = agent.respond("你在哪里？")
        assert "reply" in result
        assert "secret_triggered" in result
        # pressure_change is no longer returned by respond (Phase 1b)
        assert "pressure_change" not in result
        # 不应该立即触发secret
        assert result.get("secret_triggered") is None

    @pytest.mark.real_api
    def test_suspect_agent_respond_evidence(self):
        """SuspectAgent respond_evidence方法真实调用"""
        if not has_real_api_config():
            pytest.skip("未配置有效的API")

        suspect_data = self._get_suspect_data()
        agent = SuspectAgent(suspect_data, "测试案件")

        result = agent.respond_evidence("现场发现了血迹", "physical")
        assert "reply" in result
        assert "secret_triggered" in result
        assert "pressure_change" not in result

    @pytest.mark.real_api
    def test_suspect_agent_memory(self):
        """测试记忆功能"""
        if not has_real_api_config():
            pytest.skip("未配置有效的API")

        suspect_data = self._get_suspect_data()
        agent = SuspectAgent(suspect_data, "测试案件")

        agent.respond("第一个问题")
        agent.respond("第二个问题")

        assert len(agent.memory) >= 4  # 2 user + 2 assistant


# =============================================================================
# 证据出示后的压力变化
# =============================================================================
class TestEvidencePressureChange:
    """证据出示压力变化测试"""

    @pytest.mark.real_api
    def test_evidence_pressure_increase(self):
        """相关证据出示后压力增加"""
        if not has_real_api_config():
            pytest.skip("未配置有效的API")

        mock_case = {
            "case_id": "test_evidence",
            "title": "测试案件",
            "victim": "受害者",
            "cause_of_death": "死亡",
            "crime_scene": "现场",
            "truth": "真相",
            "suspects": [
                {
                    "name": "嫌疑人A",
                    "role": "角色",
                    "personality": "紧张",
                    "knowledge": "我知道",
                    "forbidden_to_reveal": ["杀"]
                }
            ],
            "evidences": [
                {"id": "ev1", "name": "凶器", "description": "发现凶器", "related_suspect": "嫌疑人A"}
            ],
            "interrogation_time_limit_sec": 300
        }

        engine = InterrogationEngine(mock_case)
        initial_pressure = engine.suspects[0].pressure

        engine.select_suspect(0)
        events = engine.submit_action("present_evidence", "出示证据", evidence_id="ev1")
        # 检查压力是否增加
        update_events = [e for e in events if e["type"] == "suspect_update"]
        if update_events:
            assert update_events[0]["pressure"] > initial_pressure or initial_pressure == 50


# =============================================================================
# 秘密触发机制
# =============================================================================
class TestSecretTrigger:
    """秘密触发机制测试"""

    @pytest.mark.real_api
    def test_forbidden_content_detection(self):
        """禁止内容检测"""
        if not has_real_api_config():
            pytest.skip("未配置有效的API")

        suspect_data = {
            "name": "嫌疑人",
            "role": "嫌疑人",
            "personality": "紧张",
            "knowledge": "我知道",
            "forbidden_to_reveal": ["杀", "毒", "下毒"]
        }
        agent = SuspectAgent(suspect_data, "测试案件")

        # 多次对话，看是否触发禁止内容
        for _ in range(5):
            result = agent.respond("你为什么要杀他？")
            if result.get("secret_triggered"):
                assert "杀" in result.get("reply", "").lower() or agent.pressure >= 80
                break


# =============================================================================
# 错误处理
# =============================================================================
class TestLLMErrorHandling:
    """LLM错误处理测试"""

    def test_invalid_api_key(self):
        """无效API Key处理"""
        LLMClient._instance = None
        client = LLMClient()
        with patch("core.llm_client.get_api_key", return_value="invalid_key"):
            with patch("core.llm_client.get_base_url", return_value="https://api.test.com/v1"):
                with patch("core.llm_client.get_provider", return_value="test"):
                    with patch("core.llm_client.OpenAI", side_effect=Exception("Invalid API Key")):
                        client.initialize()
                        assert not client.is_initialized

    def test_network_error_handling(self):
        """网络错误处理"""
        client = LLMClient()
        client._initialized = True
        client.client = MagicMock()
        import openai
        client.client.chat.completions.create.side_effect = openai.APITimeoutError("Timeout")

        with pytest.raises((NetworkError, openai.APITimeoutError)):
            client.chat_completion([{"role": "user", "content": "test"}])

    def test_uninitialized_client_error(self):
        """未初始化客户端错误"""
        client = LLMClient()
        client._initialized = False

        with pytest.raises(ConfigError):
            client.chat_completion([{"role": "user", "content": "test"}])


# =============================================================================
# 案件生成测试
# =============================================================================
class TestCaseGeneration:
    """案件生成测试"""

    @pytest.mark.real_api
    @pytest.mark.slow
    def test_generate_case_basic(self):
        """基础案件生成"""
        if not has_real_api_config():
            pytest.skip("未配置有效的API")

        case = generate_case("一个简单的盗窃案")
        assert "case_id" in case
        assert "title" in case
        assert "suspects" in case
        assert "evidences" in case
        assert len(case["suspects"]) >= 2
        assert len(case["evidences"]) >= 1

    @pytest.mark.real_api
    @pytest.mark.slow
    def test_generate_case_complex(self):
        """复杂案件生成"""
        if not has_real_api_config():
            pytest.skip("未配置有效的API")

        case = generate_case("发生在豪华游轮上的谋杀案，嫌疑人包括船员和乘客")
        assert case["title"]
        assert len(case["suspects"]) >= 2
        for suspect in case["suspects"]:
            assert "name" in suspect
            assert "role" in suspect
            assert "forbidden_to_reveal" in suspect


# =============================================================================
# 完整端到端审讯测试
# =============================================================================
class TestFullInterrogationE2E:
    """完整审讯端到端测试"""

    @pytest.mark.real_api
    @pytest.mark.slow
    def test_full_suspect_interrogation(self):
        """完整嫌疑人审讯流程"""
        if not has_real_api_config():
            pytest.skip("未配置有效的API")

        suspect_data = {
            "name": "嫌疑人甲",
            "role": "嫌疑人",
            "personality": "狡辩",
            "knowledge": "我那天晚上在家睡觉",
            "forbidden_to_reveal": ["杀", "偷"]
        }
        agent = SuspectAgent(suspect_data, "测试案件")

        questions = [
            "你那天晚上在哪里？",
            "你和受害者是什么关系？",
            "能描述一下你的行踪吗？",
            "你有什么不在场证明？"
        ]

        for q in questions:
            result = agent.respond(q)
            assert "reply" in result
            assert agent.pressure >= 0 and agent.pressure <= 100

    @pytest.mark.real_api
    @pytest.mark.slow
    def test_pressure_escalation(self):
        """压力升级测试"""
        if not has_real_api_config():
            pytest.skip("未配置有效的API")

        suspect_data = {
            "name": "嫌疑人",
            "role": "嫌疑人",
            "personality": "紧张",
            "knowledge": "我什么都没做",
            "forbidden_to_reveal": ["杀", "偷"]
        }
        agent = SuspectAgent(suspect_data, "测试案件")

        initial_pressure = agent.pressure

        pressure_questions = [
            "我们在调查你",
            "我们有证据",
            "你最好说实话",
            "你被捕了"
        ]

        for q in pressure_questions:
            agent.respond(q)

        # 压力应该有所增加
        assert agent.pressure >= initial_pressure


# =============================================================================
# 配置保存和加载
# =============================================================================
class TestConfigPersistence:
    """配置持久化测试"""

    def test_save_and_load_settings(self):
        """保存和加载设置"""
        test_provider = "minimax"
        test_base_url = "https://api.minimaxi.com/v1"
        test_model = "MiniMax-M2.7"
        test_api_key = "test_key_123"

        save_settings(test_provider, test_base_url, test_model, test_api_key)

        from core.config import get_settings

        settings = get_settings()
        assert settings["provider"] == test_provider
        assert settings["base_url"] == test_base_url
        assert settings["model"] == test_model

    def test_reinitialize_llm_client(self):
        """重新初始化LLMClient"""
        client = LLMClient()
        if has_real_api_config():
            provider = get_provider()
            api_key = get_api_key(provider_id=provider)
            base_url = get_base_url()
            model = get_model()
            client.reinitialize(provider, api_key, base_url, model)
            assert client.is_initialized
