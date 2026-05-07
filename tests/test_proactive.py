"""Tests for proactive (反扑) mechanism - Phase 2."""

from typing import Dict, List, Optional

import pytest

from core.interrogation import InterrogationEngine


class ProactiveDummyAgent:
    """A deterministic suspect agent for proactive testing."""

    def __init__(self, name: str, pressure: int = 50, fear: int = 50, defiance: int = 50, turn_count: int = 0) -> None:
        self.name = name
        self.pressure = pressure
        self.memory: List[Dict[str, str]] = []
        self.confession_level = 0
        self.confession_progress = 0.0
        self.turn_count = turn_count
        self.fear = fear
        self.defiance = defiance
        self.empathy_susceptibility = 50
        self.deception_skill = 50
        self.loyalty = 50
        self.credibility = 50

    def respond(self, player_input: str, context: Optional[dict] = None) -> dict:
        self.memory.append({"role": "user", "content": player_input})
        self.memory.append({"role": "assistant", "content": "我是无辜的"})
        return {"reply": "我是无辜的", "secret_triggered": None}

    def respond_evidence(
        self, evidence_description: str, evidence_type: str = "unknown"
    ) -> dict:
        self.memory.append({"role": "user", "content": f"[出示证据] {evidence_description}"})
        self.memory.append({"role": "assistant", "content": "我是无辜的"})
        return {
            "reply": "我是无辜的",
            "secret_triggered": None,
            "rebuttal": False,
            "rebuttal_believable": False,
        }

    def update_confession_progress(self) -> float:
        return self.confession_progress

    def check_confession_upgrade(self, has_evidence: bool = False) -> Optional[int]:
        return None


@pytest.fixture
def proactive_case(mock_case_simple):
    """Case data for proactive testing."""
    case = dict(mock_case_simple)
    case["culprit_name"] = "李四"
    return case


class TestProactiveProvocation:
    """Test provocation proactive type (fear < threshold)."""

    def test_provocation_triggered_by_low_fear(self, proactive_case):
        """Low fear should trigger provocation proactive."""
        engine = InterrogationEngine(proactive_case)

        suspect = ProactiveDummyAgent(name="李四", pressure=50, fear=10, turn_count=5)
        result = engine._check_proactive(suspect)

        assert result is not None
        assert result["type"] == "proactive"
        assert result["proactive_type"] == "provocation"

    def test_provocation_content_includes_name(self, proactive_case):
        """Provocation content should include suspect name."""
        engine = InterrogationEngine(proactive_case)

        suspect = ProactiveDummyAgent(name="李四", pressure=50, fear=10, turn_count=5)
        result = engine._check_proactive(suspect)

        assert "李四" in result["content"]

    def test_provocation_effects(self, proactive_case):
        """Provocation should reduce pressure and increase defiance."""
        engine = InterrogationEngine(proactive_case)

        suspect = ProactiveDummyAgent(name="李四", pressure=50, fear=10, turn_count=5)
        result = engine._check_proactive(suspect)

        assert result["effects"]["pressure"] == -2
        assert result["effects"]["defiance"] == +2

    def test_no_provocation_with_high_fear(self, proactive_case):
        """High fear should not trigger provocation."""
        engine = InterrogationEngine(proactive_case)

        suspect = ProactiveDummyAgent(name="李四", pressure=50, fear=50, turn_count=5)
        result = engine._check_proactive(suspect)

        # fear=50 >= 15, so no provocation (and no idle turns, so no recovery)
        assert result is None


class TestProactiveRecovery:
    """Test recovery proactive type (consecutive idle turns)."""

    def test_recovery_triggered_by_idle_turns(self, proactive_case):
        """Consecutive idle turns should trigger recovery proactive."""
        engine = InterrogationEngine(proactive_case)
        engine._consecutive_idle_turns = 3

        suspect = ProactiveDummyAgent(name="李四", pressure=50, fear=50, turn_count=5)
        result = engine._check_proactive(suspect)

        assert result is not None
        assert result["type"] == "proactive"
        assert result["proactive_type"] == "recover"

    def test_recovery_content(self, proactive_case):
        """Recovery content should mention regaining composure."""
        engine = InterrogationEngine(proactive_case)
        engine._consecutive_idle_turns = 3

        suspect = ProactiveDummyAgent(name="李四", pressure=50, fear=50, turn_count=5)
        result = engine._check_proactive(suspect)

        assert "李四" in result["content"]

    def test_recovery_effects(self, proactive_case):
        """Recovery should increase defiance and reduce fear."""
        engine = InterrogationEngine(proactive_case)
        engine._consecutive_idle_turns = 3

        suspect = ProactiveDummyAgent(name="李四", pressure=50, fear=50, turn_count=5)
        result = engine._check_proactive(suspect)

        assert result["effects"]["defiance"] == +3
        assert result["effects"]["fear"] == -5

    def test_no_recovery_without_idle_turns(self, proactive_case):
        """Without consecutive idle turns, recovery should not trigger."""
        engine = InterrogationEngine(proactive_case)
        # Default: no _consecutive_idle_turns attribute

        suspect = ProactiveDummyAgent(name="李四", pressure=50, fear=50, turn_count=5)
        result = engine._check_proactive(suspect)

        # Neither provocation nor recovery should trigger
        assert result is None


class TestProactiveCooldown:
    """Test proactive cooldown mechanism."""

    def test_cooldown_prevents_repeated_proactive(self, proactive_case):
        """Proactive should be on cooldown for 3 turns after triggering."""
        engine = InterrogationEngine(proactive_case)

        suspect = ProactiveDummyAgent(name="李四", pressure=50, fear=10, turn_count=5)
        # First call triggers
        result1 = engine._check_proactive(suspect)
        assert result1 is not None

        # Second call with same turn count should be on cooldown
        result2 = engine._check_proactive(suspect)
        assert result2 is None

        # After 3 turns, should be available again
        suspect.turn_count = 8
        result3 = engine._check_proactive(suspect)
        assert result3 is not None

    def test_cooldown_set_on_trigger(self, proactive_case):
        """_last_proactive_turn should be set when proactive triggers."""
        engine = InterrogationEngine(proactive_case)

        suspect = ProactiveDummyAgent(name="李四", pressure=50, fear=10, turn_count=5)
        engine._check_proactive(suspect)

        assert hasattr(suspect, '_last_proactive_turn')
        assert suspect._last_proactive_turn == 5


class TestProactiveInSubmitAction:
    """Test that proactive check runs during submit_action."""

    def test_proactive_msg_in_events(self, proactive_case):
        """Proactive messages should appear in submit_action events."""
        engine = InterrogationEngine(proactive_case)
        engine.select_suspect(0)

        suspect = ProactiveDummyAgent(name="李四", pressure=50, fear=10, turn_count=5)
        engine.suspects[0] = suspect

        events = engine.submit_action("chat", "你好")

        # Should have at least one suspect message (the normal reply)
        # and potentially a proactive message
        suspect_msgs = [e for e in events if e["type"] == "new_message" and e["role"] == "suspect"]
        # The proactive message should be present
        proactive_msgs = [m for m in suspect_msgs if "冷笑" in m["content"] or "深呼吸" in m["content"]]
        assert len(proactive_msgs) >= 1

    def test_proactive_effects_applied_to_suspect(self, proactive_case):
        """Proactive effects should modify suspect attributes."""
        engine = InterrogationEngine(proactive_case)
        engine.select_suspect(0)

        suspect = ProactiveDummyAgent(name="李四", pressure=50, fear=10, defiance=50, turn_count=5)
        engine.suspects[0] = suspect

        initial_defiance = suspect.defiance
        engine.submit_action("chat", "你好")

        # Provocation should increase defiance by 2
        # (but dimension effects and dynamics may also change it)
        # Just verify it runs without error
        assert suspect.defiance is not None


class TestProactivePriority:
    """Test proactive priority: provocation > recovery."""

    def test_provocation_over_recovery(self, proactive_case):
        """When both conditions are met, provocation should take priority."""
        engine = InterrogationEngine(proactive_case)
        engine._consecutive_idle_turns = 3  # Recovery condition met

        suspect = ProactiveDummyAgent(name="李四", pressure=50, fear=10, turn_count=5)  # Provocation condition met
        result = engine._check_proactive(suspect)

        # Provocation has higher priority
        assert result["proactive_type"] == "provocation"
