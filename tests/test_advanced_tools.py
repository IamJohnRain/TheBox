"""Tests for advanced tools - Phase 3c."""

from unittest.mock import patch


class TestLieDetector:
    """Test lie detector tool."""

    def test_lie_detector_no_knowledge_leak(self, mock_engine):
        """Lie detector should not receive suspect knowledge."""
        from core.tools import get_tool

        tool = get_tool("lie_detector")
        suspect = mock_engine.suspects[0]
        suspect.memory = [
            {"role": "user", "content": "你做了什么？"},
            {"role": "assistant", "content": "我什么都没做"},
        ]

        with patch("core.tools.lie_detector.llm_client") as mock_llm:
            mock_llm.is_initialized = True
            mock_llm.chat_completion.return_value = (
                '{"result": "uncertain", "confidence": 50, "reason": "无法判断"}'
            )

            tool.execute(mock_engine, suspect, "")

            # Check that knowledge is NOT in the prompt
            call_args = mock_llm.chat_completion.call_args
            messages = call_args[1].get("messages", call_args[0][0] if call_args[0] else [])
            prompt = ""
            if isinstance(messages, list) and messages:
                prompt = messages[0].get("content", "")
            elif isinstance(messages, dict):
                prompt = messages.get("content", "")

            # Knowledge should not appear in prompt
            assert "我讨厌老张" not in prompt  # knowledge from simple.json

    def test_lie_detector_returns_analysis(self, mock_engine):
        """Lie detector should return analysis message."""
        from core.tools import get_tool

        tool = get_tool("lie_detector")
        suspect = mock_engine.suspects[0]
        suspect.memory = [{"role": "assistant", "content": "我什么都没做"}]

        with patch("core.tools.lie_detector.llm_client") as mock_llm:
            mock_llm.is_initialized = True
            mock_llm.chat_completion.return_value = (
                '{"result": "deceptive", "confidence": 70, "reason": "回避问题"}'
            )

            events = tool.execute(mock_engine, suspect, "")

            assert len(events) == 1
            assert "测谎仪" in events[0]["content"]
            assert "疑似虚假" in events[0]["content"]

    def test_lie_detector_no_reply(self, mock_engine):
        """Lie detector with no assistant reply should return no-analysis message."""
        from core.tools import get_tool

        tool = get_tool("lie_detector")
        suspect = mock_engine.suspects[0]
        suspect.memory = [{"role": "user", "content": "你好"}]

        events = tool.execute(mock_engine, suspect, "")

        assert len(events) == 1
        assert "没有可分析" in events[0]["content"]

    def test_lie_detector_llm_failure(self, mock_engine):
        """Lie detector should handle LLM failure gracefully."""
        from core.tools import get_tool

        tool = get_tool("lie_detector")
        suspect = mock_engine.suspects[0]
        suspect.memory = [{"role": "assistant", "content": "我什么都没做"}]

        with patch("core.tools.lie_detector.llm_client") as mock_llm:
            mock_llm.is_initialized = True
            mock_llm.chat_completion.side_effect = Exception("LLM failed")

            events = tool.execute(mock_engine, suspect, "")

            assert len(events) == 1
            assert "测谎仪" in events[0]["content"]
            assert "失败" in events[0]["content"]


class TestThreat:
    """Test threat tool."""

    def test_threat_increases_pressure(self, mock_engine):
        """Threat should increase pressure by 20."""
        from core.tools import get_tool

        tool = get_tool("threat")
        suspect = mock_engine.suspects[0]
        initial_pressure = suspect.pressure

        tool.execute(mock_engine, suspect, "你最好说实话")

        assert suspect.pressure == min(100, initial_pressure + 20)

    def test_threat_high_pressure_silence(self, mock_engine):
        """High pressure should cause suspect to be silent."""
        from core.tools import get_tool

        tool = get_tool("threat")
        suspect = mock_engine.suspects[0]
        suspect.pressure = 60  # Will become 80 after threat

        events = tool.execute(mock_engine, suspect, "你最好说实话")

        # Should have silence response
        suspect_msgs = [e for e in events if e.get("suspect_name")]
        assert any("沉默" in e.get("content", "") for e in suspect_msgs)

    def test_threat_low_pressure_responds(self, mock_engine):
        """Low pressure should cause suspect to respond normally."""
        from core.tools import get_tool

        tool = get_tool("threat")
        suspect = mock_engine.suspects[0]
        suspect.pressure = 30  # Will become 50 after threat, still below 70

        events = tool.execute(mock_engine, suspect, "你最好说实话")

        # Should have a suspect response (from mock)
        suspect_msgs = [e for e in events if e.get("suspect_name")]
        assert len(suspect_msgs) == 1

    def test_threat_returns_player_message(self, mock_engine):
        """Threat should include the player's threat message."""
        from core.tools import get_tool

        tool = get_tool("threat")
        suspect = mock_engine.suspects[0]

        events = tool.execute(mock_engine, suspect, "老实交代！")

        player_msgs = [e for e in events if e.get("role") == "player"]
        assert len(player_msgs) == 1
        assert "[威胁]" in player_msgs[0]["content"]
        assert "老实交代" in player_msgs[0]["content"]


class TestDualInterrogation:
    """Test dual interrogation tool."""

    def test_dual_increases_pressure(self, mock_engine):
        """Dual interrogation should increase current suspect pressure."""
        from core.tools import get_tool

        tool = get_tool("dual_interrogation")
        suspect = mock_engine.suspects[0]
        initial_pressure = suspect.pressure

        tool.execute(mock_engine, suspect, "")

        assert suspect.pressure == min(100, initial_pressure + 20)

    def test_dual_checks_loyalty(self, mock_engine):
        """Dual interrogation should check other suspect loyalty."""
        from core.tools import get_tool

        tool = get_tool("dual_interrogation")
        suspect = mock_engine.suspects[0]
        other = mock_engine.suspects[1]

        # Set other suspect pressure > loyalty
        other.pressure = 80
        other.loyalty = 50

        events = tool.execute(mock_engine, suspect, "")

        # Should have loyalty hint
        assert any("忠诚度" in e.get("content", "") for e in events)

    def test_dual_no_loyalty_hint_when_stable(self, mock_engine):
        """No loyalty hint when other suspect is stable (pressure <= loyalty)."""
        from core.tools import get_tool

        tool = get_tool("dual_interrogation")
        suspect = mock_engine.suspects[0]
        other = mock_engine.suspects[1]

        # Set other suspect pressure <= loyalty
        other.pressure = 30
        other.loyalty = 80

        events = tool.execute(mock_engine, suspect, "")

        # Should NOT have loyalty hint
        assert not any("忠诚度" in e.get("content", "") for e in events)

    def test_dual_other_suspect_responds(self, mock_engine):
        """Dual interrogation should get the other suspect's response."""
        from core.tools import get_tool

        tool = get_tool("dual_interrogation")
        suspect = mock_engine.suspects[0]

        events = tool.execute(mock_engine, suspect, "")

        # Should have a suspect message from the other suspect
        suspect_msgs = [e for e in events if e.get("role") == "suspect"]
        assert len(suspect_msgs) == 1
        other_name = mock_engine.suspects[1].name
        assert suspect_msgs[0]["suspect_name"] == other_name


class TestPsychCollapse:
    """Test psychological collapse tool."""

    def test_psych_collapse_increases_level(self, mock_engine):
        """Psych collapse should increase confession level."""
        from core.tools import get_tool

        tool = get_tool("psych_collapse")
        suspect = mock_engine.suspects[0]
        suspect.confession_level = 0

        tool.execute(mock_engine, suspect, "")

        assert suspect.confession_level == 1

    def test_psych_collapse_max_level_4(self, mock_engine):
        """Psych collapse should not exceed level 4."""
        from core.tools import get_tool

        tool = get_tool("psych_collapse")
        suspect = mock_engine.suspects[0]
        suspect.confession_level = 4

        tool.execute(mock_engine, suspect, "")

        assert suspect.confession_level == 4

    def test_psych_collapse_sets_pressure_to_100(self, mock_engine):
        """Psych collapse should set pressure to 100."""
        from core.tools import get_tool

        tool = get_tool("psych_collapse")
        suspect = mock_engine.suspects[0]
        suspect.pressure = 30

        tool.execute(mock_engine, suspect, "")

        assert suspect.pressure == 100

    def test_psych_collapse_returns_system_message(self, mock_engine):
        """Psych collapse should return system message about level change."""
        from core.tools import get_tool

        tool = get_tool("psych_collapse")
        suspect = mock_engine.suspects[0]
        suspect.confession_level = 0

        events = tool.execute(mock_engine, suspect, "")

        system_msgs = [e for e in events if e.get("role") == "system"]
        assert len(system_msgs) >= 1
        assert "心理崩溃" in system_msgs[0]["content"]

    def test_psych_collapse_confession_update_event(self, mock_engine):
        """Psych collapse should emit ConfessionUpdateEvent when level changes."""
        from core.tools import get_tool

        tool = get_tool("psych_collapse")
        suspect = mock_engine.suspects[0]
        suspect.confession_level = 0

        events = tool.execute(mock_engine, suspect, "")

        confession_events = [e for e in events if e.get("type") == "confession_update"]
        assert len(confession_events) == 1
        assert confession_events[0]["confession_level"] == 1

    def test_psych_collapse_no_confession_event_at_max(self, mock_engine):
        """Psych collapse at max level should not emit ConfessionUpdateEvent."""
        from core.tools import get_tool

        tool = get_tool("psych_collapse")
        suspect = mock_engine.suspects[0]
        suspect.confession_level = 4

        events = tool.execute(mock_engine, suspect, "")

        confession_events = [e for e in events if e.get("type") == "confession_update"]
        assert len(confession_events) == 0


class TestToolRegistration:
    """Test that all new tools are properly registered."""

    def test_lie_detector_registered(self):
        """Lie detector should be in TOOL_REGISTRY."""
        from core.tools import TOOL_REGISTRY

        assert "lie_detector" in TOOL_REGISTRY

    def test_threat_registered(self):
        """Threat should be in TOOL_REGISTRY."""
        from core.tools import TOOL_REGISTRY

        assert "threat" in TOOL_REGISTRY

    def test_dual_interrogation_registered(self):
        """Dual interrogation should be in TOOL_REGISTRY."""
        from core.tools import TOOL_REGISTRY

        assert "dual_interrogation" in TOOL_REGISTRY

    def test_psych_collapse_registered(self):
        """Psych collapse should be in TOOL_REGISTRY."""
        from core.tools import TOOL_REGISTRY

        assert "psych_collapse" in TOOL_REGISTRY

    def test_get_tool_returns_instances(self):
        """get_tool should return tool instances for all new tools."""
        from core.tools import get_tool

        for name in ["lie_detector", "threat", "dual_interrogation", "psych_collapse"]:
            tool = get_tool(name)
            assert tool is not None
            assert tool.name == name
