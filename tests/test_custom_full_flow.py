"""Custom mode full flow tests — simulated playthrough from case setup to game end.

Uses mock_case_simple + StateDrivenSuspect for fast, deterministic testing.
Covers: confession path, secret-triggered path, timeout path, mistakes,
save/load cycles, and interaction limits.
"""

import pytest

from tests.fixtures.state_driven_suspect import StateDrivenSuspect

# ── Helpers ──


def _make_engine_with_state_driven(case_data: dict):
    """Create engine with StateDrivenSuspect for each suspect."""
    from core.interrogation import InterrogationEngine

    engine = InterrogationEngine(case_data)
    engine.suspects = [StateDrivenSuspect(s, case_data["title"]) for s in case_data["suspects"]]
    return engine


def _collect_events(events: list, event_type: str) -> list:
    """Filter events by type."""
    return [e for e in events if e.get("type") == event_type]


class TestCustomWinByConfession:
    """Win by reaching confession_level >= 4."""

    def test_confession_breakdown_via_level_4(self):
        """Set suspect to level 4 → chat triggers breakdown."""
        engine = _make_engine_with_state_driven(_get_mock_case())
        assert engine.state == "selecting"

        engine.select_suspect(0)
        assert engine.state == "interrogating"

        suspect = engine.suspects[0]
        assert suspect.confession_level == 0

        # Force to breakdown
        suspect.confession_level = 4
        suspect.pressure = 90

        events = engine.submit_action("chat", "你还有什么要说的？")

        assert engine.state == "breakdown"
        state_events = _collect_events(events, "state_change")
        assert len(state_events) == 1
        assert state_events[0]["new_state"] == "breakdown"
        assert "崩溃" in state_events[0]["verdict_reason"]

    def test_confession_produces_all_event_types(self):
        """Confession flow emits player msg, suspect msg, suspect_update, state_change."""
        engine = _make_engine_with_state_driven(_get_mock_case())
        engine.select_suspect(0)

        engine.suspects[0].confession_level = 4
        events = engine.submit_action("chat", "坦白吧")

        event_types = {e["type"] for e in events}
        assert "new_message" in event_types
        assert "suspect_update" in event_types
        assert "state_change" in event_types

    def test_actions_blocked_after_breakdown(self):
        """After breakdown, submit_action returns empty."""
        engine = _make_engine_with_state_driven(_get_mock_case())
        engine.select_suspect(0)

        engine.suspects[0].confession_level = 4
        engine.submit_action("chat", "坦白")
        assert engine.state == "breakdown"

        events = engine.submit_action("chat", "继续问")
        assert events == []


class TestCustomWinBySecret:
    """Win by secret_triggered at confession_level >= 3."""

    def test_secret_trigger_at_level_3_causes_breakdown(self):
        """Suspect leaks forbidden word at level 3 → breakdown."""
        case = _get_mock_case()
        # Ensure culprit has forbidden_to_reveal
        culprit = case["suspects"][case.get("culprit_index", 0)]
        assert "forbidden_to_reveal" in culprit

        engine = _make_engine_with_state_driven(case)
        engine.select_suspect(0)

        suspect = engine.suspects[0]
        suspect.confession_level = 3
        suspect.pressure = 90

        # Manually call _check_victory with a mock result containing secret
        result = {"reply": "测试", "secret_triggered": culprit["forbidden_to_reveal"][0]}
        victory_event = engine._check_victory(suspect, result)

        assert victory_event is not None
        assert victory_event["new_state"] == "breakdown"
        assert "泄露" in victory_event["verdict_reason"]

    def test_secret_trigger_at_low_level_no_breakdown(self):
        """Secret at level < 3 should NOT trigger breakdown."""
        case = _get_mock_case()
        engine = _make_engine_with_state_driven(case)
        engine.select_suspect(0)

        suspect = engine.suspects[0]
        suspect.confession_level = 1

        culprit = case["suspects"][case.get("culprit_index", 0)]
        result = {"reply": "test", "secret_triggered": culprit["forbidden_to_reveal"][0]}
        victory_event = engine._check_victory(suspect, result)

        assert victory_event is None
        assert engine.state == "interrogating"


class TestCustomTimeout:
    """Win/lose via timer expiration."""

    def test_timeout_to_verdict(self):
        """Timer running out → verdict state."""
        engine = _make_engine_with_state_driven(_get_mock_case())
        engine.select_suspect(0)

        engine.time_left = 1
        events = engine.tick(1)

        assert engine.state == "verdict"
        state_events = _collect_events(events, "state_change")
        assert len(state_events) == 1
        assert state_events[0]["verdict_reason"] == "审讯时间耗尽"

    def test_timeout_tick_clamps_to_zero(self):
        """Tick larger than time_left clamps to 0."""
        engine = _make_engine_with_state_driven(_get_mock_case())
        engine.select_suspect(0)

        engine.time_left = 5
        engine.tick(100)
        assert engine.time_left == 0
        assert engine.state == "verdict"

    def test_actions_blocked_after_verdict(self):
        """After verdict, submit_action returns empty."""
        engine = _make_engine_with_state_driven(_get_mock_case())
        engine.select_suspect(0)

        engine.time_left = 1
        engine.tick(1)

        events = engine.submit_action("chat", "继续问")
        assert events == []

    def test_multiple_ticks_no_duplicate_verdict(self):
        """Ticking after already verdict does not produce extra state_change."""
        engine = _make_engine_with_state_driven(_get_mock_case())
        engine.select_suspect(0)

        engine.time_left = 1
        events1 = engine.tick(1)
        assert len(_collect_events(events1, "state_change")) == 1

        events2 = engine.tick(10)
        assert len(_collect_events(events2, "state_change")) == 0


class TestCustomMistakes:
    """Wrong actions trigger mistakes and AP penalties."""

    def test_wrong_evidence_penalty(self):
        """Presenting evidence not related to current suspect → mistake + AP penalty."""
        case = _get_mock_case()
        engine = _make_engine_with_state_driven(case)
        engine.select_suspect(0)

        # Find evidence NOT related to suspect 0
        suspect_name = engine.suspects[0].name
        wrong_ev = None
        for ev in case["evidences"]:
            if ev.get("related_suspect") != suspect_name:
                wrong_ev = ev
                break

        if wrong_ev:
            old_ap = engine.action_points_remaining
            engine.submit_action("present_evidence", "看看这个", evidence_id=wrong_ev["id"])
            # AP should decrease more (action cost 2 + mistake penalty)
            assert engine.action_points_remaining < old_ap
            assert len(engine.mistake_log) > 0
            assert engine.mistake_log[-1]["type"] == "wrong_evidence"

    def test_wrong_pressure_on_innocent(self):
        """Using pressure on a non-culprit → wrong_pressure mistake."""
        case = _get_mock_case()
        engine = _make_engine_with_state_driven(case)

        # Find the innocent suspect
        culprit_name = case.get("culprit_name", case["suspects"][0]["name"])
        innocent_idx = None
        for i, s in enumerate(case["suspects"]):
            if s["name"] != culprit_name:
                innocent_idx = i
                break

        if innocent_idx is not None:
            engine.select_suspect(innocent_idx)
            old_ap = engine.action_points_remaining
            engine.submit_action("pressure", "你干了什么！")
            assert len(engine.mistake_log) > 0
            assert engine.mistake_log[-1]["type"] == "wrong_pressure"
            assert engine.action_points_remaining < old_ap

    def test_wrong_empathy_on_culprit(self):
        """Using empathy on the culprit → wrong_empathy mistake."""
        case = _get_mock_case()
        engine = _make_engine_with_state_driven(case)

        culprit_name = case.get("culprit_name", case["suspects"][0]["name"])
        culprit_idx = next(
            (i for i, s in enumerate(case["suspects"]) if s["name"] == culprit_name),
            0,
        )
        engine.select_suspect(culprit_idx)
        old_ap = engine.action_points_remaining
        engine.submit_action("empathy", "我理解你的处境")

        assert len(engine.mistake_log) > 0
        assert engine.mistake_log[-1]["type"] == "wrong_empathy"
        assert engine.action_points_remaining < old_ap


class TestCustomInteractionLimits:
    """Per-suspect interaction limits: chat turns, pressure, empathy."""

    def test_pressure_uses_limited(self):
        """Pressure can only be used PRESSURE_USES_PER_SUSPECT (2) times."""
        from core.game_config import PRESSURE_USES_PER_SUSPECT

        engine = _make_engine_with_state_driven(_get_mock_case())
        engine.select_suspect(0)

        for i in range(PRESSURE_USES_PER_SUSPECT):
            events = engine.submit_action("pressure", f"施压{i}")
            assert len(events) > 0  # normal response

        # Third pressure attempt should be blocked
        events = engine.submit_action("pressure", "继续施压")
        sys_msgs = [e for e in events if e.get("role") == "system"]
        assert len(sys_msgs) > 0
        assert "施压" in sys_msgs[0]["content"] or "过" in sys_msgs[0]["content"]

    def test_empathy_uses_limited(self):
        """Empathy can only be used EMPATHY_USES_PER_SUSPECT (2) times."""
        from core.game_config import EMPATHY_USES_PER_SUSPECT

        engine = _make_engine_with_state_driven(_get_mock_case())
        engine.select_suspect(0)

        for i in range(EMPATHY_USES_PER_SUSPECT):
            events = engine.submit_action("empathy", f"共情{i}")
            assert len(events) > 0

        events = engine.submit_action("empathy", "继续共情")
        sys_msgs = [e for e in events if e.get("role") == "system"]
        assert len(sys_msgs) > 0

    def test_chat_turns_limited(self):
        """Chat turns per suspect are limited to CHAT_TURNS_PER_SUSPECT."""
        from core.game_config import CHAT_TURNS_PER_SUSPECT

        engine = _make_engine_with_state_driven(_get_mock_case())
        engine.select_suspect(0)

        for i in range(CHAT_TURNS_PER_SUSPECT):
            events = engine.submit_action("chat", f"问题{i}")
            assert len(events) > 0

        events = engine.submit_action("chat", "最后一个问题")
        sys_msgs = [e for e in events if e.get("role") == "system"]
        assert len(sys_msgs) > 0
        assert "拒绝" in sys_msgs[0]["content"]

    def test_ap_exhausted_blocks_actions(self):
        """Running out of AP blocks further actions."""
        engine = _make_engine_with_state_driven(_get_mock_case())
        engine.select_suspect(0)

        engine.action_points_remaining = 0
        events = engine.submit_action("chat", "测试")
        sys_msgs = [e for e in events if e.get("role") == "system"]
        assert len(sys_msgs) > 0
        assert "不足" in sys_msgs[0]["content"]


class TestCustomSaveLoad:
    """Save and restore engine state."""

    def test_save_load_preserves_state(self, tmp_path):
        """Serialize engine, restore from dict, verify state."""
        from core.db import init_db, load_full_session, save_case, save_full_session
        from core.interrogation import InterrogationEngine

        case = _get_mock_case()
        db_path = str(tmp_path / "test_custom.db")
        init_db(db_path)
        save_case(case, db_path)

        engine = _make_engine_with_state_driven(case)
        engine.select_suspect(0)
        engine.submit_action("chat", "第一个问题")
        engine.submit_action("pressure", "说！")
        engine.tick(30)

        state_dict = engine.to_dict()
        save_full_session("s1", case["case_id"], state_dict, db_path)

        # Restore via from_dict (creates real SuspectAgent instances)
        _, loaded = load_full_session("s1", db_path)
        restored = InterrogationEngine.from_dict(loaded, case)

        assert restored.time_left == engine.time_left
        assert restored.state == engine.state
        assert restored.presented_evidence_ids == engine.presented_evidence_ids
        assert restored.current_suspect_index == engine.current_suspect_index
        assert restored.suspects[0].name == engine.suspects[0].name


class TestCustomScoring:
    """Integration with scoring system after game ends."""

    def test_score_calculated_after_breakdown(self):
        """Score is calculable after engine reaches breakdown."""
        from core.scoring import calculate_score

        engine = _make_engine_with_state_driven(_get_mock_case())
        engine.select_suspect(0)
        engine.suspects[0].confession_level = 4
        engine.submit_action("chat", "坦白")
        assert engine.state == "breakdown"

        # Build session_data dict that calculate_score expects
        suspect = engine.suspects[0]
        correct_ev = sum(
            1
            for eid in engine.presented_evidence_ids
            if engine._find_evidence(eid) and engine._find_evidence(eid).get("related_suspect") == suspect.name
        )
        session_data = {
            "ap_remaining": engine.action_points_remaining,
            "total_ap": engine.total_action_points,
            "correct_evidence_count": correct_ev,
            "related_evidence_count": len(
                [e for e in engine.case.get("evidences", []) if e.get("related_suspect") == suspect.name]
            ),
            "evidence_uses": engine.case.get("evidence_uses", 4),
            "confession_level": suspect.confession_level,
            "pressure_count": len(engine.mistake_log) + 2,
            "pressure_on_culprit": 2,
            "total_evidence_presented": len(engine.presented_evidence_ids),
            "mistake_log": engine.mistake_log,
            "outcome": "win",
            "truth": engine.case.get("truth", ""),
            "memory_summary": "",
            "used_tools": [],
        }

        score = calculate_score(session_data)
        assert score is not None
        assert "total_score" in score
        assert score["total_score"] >= 0

    def test_score_calculated_after_verdict(self):
        """Score is calculable after timeout verdict."""
        from core.scoring import calculate_score

        engine = _make_engine_with_state_driven(_get_mock_case())
        engine.select_suspect(0)
        engine.time_left = 1
        engine.tick(1)
        assert engine.state == "verdict"

        suspect = engine.suspects[0]
        session_data = {
            "ap_remaining": engine.action_points_remaining,
            "total_ap": engine.total_action_points,
            "correct_evidence_count": 0,
            "related_evidence_count": 0,
            "evidence_uses": 4,
            "confession_level": suspect.confession_level,
            "pressure_count": 0,
            "pressure_on_culprit": 0,
            "total_evidence_presented": 0,
            "mistake_log": [],
            "outcome": "fail",
            "truth": engine.case.get("truth", ""),
            "memory_summary": "",
            "used_tools": [],
        }

        score = calculate_score(session_data)
        assert score is not None
        assert score["total_score"] >= 0


class TestCustomSwitchSuspects:
    """Switching suspects during interrogation."""

    def test_switch_suspect_preserves_state(self):
        """Switching suspect updates index and suspect info."""
        case = _get_mock_case()
        if len(case["suspects"]) < 2:
            pytest.skip("Need at least 2 suspects")

        engine = _make_engine_with_state_driven(case)
        engine.select_suspect(0)
        assert engine.current_suspect_index == 0

        info1 = engine.select_suspect(1)
        assert engine.current_suspect_index == 1
        assert info1["name"] == case["suspects"][1]["name"]

        info0 = engine.select_suspect(0)
        assert engine.current_suspect_index == 0
        assert info0["name"] == case["suspects"][0]["name"]

    def test_pressure_uses_are_per_suspect(self):
        """Pressure uses are tracked independently per suspect."""
        from core.game_config import PRESSURE_USES_PER_SUSPECT

        case = _get_mock_case()
        if len(case["suspects"]) < 2:
            pytest.skip("Need at least 2 suspects")

        engine = _make_engine_with_state_driven(case)
        engine.select_suspect(0)

        # Use all pressure on suspect 0
        for _ in range(PRESSURE_USES_PER_SUSPECT):
            engine.submit_action("pressure", "说！")

        # Switch to suspect 1 — should have full pressure uses
        engine.select_suspect(1)
        idx = engine.current_suspect_index
        assert engine.pressure_uses_remaining[idx] == PRESSURE_USES_PER_SUSPECT


class TestCustomEvidencePresentation:
    """Evidence presentation mechanics."""

    def test_correct_evidence_increases_pressure(self):
        """Matching evidence increases suspect pressure."""
        case = _get_mock_case()
        engine = _make_engine_with_state_driven(case)
        engine.select_suspect(0)

        suspect_name = engine.suspects[0].name
        match_ev = next(
            (e for e in case["evidences"] if e.get("related_suspect") == suspect_name),
            None,
        )
        if not match_ev:
            pytest.skip("No matching evidence found")

        old_pressure = engine.suspects[0].pressure
        engine.submit_action("present_evidence", "出示证据", evidence_id=match_ev["id"])

        assert engine.suspects[0].pressure > old_pressure
        assert match_ev["id"] in engine.presented_evidence_ids

    def test_evidence_uses_are_global(self):
        """Evidence uses are global, not per suspect."""
        from core.game_config import DEFAULT_EVIDENCE_USES

        case = _get_mock_case()
        engine = _make_engine_with_state_driven(case)
        engine.select_suspect(0)

        assert engine.evidence_uses_remaining == DEFAULT_EVIDENCE_USES

        # Use one evidence
        evs = case["evidences"]
        if evs:
            engine.submit_action("present_evidence", "test", evidence_id=evs[0]["id"])
            assert engine.evidence_uses_remaining == DEFAULT_EVIDENCE_USES - 1


# ── Inline mock case ──


def _get_mock_case() -> dict:
    """Return a mock case with all required fields for InterrogationEngine."""
    import json

    from tests.fixtures.conftest import FIXTURES_DIR

    with open(FIXTURES_DIR / "mock_cases" / "simple.json", "r", encoding="utf-8") as f:
        case = json.load(f)

    # Ensure culprit_name exists
    if "culprit_name" not in case:
        case["culprit_name"] = "李四"

    return case
