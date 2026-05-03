"""审讯复盘报告生成器测试。"""

import pytest

from core.review_generator import _fallback_review, generate_review


class TestFallbackReview:
    """降级复盘（LLM 不可用时的兜底）。"""

    def test_breakdown_state_returns_high_score(self):
        """破案成功时分数较高。"""
        engine_state = {"state": "breakdown", "suspects_states": []}
        case_data = {}
        result = _fallback_review(engine_state, case_data)
        assert result["score"] >= 70
        assert "突破" in result["strategy_analysis"]

    def test_verdict_state_returns_low_score(self):
        """时间耗尽时分数较低。"""
        engine_state = {"state": "verdict", "suspects_states": []}
        case_data = {}
        result = _fallback_review(engine_state, case_data)
        assert result["score"] <= 50
        assert "未能" in result["strategy_analysis"]

    def test_result_has_all_required_keys(self):
        """降级复盘结果包含所有必要字段。"""
        engine_state = {"state": "breakdown", "suspects_states": []}
        case_data = {}
        result = _fallback_review(engine_state, case_data)
        for key in ("score", "strategy_analysis", "key_moments", "suggestions", "verdict"):
            assert key in result, f"Missing key: {key}"

    def test_score_is_int(self):
        """分数是整数。"""
        engine_state = {"state": "breakdown", "suspects_states": []}
        case_data = {}
        result = _fallback_review(engine_state, case_data)
        assert isinstance(result["score"], int)

    def test_key_moments_is_list(self):
        """key_moments 是列表。"""
        engine_state = {"state": "breakdown", "suspects_states": []}
        case_data = {}
        result = _fallback_review(engine_state, case_data)
        assert isinstance(result["key_moments"], list)

    def test_suggestions_is_list(self):
        """suggestions 是列表。"""
        engine_state = {"state": "verdict", "suspects_states": []}
        case_data = {}
        result = _fallback_review(engine_state, case_data)
        assert isinstance(result["suggestions"], list)


class TestGenerateReviewFallback:
    """generate_review 在 LLM 未初始化时的降级行为。"""

    def test_llm_not_initialized_returns_fallback(self, monkeypatch):
        """LLMClient 未初始化时返回降级复盘。"""
        import core.review_generator as mod

        monkeypatch.setattr(mod.llm_client, "_initialized", False)
        engine_state = {"state": "breakdown", "suspects_states": []}
        case_data = {"title": "测试案件"}
        result = generate_review(engine_state, case_data)
        assert result is not None
        assert result["score"] >= 70

    def test_llm_exception_returns_fallback(self, monkeypatch):
        """LLM 调用异常时返回降级复盘。"""
        import core.review_generator as mod

        monkeypatch.setattr(mod.llm_client, "_initialized", True)

        def mock_chat_completion(**kwargs):
            raise RuntimeError("LLM error")

        monkeypatch.setattr(
            mod.llm_client, "chat_completion", mock_chat_completion
        )
        engine_state = {"state": "verdict", "suspects_states": []}
        case_data = {"title": "测试案件"}
        result = generate_review(engine_state, case_data)
        assert result is not None
        assert result["score"] <= 50


class TestGenerateReviewSuccess:
    """generate_review 在 LLM 正常时的行为。"""

    def test_llm_returns_valid_json(self, monkeypatch):
        """LLM 返回有效 JSON 时正常解析。"""
        import core.review_generator as mod
        import json

        monkeypatch.setattr(mod.llm_client, "_initialized", True)

        mock_result = {
            "score": 85,
            "strategy_analysis": "审讯策略得当",
            "key_moments": ["关键证据出示时机"],
            "suggestions": ["应更早施压"],
            "verdict": "审讯成功",
        }

        def mock_chat_completion(**kwargs):
            return json.dumps(mock_result)

        monkeypatch.setattr(
            mod.llm_client, "chat_completion", mock_chat_completion
        )
        engine_state = {
            "state": "breakdown",
            "time_left": 300,
            "presented_evidence_ids": ["e1"],
            "suspects_states": [
                {"name": "张三", "pressure": 80, "memory": ["a", "b"]}
            ],
        }
        case_data = {"title": "测试案件", "interrogation_time_limit_sec": 600}
        result = generate_review(engine_state, case_data)
        assert result is not None
        assert result["score"] == 85
        assert result["strategy_analysis"] == "审讯策略得当"

    def test_llm_returns_score_as_string(self, monkeypatch):
        """LLM 返回 score 为字符串时能转换为 int。"""
        import core.review_generator as mod
        import json

        monkeypatch.setattr(mod.llm_client, "_initialized", True)

        mock_result = {
            "score": "75",
            "strategy_analysis": "尚可",
            "key_moments": [],
            "suggestions": [],
            "verdict": "及格",
        }

        def mock_chat_completion(**kwargs):
            return json.dumps(mock_result)

        monkeypatch.setattr(
            mod.llm_client, "chat_completion", mock_chat_completion
        )
        engine_state = {"state": "breakdown", "suspects_states": []}
        case_data = {"title": "测试案件", "interrogation_time_limit_sec": 600}
        result = generate_review(engine_state, case_data)
        assert result is not None
        assert isinstance(result["score"], int)
        assert result["score"] == 75

    def test_llm_missing_fields_get_defaults(self, monkeypatch):
        """LLM 返回 JSON 缺少字段时使用默认值。"""
        import core.review_generator as mod
        import json

        monkeypatch.setattr(mod.llm_client, "_initialized", True)

        mock_result = {"score": 60}

        def mock_chat_completion(**kwargs):
            return json.dumps(mock_result)

        monkeypatch.setattr(
            mod.llm_client, "chat_completion", mock_chat_completion
        )
        engine_state = {"state": "breakdown", "suspects_states": []}
        case_data = {"title": "测试案件", "interrogation_time_limit_sec": 600}
        result = generate_review(engine_state, case_data)
        assert result is not None
        assert result["strategy_analysis"] == ""
        assert result["key_moments"] == []
        assert result["suggestions"] == []
        assert result["verdict"] == ""
