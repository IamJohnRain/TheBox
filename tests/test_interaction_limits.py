"""Tests for AP system and interaction limits - Phase 1d."""

import pytest


@pytest.fixture
def interrogating_engine(mock_engine):
    """Provide an engine in 'interrogating' state ready for submit_action."""
    if mock_engine is None:
        pytest.skip("InterrogationEngine not available")
    mock_engine.state = "interrogating"
    return mock_engine


class TestActionPoints:
    """Test action points system."""

    def test_initial_ap_from_config(self, mock_case_simple):
        """Initial AP should come from config."""
        from core.interrogation import InterrogationEngine
        from core.game_config import DEFAULT_TOTAL_ACTION_POINTS

        engine = InterrogationEngine(mock_case_simple)
        assert engine.action_points_remaining == DEFAULT_TOTAL_ACTION_POINTS

    def test_chat_costs_1_ap(self, interrogating_engine):
        """Chat action should cost 1 AP."""
        from core.game_config import ACTION_AP_COST

        initial_ap = interrogating_engine.action_points_remaining
        interrogating_engine.submit_action("chat", "你好")

        assert interrogating_engine.action_points_remaining == initial_ap - ACTION_AP_COST["chat"]

    def test_present_evidence_costs_2_ap(self, interrogating_engine):
        """Present evidence should cost 2 AP."""
        from core.game_config import ACTION_AP_COST

        initial_ap = interrogating_engine.action_points_remaining
        interrogating_engine.submit_action("present_evidence", "出示证据", evidence_id="e1")

        assert interrogating_engine.action_points_remaining == initial_ap - ACTION_AP_COST["present_evidence"]

    def test_insufficient_ap_returns_system_message(self, interrogating_engine):
        """Should return system message when AP is insufficient."""
        interrogating_engine.action_points_remaining = 1  # Not enough for present_evidence (2 AP)

        events = interrogating_engine.submit_action("present_evidence", "出示证据", evidence_id="e1")

        assert len(events) == 1
        assert "不足" in events[0]["content"]


class TestEvidenceUses:
    """Test evidence uses limit."""

    def test_initial_evidence_uses(self, mock_case_simple):
        """Initial evidence uses should come from config."""
        from core.interrogation import InterrogationEngine
        from core.game_config import DEFAULT_EVIDENCE_USES

        engine = InterrogationEngine(mock_case_simple)
        assert engine.evidence_uses_remaining == DEFAULT_EVIDENCE_USES

    def test_present_evidence_decreases_uses(self, interrogating_engine):
        """Presenting evidence should decrease remaining uses."""
        initial_uses = interrogating_engine.evidence_uses_remaining
        interrogating_engine.submit_action("present_evidence", "出示证据", evidence_id="e1")

        assert interrogating_engine.evidence_uses_remaining == initial_uses - 1

    def test_no_evidence_uses_returns_message(self, interrogating_engine):
        """Should return message when evidence uses exhausted."""
        interrogating_engine.evidence_uses_remaining = 0

        events = interrogating_engine.submit_action("present_evidence", "出示证据", evidence_id="e1")

        assert any("耗尽" in e.get("content", "") for e in events)


class TestChatTurnsLimit:
    """Test chat turns per suspect limit."""

    def test_initial_chat_turns(self, mock_case_simple):
        """Initial chat turns should come from config."""
        from core.interrogation import InterrogationEngine
        from core.game_config import CHAT_TURNS_PER_SUSPECT

        engine = InterrogationEngine(mock_case_simple)
        assert engine.chat_turns_remaining[0] == CHAT_TURNS_PER_SUSPECT

    def test_chat_decreases_turns(self, interrogating_engine):
        """Chat should decrease remaining turns."""
        initial_turns = interrogating_engine.chat_turns_remaining[0]
        interrogating_engine.submit_action("chat", "你好")

        assert interrogating_engine.chat_turns_remaining[0] == initial_turns - 1

    def test_no_chat_turns_returns_refusal(self, interrogating_engine):
        """Should return refusal when chat turns exhausted."""
        interrogating_engine.chat_turns_remaining[0] = 0

        events = interrogating_engine.submit_action("chat", "你好")

        assert any("拒绝" in e.get("content", "") for e in events)


class TestPressureEmpathyLimits:
    """Test pressure and empathy uses per suspect."""

    def test_initial_pressure_uses(self, mock_case_simple):
        """Initial pressure uses should come from config."""
        from core.interrogation import InterrogationEngine
        from core.game_config import PRESSURE_USES_PER_SUSPECT

        engine = InterrogationEngine(mock_case_simple)
        assert engine.pressure_uses_remaining[0] == PRESSURE_USES_PER_SUSPECT

    def test_pressure_decreases_uses(self, interrogating_engine):
        """Pressure action should decrease remaining uses."""
        initial_uses = interrogating_engine.pressure_uses_remaining[0]
        interrogating_engine.submit_action("pressure", "你最好说实话！")

        assert interrogating_engine.pressure_uses_remaining[0] == initial_uses - 1

    def test_no_pressure_uses_returns_message(self, interrogating_engine):
        """Should return message when pressure uses exhausted."""
        interrogating_engine.pressure_uses_remaining[0] = 0

        events = interrogating_engine.submit_action("pressure", "你最好说实话！")

        assert any("施压" in e.get("content", "") for e in events)

    def test_empathy_limit(self, interrogating_engine):
        """Empathy should have same limit as pressure."""
        from core.game_config import EMPATHY_USES_PER_SUSPECT

        assert interrogating_engine.empathy_uses_remaining[0] == EMPATHY_USES_PER_SUSPECT

        interrogating_engine.submit_action("empathy", "我理解你的处境")
        assert interrogating_engine.empathy_uses_remaining[0] == EMPATHY_USES_PER_SUSPECT - 1


class TestSaveLoadCompatibility:
    """Test save/load with new fields."""

    def test_to_dict_includes_new_fields(self, interrogating_engine):
        """to_dict should include AP and interaction limits."""
        state = interrogating_engine.to_dict()

        assert "action_points_remaining" in state
        assert "evidence_uses_remaining" in state
        assert "chat_turns_remaining" in state
        assert "pressure_uses_remaining" in state
        assert "empathy_uses_remaining" in state
        assert "mistake_log" in state

    def test_from_dict_restores_new_fields(self, interrogating_engine, mock_case_simple):
        """from_dict should restore AP and interaction limits."""
        from core.interrogation import InterrogationEngine

        # Modify state
        interrogating_engine.action_points_remaining = 15
        interrogating_engine.evidence_uses_remaining = 2
        interrogating_engine.chat_turns_remaining[0] = 5

        state = interrogating_engine.to_dict()
        restored = InterrogationEngine.from_dict(state, mock_case_simple)

        assert restored.action_points_remaining == 15
        assert restored.evidence_uses_remaining == 2
        assert restored.chat_turns_remaining[0] == 5
