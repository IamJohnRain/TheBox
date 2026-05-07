"""Tests for rebuttal mechanism - Phase 2."""

from typing import Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from core.interrogation import InterrogationEngine


class RebuttalDummyAgent:
    """A deterministic suspect agent with configurable rebuttal behavior."""

    def __init__(
        self,
        name: str,
        pressure: int = 50,
        fear: int = 50,
        defiance: int = 50,
        deception_skill: int = 50,
        credibility: int = 50,
        rebuttal: bool = False,
        rebuttal_believable: bool = False,
    ) -> None:
        self.name = name
        self.pressure = pressure
        self.memory: List[Dict[str, str]] = []
        self.confession_level = 0
        self.confession_progress = 0.0
        self.turn_count = 0
        self.fear = fear
        self.defiance = defiance
        self.empathy_susceptibility = 50
        self.deception_skill = deception_skill
        self.loyalty = 50
        self.credibility = credibility
        self._rebuttal = rebuttal
        self._rebuttal_believable = rebuttal_believable

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
            "rebuttal": self._rebuttal,
            "rebuttal_believable": self._rebuttal_believable,
        }

    def update_confession_progress(self) -> float:
        return self.confession_progress

    def check_confession_upgrade(self, has_evidence: bool = False) -> Optional[int]:
        return None


@pytest.fixture
def rebuttal_case(mock_case_simple):
    """Case data with culprit_name set."""
    case = dict(mock_case_simple)
    case["culprit_name"] = "李四"
    # Add chain_with field to e1 for chain testing
    for e in case["evidences"]:
        if e["id"] == "e1":
            e["chain_with"] = ["e2"]
    return case


class TestRebuttalFields:
    """Test that respond_evidence returns rebuttal fields."""

    def test_respond_evidence_includes_rebuttal_fields(self, mock_case_simple):
        """respond_evidence should include rebuttal and rebuttal_believable fields."""
        engine = InterrogationEngine(mock_case_simple)
        engine.select_suspect(0)
        suspect = engine.suspects[0]

        result = suspect.respond_evidence("test", "physical")
        assert "rebuttal" in result
        assert "rebuttal_believable" in result

    def test_dummy_agent_includes_rebuttal_fields(self, rebuttal_case):
        """DummySuspectAgent should include rebuttal fields in respond_evidence."""
        from core.interrogation import DummySuspectAgent

        dummy = DummySuspectAgent({"name": "test"})
        result = dummy.respond_evidence("test", "physical")
        assert "rebuttal" in result
        assert "rebuttal_believable" in result


class TestRebuttalSuccess:
    """Test rebuttal success scenario: pressure not increased, credibility up."""

    def test_rebuttal_success_no_pressure_increase(self, rebuttal_case):
        """When rebuttal succeeds, pressure should not increase."""
        engine = InterrogationEngine(rebuttal_case)
        engine.select_suspect(0)

        # Set up suspect with believable rebuttal at low pressure
        suspect = RebuttalDummyAgent(
            name="李四",
            pressure=30,  # Low pressure: below hard threshold
            fear=50,
            defiance=50,
            deception_skill=50,
            credibility=50,
            rebuttal=True,
            rebuttal_believable=True,
        )
        engine.suspects[0] = suspect

        initial_pressure = suspect.pressure
        evidence = rebuttal_case["evidences"][0]
        engine.submit_action("present_evidence", "看看这个", evidence_id=evidence["id"])

        # With rebuttal success, pressure should not increase
        assert suspect.pressure <= initial_pressure

    def test_rebuttal_success_increases_credibility(self, rebuttal_case):
        """When rebuttal succeeds, credibility should increase."""
        engine = InterrogationEngine(rebuttal_case)
        engine.select_suspect(0)

        suspect = RebuttalDummyAgent(
            name="李四",
            pressure=30,
            fear=50,
            defiance=50,
            deception_skill=50,
            credibility=50,
            rebuttal=True,
            rebuttal_believable=True,
        )
        engine.suspects[0] = suspect

        initial_credibility = suspect.credibility
        evidence = rebuttal_case["evidences"][0]
        engine.submit_action("present_evidence", "看看这个", evidence_id=evidence["id"])

        assert suspect.credibility > initial_credibility


class TestRebuttalFailure:
    """Test rebuttal failure scenario: pressure increases normally, credibility drops."""

    def test_rebuttal_failure_pressure_increases(self, rebuttal_case):
        """When rebuttal fails, pressure should increase normally."""
        engine = InterrogationEngine(rebuttal_case)
        engine.select_suspect(0)

        suspect = RebuttalDummyAgent(
            name="李四",
            pressure=30,
            fear=50,
            defiance=50,
            deception_skill=50,
            credibility=50,
            rebuttal=True,
            rebuttal_believable=False,  # Rebuttal fails
        )
        engine.suspects[0] = suspect

        initial_pressure = suspect.pressure
        evidence = rebuttal_case["evidences"][0]
        engine.submit_action("present_evidence", "看看这个", evidence_id=evidence["id"])

        assert suspect.pressure > initial_pressure

    def test_rebuttal_failure_decreases_credibility(self, rebuttal_case):
        """When rebuttal fails, credibility should decrease."""
        engine = InterrogationEngine(rebuttal_case)
        engine.select_suspect(0)

        suspect = RebuttalDummyAgent(
            name="李四",
            pressure=30,
            fear=50,
            defiance=50,
            deception_skill=50,
            credibility=50,
            rebuttal=True,
            rebuttal_believable=False,
        )
        engine.suspects[0] = suspect

        initial_credibility = suspect.credibility
        evidence = rebuttal_case["evidences"][0]
        engine.submit_action("present_evidence", "看看这个", evidence_id=evidence["id"])

        assert suspect.credibility < initial_credibility


class TestRebuttalHighPressureDecay:
    """Test that high pressure forces rebuttal believability to decay."""

    def test_high_pressure_forces_rebuttal_unbelievable(self, rebuttal_case):
        """At high pressure, believable rebuttal should be forced to unbelievable."""
        from core.game_config import REBUTTAL_DECAY_CONFIG

        engine = InterrogationEngine(rebuttal_case)
        engine.select_suspect(0)

        # Set pressure above the effective hard threshold
        # effective_hard_threshold = 80 + (50 - 50) * 0.2 = 80
        suspect = RebuttalDummyAgent(
            name="李四",
            pressure=85,  # Above default threshold of 80
            fear=50,
            defiance=50,
            deception_skill=50,
            credibility=50,
            rebuttal=True,
            rebuttal_believable=True,  # LLM says believable, but pressure overrides
        )
        engine.suspects[0] = suspect

        initial_pressure = suspect.pressure
        evidence = rebuttal_case["evidences"][0]
        engine.submit_action("present_evidence", "看看这个", evidence_id=evidence["id"])

        # Because rebuttal_believable was forced to False, pressure should increase
        assert suspect.pressure > initial_pressure

    def test_high_deception_skill_raises_threshold(self, rebuttal_case):
        """High deception_skill should raise the effective rebuttal threshold."""
        engine = InterrogationEngine(rebuttal_case)
        engine.select_suspect(0)

        # With deception_skill=90: effective threshold = 80 + (90-50)*0.2 = 80+8 = 88
        suspect = RebuttalDummyAgent(
            name="李四",
            pressure=85,  # Above 80 but below 88
            fear=50,
            defiance=50,
            deception_skill=90,  # High deception skill
            credibility=50,
            rebuttal=True,
            rebuttal_believable=True,
        )
        engine.suspects[0] = suspect

        evidence = rebuttal_case["evidences"][0]
        engine.submit_action("present_evidence", "看看这个", evidence_id=evidence["id"])

        # With high deception skill, 85 pressure is still below threshold (88)
        # So rebuttal should succeed, and credibility should increase
        assert suspect.credibility > 50  # credibility_bonus_success applied

    def test_no_rebuttal_no_effect(self, rebuttal_case):
        """When rebuttal is False, no rebuttal processing should occur."""
        engine = InterrogationEngine(rebuttal_case)
        engine.select_suspect(0)

        suspect = RebuttalDummyAgent(
            name="李四",
            pressure=50,
            fear=50,
            defiance=50,
            deception_skill=50,
            credibility=50,
            rebuttal=False,
            rebuttal_believable=False,
        )
        engine.suspects[0] = suspect

        initial_pressure = suspect.pressure
        initial_credibility = suspect.credibility
        evidence = rebuttal_case["evidences"][0]
        engine.submit_action("present_evidence", "看看这个", evidence_id=evidence["id"])

        # Credibility should not be modified by rebuttal logic
        assert suspect.credibility == initial_credibility
        # Pressure should increase normally
        assert suspect.pressure > initial_pressure
