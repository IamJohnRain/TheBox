"""Tests for hidden dimensions and confession system - Phase 1e."""

import pytest


class TestHiddenDimensions:
    """Test hidden dimension initialization and calculation."""

    def test_dimensions_from_explicit_values(self, mock_case_simple):
        """Dimensions should use explicit values from suspect data."""
        from core.suspect_agent import SuspectAgent

        suspect_data = mock_case_simple["suspects"][0]
        agent = SuspectAgent(suspect_data, mock_case_simple["title"])

        # simple.json has "hidden_" prefixed values
        assert agent.fear == suspect_data.get("hidden_fear", 50)
        assert agent.defiance == suspect_data.get("hidden_defiance", 50)

    def test_dimensions_from_personality(self):
        """Dimensions should be calculated from personality when no explicit value."""
        from core.suspect_agent import SuspectAgent

        suspect_data = {
            "name": "测试",
            "role": "嫌疑人",
            "personality": "胆小",  # fear=80, defiance=20
            "knowledge": "我知道一些事",
            "forbidden_to_reveal": ["秘密"],
        }
        agent = SuspectAgent(suspect_data, "测试案件")

        assert agent.fear == 80  # 胆小性格的fear值
        assert agent.defiance == 20  # 胆小性格的defiance值

    def test_dimensions_weighted_combination(self):
        """Primary + secondary personality should be weighted."""
        from core.suspect_agent import SuspectAgent

        suspect_data = {
            "name": "测试",
            "role": "嫌疑人",
            "personality": "冷静",  # fear=30
            "personality_secondary": "胆小",  # fear=80
            "knowledge": "我知道一些事",
            "forbidden_to_reveal": ["秘密"],
        }
        agent = SuspectAgent(suspect_data, "测试案件")

        # 30 * 0.7 + 80 * 0.3 = 21 + 24 = 45
        assert agent.fear == 45

    def test_dimension_bounds_respected(self):
        """Dimensions should respect min/max bounds."""
        from core.suspect_agent import SuspectAgent
        from core.game_config import DIMENSION_BOUNDS

        suspect_data = {
            "name": "测试",
            "role": "嫌疑人",
            "personality": "冷静",
            "fear": 150,  # Out of bounds
            "defiance": -10,  # Out of bounds
            "knowledge": "我知道一些事",
            "forbidden_to_reveal": ["秘密"],
        }
        agent = SuspectAgent(suspect_data, "测试案件")

        assert agent.fear <= DIMENSION_BOUNDS["fear"]["max"]
        assert agent.defiance >= DIMENSION_BOUNDS["defiance"]["min"]


class TestConfessionSystem:
    """Test confession level system."""

    def test_initial_confession_level(self, mock_case_simple):
        """Initial confession level should be 0."""
        from core.suspect_agent import SuspectAgent

        suspect_data = mock_case_simple["suspects"][0]
        agent = SuspectAgent(suspect_data, mock_case_simple["title"])

        assert agent.confession_level == 0
        assert agent.confession_progress == 0.0

    def test_confession_upgrade_requires_conditions(self, mock_case_simple):
        """Confession upgrade should check pressure, turns, and evidence."""
        from core.suspect_agent import SuspectAgent

        suspect_data = mock_case_simple["suspects"][0]
        agent = SuspectAgent(suspect_data, mock_case_simple["title"])

        # Not enough pressure
        agent.pressure = 30
        agent.turn_count = 5
        assert agent.check_confession_upgrade(has_evidence=True) is None

        # Enough pressure but not enough turns
        agent.pressure = 50
        agent.turn_count = 2
        assert agent.check_confession_upgrade(has_evidence=False) is None

        # All conditions met (level 0→1: pressure>=40, turns>=3, no evidence required)
        agent.pressure = 45
        agent.turn_count = 4
        result = agent.check_confession_upgrade(has_evidence=False)
        assert result == 1

    def test_confession_progress_update(self, mock_case_simple):
        """Confession progress should increase based on pressure segment."""
        from core.suspect_agent import SuspectAgent

        suspect_data = mock_case_simple["suspects"][0]
        agent = SuspectAgent(suspect_data, mock_case_simple["title"])

        # Low pressure segment (0-30): rate = 0.02
        agent.pressure = 20
        agent.update_confession_progress()
        assert agent.confession_progress == pytest.approx(0.02)


class TestDimensionPerTurnEffects:
    """Test per-turn dimension linkage."""

    def test_high_pressure_reduces_defiance(self, mock_engine):
        """Pressure > 60 should reduce defiance."""
        suspect = mock_engine.suspects[0]
        suspect.pressure = 70
        suspect.defiance = 50

        mock_engine._apply_dimension_per_turn_effects(suspect)

        assert suspect.defiance == 49  # -1

    def test_high_fear_reduces_multiple_dimensions(self, mock_engine):
        """Fear > 70 should reduce defiance, deception, loyalty."""
        suspect = mock_engine.suspects[0]
        suspect.fear = 75
        suspect.defiance = 50
        suspect.deception_skill = 50
        suspect.loyalty = 50

        mock_engine._apply_dimension_per_turn_effects(suspect)

        assert suspect.defiance == 48  # -2
        assert suspect.deception_skill == 47  # -3
        assert suspect.loyalty == 48  # -2


class TestSaveLoadDimensions:
    """Test save/load with dimension fields."""

    def test_to_dict_includes_dimensions(self, mock_engine):
        """to_dict should include all dimension fields."""
        state = mock_engine.to_dict()
        suspect_state = state["suspects_states"][0]

        assert "confession_level" in suspect_state
        assert "fear" in suspect_state
        assert "defiance" in suspect_state
        assert "empathy_susceptibility" in suspect_state
        assert "deception_skill" in suspect_state
        assert "loyalty" in suspect_state
        assert "credibility" in suspect_state

    def test_from_dict_restores_dimensions(self, mock_engine, mock_case_simple):
        """from_dict should restore all dimension fields."""
        from core.interrogation import InterrogationEngine

        # Modify dimensions
        suspect = mock_engine.suspects[0]
        suspect.confession_level = 2
        suspect.fear = 75
        suspect.defiance = 30

        state = mock_engine.to_dict()
        restored = InterrogationEngine.from_dict(state, mock_case_simple)

        assert restored.suspects[0].confession_level == 2
        assert restored.suspects[0].fear == 75
        assert restored.suspects[0].defiance == 30
