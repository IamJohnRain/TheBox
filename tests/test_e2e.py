from typing import Dict, List, Optional

import pytest

from core.db import init_db, load_full_session, save_case, save_full_session
from core.interrogation import InterrogationEngine


class DummySuspectAgent:
    """A deterministic stand-in for SuspectAgent that returns fixed responses without LLM."""

    def __init__(
        self,
        suspect_data: dict,
        case_title: str = "",
    ) -> None:
        self.name: str = suspect_data["name"]
        self.pressure: int = 50
        self.memory: List[Dict[str, str]] = []
        self._reply = "我是无辜的"
        self._pressure_change = 0
        self._secret_triggered = None

    def respond(self, player_input: str, context: Optional[dict] = None) -> dict:
        """Return a fixed response dict."""
        self.memory.append({"role": "user", "content": player_input})
        self.memory.append({"role": "assistant", "content": self._reply})
        return {
            "reply": self._reply,
            "pressure_change": self._pressure_change,
            "secret_triggered": self._secret_triggered,
        }


def _make_mock_case() -> dict:
    """Return a mock case dict for testing."""
    return {
        "case_id": "e2e_test_001",
        "title": "测试案件",
        "victim": "受害者",
        "cause_of_death": "中毒",
        "crime_scene": "办公室",
        "truth": "同事甲因嫉妒下毒",
        "suspects": [
            {
                "name": "同事甲",
                "role": "同事",
                "personality": "阴险",
                "knowledge": "我知道办公室里发生的事",
                "forbidden_to_reveal": ["下毒", "毒药"],
            },
            {
                "name": "同事乙",
                "role": "同事",
                "personality": "老实",
                "knowledge": "我什么都没看到",
                "forbidden_to_reveal": ["我杀的"],
            },
        ],
        "evidences": [
            {
                "id": "ev1",
                "name": "毒药瓶",
                "description": "在同事甲桌下发现的毒药瓶",
                "related_suspect": "同事甲",
            },
            {
                "id": "ev2",
                "name": "监控录像",
                "description": "显示同事甲深夜出入办公室",
                "related_suspect": "同事甲",
            },
        ],
        "interrogation_time_limit_sec": 300,
    }


def _make_engine_with_dummies(case_data: dict) -> InterrogationEngine:
    """Create an engine with DummySuspectAgent instances replacing real SuspectAgents."""
    engine = InterrogationEngine(case_data)
    engine.suspects = [
        DummySuspectAgent(s, case_data["title"]) for s in case_data["suspects"]
    ]
    return engine


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = str(tmp_path / "test_e2e.db")
    init_db(db_path)
    return db_path


@pytest.fixture
def mock_case():
    """Return a mock case dict."""
    return _make_mock_case()


@pytest.mark.slow
def test_save_and_restore_session(temp_db, mock_case):
    """Test that saving and loading a session preserves all engine state."""
    save_case(mock_case, temp_db)
    engine = _make_engine_with_dummies(mock_case)
    engine.select_suspect(0)
    engine.submit_action("chat", "你在哪里？")
    engine.submit_action("pressure", "说实话！")
    engine.submit_action("present_evidence", "看看这个", evidence_id="ev1")
    engine.tick(10)

    session_id = "test_session_001"
    engine_state_dict = engine.to_dict()
    save_full_session(session_id, mock_case["case_id"], engine_state_dict, temp_db)

    result = load_full_session(session_id, temp_db)
    assert result is not None
    loaded_case_id, loaded_state = result
    assert loaded_case_id == mock_case["case_id"]

    restored_engine = _make_engine_with_dummies(mock_case)
    restored_engine = InterrogationEngine.from_dict(loaded_state, mock_case)

    assert restored_engine.time_left == engine.time_left
    assert restored_engine.current_suspect_index == engine.current_suspect_index
    assert restored_engine.state == engine.state
    assert restored_engine.presented_evidence_ids == engine.presented_evidence_ids

    for i in range(len(engine.suspects)):
        assert restored_engine.suspects[i].name == engine.suspects[i].name
        assert restored_engine.suspects[i].pressure == engine.suspects[i].pressure
        assert restored_engine.suspects[i].memory == engine.suspects[i].memory


@pytest.mark.slow
def test_full_interrogation_flow(temp_db, mock_case):
    """Test a complete interrogation flow with state transitions and events."""
    save_case(mock_case, temp_db)
    engine = _make_engine_with_dummies(mock_case)

    assert engine.state == "selecting"

    info = engine.select_suspect(0)
    assert engine.state == "interrogating"
    assert info["name"] == "同事甲"

    events = engine.submit_action("chat", "你那天在哪里？")
    assert len(events) > 0
    msg_events = [e for e in events if e["type"] == "new_message"]
    assert len(msg_events) >= 2
    update_events = [e for e in events if e["type"] == "suspect_update"]
    assert len(update_events) == 1

    events = engine.submit_action("pressure", "你必须说实话！")
    assert engine.suspects[0].pressure == 60

    events = engine.submit_action("present_evidence", "看看这个证据", evidence_id="ev1")
    assert "ev1" in engine.presented_evidence_ids
    assert engine.suspects[0].pressure == 80

    events = engine.submit_action("empathy", "我能理解你。")
    assert engine.suspects[0].pressure == 75

    engine.select_suspect(1)
    assert engine.current_suspect_index == 1
    events = engine.submit_action("chat", "你看到什么了？")
    msg_events = [e for e in events if e["type"] == "new_message" and e["role"] == "suspect"]
    assert len(msg_events) == 1

    engine.time_left = 1
    events = engine.tick(1)
    assert engine.state == "verdict"
    state_events = [e for e in events if e["type"] == "state_change"]
    assert len(state_events) == 1
    assert state_events[0]["new_state"] == "verdict"

    events = engine.submit_action("chat", "你好")
    assert events == []


@pytest.mark.slow
def test_multiple_save_cycles(temp_db, mock_case):
    """Test saving, loading, doing more actions, saving again, and loading again."""
    save_case(mock_case, temp_db)
    engine = _make_engine_with_dummies(mock_case)
    engine.select_suspect(0)

    engine.submit_action("chat", "第一个问题")
    engine.submit_action("pressure", "施压")

    session_id_1 = "cycle_session_001"
    state_1 = engine.to_dict()
    save_full_session(session_id_1, mock_case["case_id"], state_1, temp_db)

    _, loaded_state_1 = load_full_session(session_id_1, temp_db)
    engine = InterrogationEngine.from_dict(loaded_state_1, mock_case)
    engine.suspects = [
        DummySuspectAgent(s, mock_case["title"]) for s in mock_case["suspects"]
    ]
    engine.suspects[0].pressure = state_1["suspects_states"][0]["pressure"]
    engine.suspects[0].memory = state_1["suspects_states"][0]["memory"]

    assert engine.time_left == state_1["time_left"]
    assert engine.state == state_1["state"]

    engine.submit_action("chat", "第二个问题")
    engine.submit_action("empathy", "共情")
    engine.tick(20)

    session_id_2 = "cycle_session_002"
    state_2 = engine.to_dict()
    save_full_session(session_id_2, mock_case["case_id"], state_2, temp_db)

    _, loaded_state_2 = load_full_session(session_id_2, temp_db)
    engine_2 = InterrogationEngine.from_dict(loaded_state_2, mock_case)
    engine_2.suspects = [
        DummySuspectAgent(s, mock_case["title"]) for s in mock_case["suspects"]
    ]
    for i, s_state in enumerate(state_2["suspects_states"]):
        engine_2.suspects[i].pressure = s_state["pressure"]
        engine_2.suspects[i].memory = s_state["memory"]

    assert engine_2.time_left == state_2["time_left"]
    assert engine_2.current_suspect_index == state_2["current_suspect_index"]
    assert engine_2.state == state_2["state"]
    assert engine_2.presented_evidence_ids == set(state_2["presented_evidence_ids"])

    assert state_2["time_left"] < state_1["time_left"]

    result = load_full_session(session_id_1, temp_db)
    assert result is not None
    _, old_state = result
    assert old_state["time_left"] == state_1["time_left"]
