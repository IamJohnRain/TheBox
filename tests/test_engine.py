from typing import Dict, List, Optional

import pytest

from core.interrogation import InterrogationEngine


class DummySuspectAgent:
    """A deterministic stand-in for SuspectAgent that returns fixed responses."""

    def __init__(
        self,
        name: str,
        pressure: int = 50,
        reply: str = "我是无辜的",
        pressure_change: int = 0,
        secret_triggered: Optional[str] = None,
    ) -> None:
        self.name = name
        self.pressure = pressure
        self.memory: List[Dict[str, str]] = []
        self._reply = reply
        self._pressure_change = pressure_change
        self._secret_triggered = secret_triggered

    def respond(self, player_input: str, context: Optional[dict] = None) -> dict:
        """Return a fixed response dict."""
        self.memory.append({"role": "user", "content": player_input})
        self.memory.append({"role": "assistant", "content": self._reply})
        return {
            "reply": self._reply,
            "pressure_change": self._pressure_change,
            "secret_triggered": self._secret_triggered,
        }


@pytest.fixture
def simple_case(mock_case_simple):
    return mock_case_simple


@pytest.fixture
def engine_with_dummies(simple_case):
    engine = InterrogationEngine(simple_case)
    engine.suspects = [
        DummySuspectAgent(name=s["name"], pressure=50) for s in simple_case["suspects"]
    ]
    return engine


class TestInitialState:
    def test_initial_state_is_selecting(self, engine_with_dummies):
        assert engine_with_dummies.state == "selecting"

    def test_initial_time_left(self, engine_with_dummies, simple_case):
        assert engine_with_dummies.time_left == simple_case["interrogation_time_limit_sec"]

    def test_initial_suspect_index(self, engine_with_dummies):
        assert engine_with_dummies.current_suspect_index == 0

    def test_initial_presented_evidence_empty(self, engine_with_dummies):
        assert len(engine_with_dummies.presented_evidence_ids) == 0


class TestSelectSuspect:
    def test_select_suspect_updates_index(self, engine_with_dummies):
        engine_with_dummies.select_suspect(1)
        assert engine_with_dummies.current_suspect_index == 1

    def test_select_suspect_returns_correct_name(self, engine_with_dummies, simple_case):
        info = engine_with_dummies.select_suspect(0)
        assert info["name"] == simple_case["suspects"][0]["name"]

    def test_select_suspect_returns_pressure(self, engine_with_dummies):
        result = engine_with_dummies.select_suspect(0)
        assert result["pressure"] == 50

    def test_select_suspect_changes_state_to_interrogating(self, engine_with_dummies):
        assert engine_with_dummies.state == "selecting"
        engine_with_dummies.select_suspect(0)
        assert engine_with_dummies.state == "interrogating"

    def test_select_suspect_invalid_index_raises(self, engine_with_dummies):
        with pytest.raises(ValueError):
            engine_with_dummies.select_suspect(99)

    def test_select_second_suspect(self, engine_with_dummies, simple_case):
        result = engine_with_dummies.select_suspect(1)
        assert result["name"] == simple_case["suspects"][1]["name"]


class TestSubmitActionChat:
    def test_chat_returns_events_with_reply(self, engine_with_dummies):
        engine_with_dummies.select_suspect(0)
        events = engine_with_dummies.submit_action("chat", "你那天在哪里？")
        messages = [e for e in events if e["type"] == "new_message"]
        assert len(messages) >= 2
        suspect_msgs = [m for m in messages if m["role"] == "suspect"]
        assert len(suspect_msgs) == 1
        assert suspect_msgs[0]["content"] == "我是无辜的"

    def test_chat_includes_player_message(self, engine_with_dummies):
        engine_with_dummies.select_suspect(0)
        events = engine_with_dummies.submit_action("chat", "你好")
        player_msgs = [e for e in events if e["type"] == "new_message" and e["role"] == "player"]
        assert len(player_msgs) == 1
        assert player_msgs[0]["content"] == "你好"

    def test_chat_includes_suspect_update(self, engine_with_dummies):
        engine_with_dummies.select_suspect(0)
        events = engine_with_dummies.submit_action("chat", "你好")
        updates = [e for e in events if e["type"] == "suspect_update"]
        assert len(updates) == 1

    def test_chat_when_not_interrogating_returns_empty(self, engine_with_dummies):
        engine_with_dummies.state = "selecting"
        events = engine_with_dummies.submit_action("chat", "你好")
        assert events == []


class TestSubmitActionPressure:
    def test_pressure_boosts_by_10(self, engine_with_dummies):
        engine_with_dummies.select_suspect(0)
        initial_pressure = engine_with_dummies.suspects[0].pressure
        engine_with_dummies.submit_action("pressure", "你必须说实话！")
        final_pressure = engine_with_dummies.suspects[0].pressure
        assert final_pressure == initial_pressure + 10

    def test_pressure_event_reflects_change(self, engine_with_dummies):
        engine_with_dummies.select_suspect(0)
        initial_pressure = engine_with_dummies.suspects[0].pressure
        events = engine_with_dummies.submit_action("pressure", "说！")
        updates = [e for e in events if e["type"] == "suspect_update"]
        assert updates[0]["pressure"] == initial_pressure + 10


class TestSubmitActionEmpathy:
    def test_empathy_reduces_pressure_by_5(self, engine_with_dummies):
        engine_with_dummies.select_suspect(0)
        initial_pressure = engine_with_dummies.suspects[0].pressure
        engine_with_dummies.submit_action("empathy", "我能理解你的感受。")
        final_pressure = engine_with_dummies.suspects[0].pressure
        assert final_pressure == initial_pressure - 5

    def test_empathy_clamps_at_zero(self, engine_with_dummies):
        engine_with_dummies.select_suspect(0)
        engine_with_dummies.suspects[0].pressure = 2
        engine_with_dummies.submit_action("empathy", "别担心。")
        assert engine_with_dummies.suspects[0].pressure == 0


class TestSubmitActionPresentEvidence:
    def test_invalid_evidence_no_pressure_change(self, engine_with_dummies):
        engine_with_dummies.select_suspect(0)
        initial_pressure = engine_with_dummies.suspects[0].pressure
        events = engine_with_dummies.submit_action("present_evidence", "看看这个", evidence_id="nonexistent")
        assert engine_with_dummies.suspects[0].pressure == initial_pressure
        system_msgs = [e for e in events if e["type"] == "new_message" and e["role"] == "system"]
        assert len(system_msgs) == 1
        assert "不存在" in system_msgs[0]["content"]

    def test_valid_matching_evidence_increases_pressure_by_20(self, engine_with_dummies, simple_case):
        engine_with_dummies.select_suspect(0)
        suspect = engine_with_dummies.suspects[0]
        initial_pressure = suspect.pressure
        matching_evidence = simple_case["evidences"][0]
        assert matching_evidence["related_suspect"] == suspect.name
        engine_with_dummies.submit_action(
            "present_evidence", "看看这个证据", evidence_id=matching_evidence["id"]
        )
        assert suspect.pressure == initial_pressure + 20

    def test_valid_matching_evidence_recorded(self, engine_with_dummies, simple_case):
        engine_with_dummies.select_suspect(0)
        matching_evidence = simple_case["evidences"][0]
        engine_with_dummies.submit_action(
            "present_evidence", "证据在这里", evidence_id=matching_evidence["id"]
        )
        assert matching_evidence["id"] in engine_with_dummies.presented_evidence_ids

    def test_non_matching_evidence_no_extra_pressure(self, engine_with_dummies, simple_case):
        engine_with_dummies.select_suspect(1)
        suspect = engine_with_dummies.suspects[1]
        initial_pressure = suspect.pressure
        non_matching = simple_case["evidences"][0]
        engine_with_dummies.submit_action(
            "present_evidence", "看看这个", evidence_id=non_matching["id"]
        )
        assert suspect.pressure == initial_pressure

    def test_none_evidence_id_returns_system_message(self, engine_with_dummies):
        engine_with_dummies.select_suspect(0)
        initial_pressure = engine_with_dummies.suspects[0].pressure
        engine_with_dummies.submit_action("present_evidence", "看看这个", evidence_id=None)
        assert engine_with_dummies.suspects[0].pressure == initial_pressure


class TestTick:
    def test_tick_decreases_time_left(self, engine_with_dummies):
        initial_time = engine_with_dummies.time_left
        engine_with_dummies.tick(1)
        assert engine_with_dummies.time_left == initial_time - 1

    def test_tick_returns_timer_event(self, engine_with_dummies):
        events = engine_with_dummies.tick(1)
        timer_events = [e for e in events if e["type"] == "timer_tick"]
        assert len(timer_events) == 1
        assert timer_events[0]["time_left"] == engine_with_dummies.time_left

    def test_tick_multiple_seconds(self, engine_with_dummies):
        initial_time = engine_with_dummies.time_left
        engine_with_dummies.tick(30)
        assert engine_with_dummies.time_left == initial_time - 30

    def test_tick_to_zero_state_becomes_verdict(self, engine_with_dummies):
        engine_with_dummies.time_left = 1
        events = engine_with_dummies.tick(1)
        assert engine_with_dummies.time_left == 0
        assert engine_with_dummies.state == "verdict"
        state_events = [e for e in events if e["type"] == "state_change"]
        assert len(state_events) == 1
        assert state_events[0]["new_state"] == "verdict"
        assert state_events[0]["verdict_reason"] == "审讯时间耗尽"

    def test_tick_past_zero_clamps(self, engine_with_dummies):
        engine_with_dummies.time_left = 5
        engine_with_dummies.tick(100)
        assert engine_with_dummies.time_left == 0

    def test_tick_when_already_verdict_no_duplicate_event(self, engine_with_dummies):
        engine_with_dummies.state = "verdict"
        events = engine_with_dummies.tick(1)
        state_events = [e for e in events if e["type"] == "state_change"]
        assert len(state_events) == 0


class TestSecretTriggered:
    def test_secret_triggered_sets_breakdown(self, engine_with_dummies):
        engine_with_dummies.select_suspect(0)
        engine_with_dummies.suspects[0] = DummySuspectAgent(
            name="李四", pressure=50, secret_triggered="我打的"
        )
        events = engine_with_dummies.submit_action("chat", "是你干的吧？")
        assert engine_with_dummies.state == "breakdown"
        state_events = [e for e in events if e["type"] == "state_change"]
        assert len(state_events) == 1
        assert state_events[0]["new_state"] == "breakdown"
        assert "李四" in state_events[0]["verdict_reason"]

    def test_no_secret_stays_interrogating(self, engine_with_dummies):
        engine_with_dummies.select_suspect(0)
        engine_with_dummies.submit_action("chat", "你好")
        assert engine_with_dummies.state == "interrogating"
