"""Tests for tool system - Phase 3a."""

import pytest


class TestToolRegistry:
    """Test tool registration."""

    def test_tools_registered(self):
        """All tools should be registered."""
        from core.tools import TOOL_REGISTRY

        # Import modules to trigger registration
        import core.tools.psych_profile  # noqa: F401
        import core.tools.silent_pressure  # noqa: F401

        assert "psych_profile_basic" in TOOL_REGISTRY
        assert "psych_profile_advanced" in TOOL_REGISTRY
        assert "psych_profile_master" in TOOL_REGISTRY
        assert "silent_pressure" in TOOL_REGISTRY

    def test_get_tool_returns_instance(self):
        """get_tool should return tool instance."""
        from core.tools import get_tool

        tool = get_tool("psych_profile_basic")
        assert tool.name == "psych_profile_basic"
        assert tool.display_name == "心理侧写（初级）"

    def test_get_tool_unknown_raises(self):
        """get_tool with unknown name should raise ValueError."""
        from core.tools import get_tool

        with pytest.raises(ValueError, match="未知工具"):
            get_tool("nonexistent_tool")

    def test_register_tool_decorator(self):
        """register_tool decorator should add to TOOL_REGISTRY."""
        from core.tools import Tool, TOOL_REGISTRY, register_tool

        @register_tool
        class _TestTool(Tool):
            name = "_test_tool_temp"
            display_name = "测试工具"
            max_uses = 1
            unlock_level = 1
            cost_ap = 0

            def execute(self, engine, suspect, content: str):
                return []

        assert "_test_tool_temp" in TOOL_REGISTRY
        # Cleanup
        del TOOL_REGISTRY["_test_tool_temp"]


class TestPsychProfileTools:
    """Test psychological profiling tools."""

    def test_basic_profile_shows_fear(self, mock_engine):
        """Basic profile should show personality and fear."""
        from core.tools import get_tool

        tool = get_tool("psych_profile_basic")
        suspect = mock_engine.suspects[0]
        suspect.fear = 75

        events = tool.execute(mock_engine, suspect, "")

        assert len(events) == 1
        assert "75" in events[0]["content"]
        assert "恐惧" in events[0]["content"]

    def test_basic_profile_empathy_advice(self, mock_engine):
        """Basic profile should suggest empathy when fear is high."""
        from core.tools import get_tool

        tool = get_tool("psych_profile_basic")
        suspect = mock_engine.suspects[0]
        suspect.fear = 80

        events = tool.execute(mock_engine, suspect, "")
        assert "共情" in events[0]["content"]

    def test_basic_profile_pressure_advice(self, mock_engine):
        """Basic profile should suggest pressure when fear is low."""
        from core.tools import get_tool

        tool = get_tool("psych_profile_basic")
        suspect = mock_engine.suspects[0]
        suspect.fear = 30

        events = tool.execute(mock_engine, suspect, "")
        assert "证据施压" in events[0]["content"]

    def test_advanced_profile_shows_more(self, mock_engine):
        """Advanced profile should show defiance and empathy."""
        from core.tools import get_tool

        tool = get_tool("psych_profile_advanced")
        suspect = mock_engine.suspects[0]
        suspect.defiance = 80
        suspect.empathy_susceptibility = 30

        events = tool.execute(mock_engine, suspect, "")

        content = events[0]["content"]
        assert "抗压性" in content
        assert "共情易感性" in content
        assert "极强" in content  # defiance > 70

    def test_advanced_profile_strategy_advice(self, mock_engine):
        """Advanced profile should give strategy advice based on dimensions."""
        from core.tools import get_tool

        tool = get_tool("psych_profile_advanced")

        # Empathy > defiance → suggest empathy
        suspect = mock_engine.suspects[0]
        suspect.empathy_susceptibility = 80
        suspect.defiance = 20

        events = tool.execute(mock_engine, suspect, "")
        assert "共情策略" in events[0]["content"]

        # Defiance >= empathy → suggest pressure
        suspect.defiance = 90
        suspect.empathy_susceptibility = 30

        events = tool.execute(mock_engine, suspect, "")
        assert "施压策略" in events[0]["content"]

    def test_master_profile_shows_all(self, mock_engine):
        """Master profile should show all hidden dimensions."""
        from core.tools import get_tool

        tool = get_tool("psych_profile_master")
        suspect = mock_engine.suspects[0]
        suspect.defiance = 65
        suspect.deception_skill = 70

        events = tool.execute(mock_engine, suspect, "")

        content = events[0]["content"]
        assert "欺骗技巧" in content
        assert "忠诚度" in content
        assert "综合评估" in content


class TestSilentPressureTool:
    """Test silent pressure tool."""

    def test_silent_pressure_increases_pressure(self, mock_engine):
        """Silent pressure should increase suspect pressure by 15."""
        from core.tools import get_tool

        tool = get_tool("silent_pressure")
        suspect = mock_engine.suspects[0]
        suspect.pressure = 50

        events = tool.execute(mock_engine, suspect, "")

        assert suspect.pressure == 65  # 50 + 15

    def test_silent_pressure_returns_events(self, mock_engine):
        """Silent pressure should return player, suspect, and update events."""
        from core.tools import get_tool

        tool = get_tool("silent_pressure")
        suspect = mock_engine.suspects[0]

        events = tool.execute(mock_engine, suspect, "")

        assert len(events) == 3
        assert events[0]["role"] == "player"
        assert events[0]["content"] == "[沉默施压]"
        assert events[1]["role"] == "suspect"
        assert events[2]["type"] == "suspect_update"

    def test_silent_pressure_pressure_capped(self, mock_engine):
        """Silent pressure should not exceed 100."""
        from core.tools import get_tool

        tool = get_tool("silent_pressure")
        suspect = mock_engine.suspects[0]
        suspect.pressure = 95

        tool.execute(mock_engine, suspect, "")

        assert suspect.pressure == 100  # min(100, 95+15)


class TestToolUsage:
    """Test tool usage in engine."""

    def test_use_tool_decreases_uses(self, mock_engine):
        """Using tool should decrease remaining uses."""
        mock_engine.available_tools = {"psych_profile_basic": 1}

        events = mock_engine._use_tool("psych_profile_basic", "")

        assert mock_engine.available_tools["psych_profile_basic"] == 0

    def test_use_tool_no_uses_returns_message(self, mock_engine):
        """Using exhausted tool should return message."""
        mock_engine.available_tools = {"psych_profile_basic": 0}

        events = mock_engine._use_tool("psych_profile_basic", "")

        assert any("耗尽" in e.get("content", "") for e in events)

    def test_use_tool_unavailable_returns_message(self, mock_engine):
        """Using unavailable tool should return message."""
        events = mock_engine._use_tool("nonexistent", "")

        assert any("不可用" in e.get("content", "") for e in events)

    def test_use_tool_costs_ap(self, mock_engine):
        """Using tool with AP cost should deduct AP."""
        mock_engine.available_tools = {"silent_pressure": 2}
        mock_engine.action_points_remaining = 10

        events = mock_engine._use_tool("silent_pressure", "")

        assert mock_engine.action_points_remaining == 9  # 10 - 1

    def test_insufficient_ap_blocks_tool(self, mock_engine):
        """Insufficient AP should block tool use."""
        mock_engine.available_tools = {"silent_pressure": 2}
        mock_engine.action_points_remaining = 0

        events = mock_engine._use_tool("silent_pressure", "")

        assert any("不足" in e.get("content", "") for e in events)
        assert mock_engine.action_points_remaining == 0  # AP not deducted

    def test_use_tool_records_in_used_tools(self, mock_engine):
        """Using tool should record it in used_tools list."""
        mock_engine.available_tools = {"psych_profile_basic": 1}

        mock_engine._use_tool("psych_profile_basic", "")

        assert "psych_profile_basic" in mock_engine.used_tools

    def test_submit_action_tool_branch(self, mock_engine):
        """submit_action with tool_ prefix should route to _use_tool."""
        mock_engine.state = "interrogating"
        mock_engine.available_tools = {"psych_profile_basic": 1}

        events = mock_engine.submit_action("tool_psych_profile_basic", "")

        # Should produce at least the system message from the tool
        assert len(events) >= 1
        assert mock_engine.available_tools["psych_profile_basic"] == 0


class TestInitTools:
    """Test init_tools method."""

    def test_init_tools_level_1(self, mock_engine):
        """Level 1 should have no tools."""
        mock_engine.init_tools(player_level=1)
        assert mock_engine.available_tools == {}

    def test_init_tools_level_2(self, mock_engine):
        """Level 2 should unlock psych_profile_basic."""
        mock_engine.init_tools(player_level=2)
        assert "psych_profile_basic" in mock_engine.available_tools
        assert mock_engine.available_tools["psych_profile_basic"] == 1

    def test_init_tools_level_10(self, mock_engine):
        """Level 10 should unlock advanced profile and silent pressure."""
        mock_engine.init_tools(player_level=10)
        assert "psych_profile_basic" in mock_engine.available_tools
        assert "psych_profile_advanced" in mock_engine.available_tools
        assert "silent_pressure" in mock_engine.available_tools
        assert mock_engine.available_tools["silent_pressure"] == 2

    def test_init_tools_level_15(self, mock_engine):
        """Level 15 should unlock master profile."""
        mock_engine.init_tools(player_level=15)
        assert "psych_profile_master" in mock_engine.available_tools

    def test_init_tools_level_20_bonus(self, mock_engine):
        """Level 20+ should add +1 max_uses to all tools."""
        mock_engine.init_tools(player_level=20)
        assert mock_engine.available_tools["psych_profile_basic"] == 2  # 1 + 1
        assert mock_engine.available_tools["silent_pressure"] == 3  # 2 + 1


class TestToolSerialization:
    """Test tool state serialization/deserialization."""

    def test_to_dict_includes_tools(self, mock_engine):
        """to_dict should include available_tools and used_tools."""
        mock_engine.available_tools = {"psych_profile_basic": 1}
        mock_engine.used_tools = []

        state = mock_engine.to_dict()
        assert "available_tools" in state
        assert "used_tools" in state
        assert state["available_tools"]["psych_profile_basic"] == 1

    def test_from_dict_restores_tools(self, mock_engine, mock_case_simple):
        """from_dict should restore available_tools and used_tools."""
        from core.interrogation import InterrogationEngine

        mock_engine.available_tools = {"psych_profile_basic": 0, "silent_pressure": 1}
        mock_engine.used_tools = ["psych_profile_basic"]

        state = mock_engine.to_dict()
        restored = InterrogationEngine.from_dict(state, mock_case_simple)

        assert restored.available_tools == {"psych_profile_basic": 0, "silent_pressure": 1}
        assert restored.used_tools == ["psych_profile_basic"]
