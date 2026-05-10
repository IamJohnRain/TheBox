"""Story mode full flow tests — simulated playthrough of the entire story.

All tests use StateDrivenSuspect (no LLM) and play through from story
selection to an ending, covering win / partial / fail paths.
"""

from schemas.story import ChapterResult

# ── Story chapters enriched with interrogation_time_limit_sec ──


def _enhanced_story_data() -> dict:
    """Return a story dict that has all fields needed by InterrogationEngine."""
    from core.story_loader import load_story

    story = load_story("test_story")
    # Each chapter's case_data must have interrogation_time_limit_sec
    for ch in story["chapters"]:
        if "interrogation_time_limit_sec" not in ch.get("case_data", {}):
            ch["case_data"]["interrogation_time_limit_sec"] = 600
    return story


# ── Helpers ──


def _ensure_time_limit(case_data: dict, default: int = 600) -> None:
    """Ensure case_data has interrogation_time_limit_sec (mutates in place)."""
    if "interrogation_time_limit_sec" not in case_data:
        case_data["interrogation_time_limit_sec"] = default


def _inject_state_driven(engine, case_data):
    """Replace real SuspectAgent with StateDrivenSuspect."""
    from tests.fixtures.state_driven_suspect import StateDrivenSuspect

    engine.suspects = [StateDrivenSuspect(s, case_data["title"]) for s in case_data["suspects"]]


def _play_to_breakdown(engine):
    """Drive the engine to breakdown state.

    Strategy: set suspect to confession_level=4 (complete breakdown).
    The engine's _check_victory checks confession_level >= 4 at the
    END of submit_action, so one chat after setting level 4 triggers it.
    """
    suspect = engine.suspects[engine.current_suspect_index]
    suspect.confession_level = 4
    suspect.pressure = 90

    if engine.state == "selecting":
        engine.select_suspect(0)

    # One chat will trigger respond → _check_victory → level 4 → breakdown
    events = engine.submit_action("chat", "交代你的全部罪行")
    assert engine.state == "breakdown", f"Expected breakdown, got {engine.state}. Events: {events}"
    return events


def _play_to_partial(engine, suspect_index: int = 0):
    """Drive engine to partial confession level (>= 2).

    Directly sets suspect state to simulate a partially successful interrogation.
    """
    if engine.state == "selecting":
        engine.select_suspect(suspect_index)

    suspect = engine.suspects[suspect_index]

    # Simulate a partially successful interrogation:
    # enough turns played, evidence shown, pressure at threshold
    suspect.turn_count = 7
    suspect.confession_level = 1  # already upgraded from 0→1
    suspect.pressure = 60

    has_evidence = bool(engine.case.get("evidences"))
    if has_evidence:
        ev = engine.case["evidences"][0]
        engine.submit_action("present_evidence", "看看这个", evidence_id=ev["id"])
        # This triggers: respond_evidence, turn_count++, check_confession_upgrade

    # Do a few more actions to accumulate turns >= 7
    for _ in range(3):
        engine.submit_action("chat", "再想想")

    # At this point: turn_count >= 10, pressure should be high enough
    # StateDrivenSuspect auto-upgrades if thresholds met
    return suspect.confession_level


def _play_to_verdict(engine):
    """Tick time to reach verdict (timeout)."""
    if engine.state == "selecting":
        engine.select_suspect(0)
    engine.time_left = 1
    events = engine.tick(1)
    assert engine.state == "verdict"
    return events


class TestStoryWinPath:
    """Test story mode win path: ch01 → breakdown → ending_good."""

    def test_ch01_win_goes_to_good_ending(self):
        """Win chapter 1 → branch to ending_good (skip ch02)."""
        from core.interrogation import InterrogationEngine
        from core.story_engine import StoryEngine

        story = _enhanced_story_data()
        engine = StoryEngine(story)
        case_data = engine.start_chapter()

        ie = InterrogationEngine(case_data)
        _inject_state_driven(ie, case_data)
        engine.interrogation_engine = ie

        # Play to breakdown
        ie.select_suspect(0)
        _play_to_breakdown(ie)

        # Evaluate and advance
        suspect = ie.suspects[0]
        result = ChapterResult(
            result="win",
            confession_level=suspect.confession_level,
            evidence_count=len(ie.presented_evidence_ids),
            ap_remaining_pct=round(ie.action_points_remaining / max(ie.total_action_points, 1), 2),
            suspect_name=suspect.name,
            culprit_name=ie.case.get("culprit_name", ""),
            verdict_reason="测试破案",
        )

        # Verify result type
        assert result["result"] == "win"
        assert suspect.confession_level >= 3

        # Advance story
        next_id = engine.complete_chapter(result)
        assert next_id == "ending_good"
        assert engine.is_ending(next_id)

    def test_ch01_win_narrative_text(self):
        """Win chapter 1 → closing_win narrative is returned."""
        from core.interrogation import InterrogationEngine
        from core.story_engine import StoryEngine

        story = _enhanced_story_data()
        engine = StoryEngine(story)
        case_data = engine.start_chapter()

        ie = InterrogationEngine(case_data)
        _inject_state_driven(ie, case_data)

        ie.select_suspect(0)
        _play_to_breakdown(ie)

        result = ChapterResult(
            result="win",
            confession_level=4,
            evidence_count=0,
            ap_remaining_pct=0.5,
            suspect_name="嫌疑人A",
            culprit_name="嫌疑人A",
            verdict_reason="",
        )

        narrative = engine.get_narrative(result)
        assert "成功" in narrative

        engine.complete_chapter(result)

        # Check ending data
        ending = engine.get_ending("ending_good")
        assert ending is not None
        assert ending["title"] == "好结局"


class TestStoryFailPath:
    """Test story mode fail path: ch01 → verdict → ending_bad."""

    def test_ch01_fail_goes_to_bad_ending(self):
        """Fail chapter 1 (timeout) → branch to ending_bad."""
        from core.interrogation import InterrogationEngine
        from core.story_engine import StoryEngine

        story = _enhanced_story_data()
        engine = StoryEngine(story)
        case_data = engine.start_chapter()

        ie = InterrogationEngine(case_data)
        _inject_state_driven(ie, case_data)
        engine.interrogation_engine = ie

        # Play to verdict (timeout)
        ie.select_suspect(0)
        _play_to_verdict(ie)

        # Evaluate
        suspect = ie.suspects[0]
        result = ChapterResult(
            result="fail",
            confession_level=suspect.confession_level,
            evidence_count=len(ie.presented_evidence_ids),
            ap_remaining_pct=round(ie.action_points_remaining / max(ie.total_action_points, 1), 2),
            suspect_name=suspect.name,
            culprit_name=ie.case.get("culprit_name", ""),
            verdict_reason="审讯时间耗尽",
        )

        assert result["result"] == "fail"
        assert suspect.confession_level < 2

        # Branch: fail → ending_bad
        next_id = engine.complete_chapter(result)
        assert next_id == "ending_bad"
        assert engine.is_ending(next_id)

    def test_ch01_fail_narrative_text(self):
        """Fail chapter 1 → closing_fail narrative is returned."""
        from core.interrogation import InterrogationEngine
        from core.story_engine import StoryEngine

        story = _enhanced_story_data()
        engine = StoryEngine(story)
        case_data = engine.start_chapter()

        ie = InterrogationEngine(case_data)
        _inject_state_driven(ie, case_data)

        ie.select_suspect(0)
        _play_to_verdict(ie)

        result = ChapterResult(
            result="fail",
            confession_level=0,
            evidence_count=0,
            ap_remaining_pct=0.5,
            suspect_name="嫌疑人A",
            culprit_name="嫌疑人A",
            verdict_reason="",
        )

        narrative = engine.get_narrative(result)
        assert "失败" in narrative


class TestStoryPartialThenWin:
    """Test partial path: ch01 partial → ch02 → ending_good."""

    def test_partial_advances_to_ch02(self):
        """Partial result on ch01 → advances to ch02 (not ending)."""
        from core.interrogation import InterrogationEngine
        from core.story_engine import StoryEngine

        story = _enhanced_story_data()
        se = StoryEngine(story)

        # ── Chapter 1: partial ──
        case_ch01 = se.start_chapter()
        ie_ch01 = InterrogationEngine(case_ch01)
        _inject_state_driven(ie_ch01, case_ch01)
        se.interrogation_engine = ie_ch01

        ie_ch01.select_suspect(0)
        _play_to_partial(ie_ch01)

        suspect = ie_ch01.suspects[0]
        level_after_ch01 = suspect.confession_level

        # Force partial even if we didn't reach level 2 — ensure at least
        # some evidence was presented for the fallback partial condition
        if level_after_ch01 < 2 and len(ie_ch01.presented_evidence_ids) == 0:
            ev = ie_ch01.case.get("evidences", [])
            if ev:
                ie_ch01.submit_action("present_evidence", "test", evidence_id=ev[0]["id"])

        # Determine result
        if ie_ch01.state == "verdict" and len(ie_ch01.presented_evidence_ids) > 0:
            ch01_result_type = "partial"
        elif suspect.confession_level >= 2:
            ch01_result_type = "partial"
        elif suspect.confession_level >= 4 or ie_ch01.state == "breakdown":
            ch01_result_type = "win"
        else:
            ch01_result_type = "fail"

        result_ch01 = ChapterResult(
            result=ch01_result_type,
            confession_level=suspect.confession_level,
            evidence_count=len(ie_ch01.presented_evidence_ids),
            ap_remaining_pct=round(ie_ch01.action_points_remaining / max(ie_ch01.total_action_points, 1), 2),
            suspect_name=suspect.name,
            culprit_name=case_ch01.get("culprit_name", ""),
            verdict_reason=f"Chapter 1 ended: {ie_ch01.state}",
        )

        assert result_ch01["result"] == "partial", (
            f"Expected partial, got {result_ch01['result']} "
            f"(level={suspect.confession_level}, "
            f"evidence={len(ie_ch01.presented_evidence_ids)}, "
            f"state={ie_ch01.state})"
        )

        next_id = se.complete_chapter(result_ch01)
        assert next_id == "ch02"
        assert not se.is_ending(next_id)
        assert "ch01" in se.completed_chapters

    def test_two_chapter_win_to_good_ending(self):
        """ch01 partial → ch02 win → ending_good."""
        from core.interrogation import InterrogationEngine
        from core.story_engine import StoryEngine

        story = _enhanced_story_data()
        se = StoryEngine(story)

        # ── Chapter 1: partial ──
        case_ch01 = se.start_chapter()
        ie_ch01 = InterrogationEngine(case_ch01)
        _inject_state_driven(ie_ch01, case_ch01)
        se.interrogation_engine = ie_ch01

        ie_ch01.select_suspect(0)
        _play_to_partial(ie_ch01)
        suspect_ch01 = ie_ch01.suspects[0]

        if suspect_ch01.confession_level < 2 and len(ie_ch01.presented_evidence_ids) == 0:
            ev = ie_ch01.case.get("evidences", [])
            if ev:
                ie_ch01.submit_action("present_evidence", "test", evidence_id=ev[0]["id"])

        result_ch01 = ChapterResult(
            result="partial",
            confession_level=suspect_ch01.confession_level,
            evidence_count=len(ie_ch01.presented_evidence_ids),
            ap_remaining_pct=round(ie_ch01.action_points_remaining / max(ie_ch01.total_action_points, 1), 2),
            suspect_name=suspect_ch01.name,
            culprit_name=case_ch01.get("culprit_name", ""),
            verdict_reason="partial",
        )

        next_id = se.complete_chapter(result_ch01)
        assert next_id == "ch02"

        # ── Chapter 2: win ──
        case_ch02 = se.start_chapter()
        ie_ch02 = InterrogationEngine(case_ch02)
        _inject_state_driven(ie_ch02, case_ch02)
        se.interrogation_engine = ie_ch02

        ie_ch02.select_suspect(0)
        _play_to_breakdown(ie_ch02)

        suspect_ch02 = ie_ch02.suspects[0]
        result_ch02 = ChapterResult(
            result="win",
            confession_level=suspect_ch02.confession_level,
            evidence_count=len(ie_ch02.presented_evidence_ids),
            ap_remaining_pct=round(ie_ch02.action_points_remaining / max(ie_ch02.total_action_points, 1), 2),
            suspect_name=suspect_ch02.name,
            culprit_name=case_ch02.get("culprit_name", ""),
            verdict_reason="chapter 2 win",
        )

        next_id = se.complete_chapter(result_ch02)
        assert next_id == "ending_good"
        assert se.is_ending(next_id)

    def test_story_progress_tracks_completed_chapters(self):
        """Verify progress tracking across chapters."""
        from core.interrogation import InterrogationEngine
        from core.story_engine import StoryEngine

        story = _enhanced_story_data()
        se = StoryEngine(story)

        # Initial progress
        progress = se.get_progress()
        assert progress["completed_count"] == 0
        assert progress["current_chapter_id"] == "ch01"
        assert progress["total_chapters"] == 2

        # Play chapter 1 → partial
        case_ch01 = se.start_chapter()
        ie_ch01 = InterrogationEngine(case_ch01)
        _inject_state_driven(ie_ch01, case_ch01)
        se.interrogation_engine = ie_ch01
        ie_ch01.select_suspect(0)
        _play_to_partial(ie_ch01)

        suspect = ie_ch01.suspects[0]
        if suspect.confession_level < 2 and len(ie_ch01.presented_evidence_ids) == 0:
            ev = ie_ch01.case.get("evidences", [])
            if ev:
                ie_ch01.submit_action("present_evidence", "t", evidence_id=ev[0]["id"])

        result_ch01 = ChapterResult(
            result="partial",
            confession_level=suspect.confession_level,
            evidence_count=len(ie_ch01.presented_evidence_ids),
            ap_remaining_pct=0.5,
            suspect_name=suspect.name,
            culprit_name=case_ch01.get("culprit_name", ""),
            verdict_reason="",
        )
        se.complete_chapter(result_ch01)

        progress = se.get_progress()
        assert progress["completed_count"] == 1
        assert progress["current_chapter_id"] == "ch02"


class TestStorySessionIntegration:
    """Test GameSession integration with story mode."""

    def test_game_session_story_full_flow(self):
        """Full flow via GameSession: start_story → start_chapter → play → evaluate → complete."""
        from core.game_session import GameSession
        from core.interrogation import InterrogationEngine

        session = GameSession()
        session.start_story("test_story")
        assert session.mode == "story"
        assert session.story_engine is not None

        # Chapter 1
        case_ch01 = session.start_chapter()
        _ensure_time_limit(case_ch01)
        ie = InterrogationEngine(case_ch01)
        _inject_state_driven(ie, case_ch01)
        session.engine = ie
        session.story_engine.interrogation_engine = ie

        ie.select_suspect(0)
        _play_to_breakdown(ie)

        # Evaluate
        result = session.evaluate_chapter()
        assert result["result"] == "win"
        assert result["suspect_name"] == "嫌疑人A"
        assert result["culprit_name"] == "嫌疑人A"

        # Complete
        narrative = session.get_narrative(result)
        assert "成功" in narrative

        next_id = session.complete_chapter(result)
        assert next_id == "ending_good"

    def test_game_session_story_fail_path(self):
        """Full fail flow via GameSession: timeout → evaluate → ending_bad."""
        from core.game_session import GameSession
        from core.interrogation import InterrogationEngine

        session = GameSession()
        session.start_story("test_story")

        case_ch01 = session.start_chapter()
        _ensure_time_limit(case_ch01)
        ie = InterrogationEngine(case_ch01)
        _inject_state_driven(ie, case_ch01)
        session.engine = ie
        session.story_engine.interrogation_engine = ie

        ie.select_suspect(0)
        _play_to_verdict(ie)

        result = session.evaluate_chapter()
        assert result["result"] == "fail"

        narrative = session.get_narrative(result)
        assert "失败" in narrative

        next_id = session.complete_chapter(result)
        assert next_id == "ending_bad"

    def test_on_interrogation_ending_integrates(self):
        """GameSession.on_interrogation_ending properly advances the story."""
        from core.game_session import GameSession
        from core.interrogation import InterrogationEngine

        session = GameSession()
        session.start_story("test_story")

        case_ch01 = session.start_chapter()
        _ensure_time_limit(case_ch01)
        ie = InterrogationEngine(case_ch01)
        _inject_state_driven(ie, case_ch01)
        session.engine = ie
        session.story_engine.interrogation_engine = ie

        ie.select_suspect(0)
        _play_to_breakdown(ie)

        # Simulate the UI layer calling on_interrogation_ending
        state_event = {"type": "state_change", "new_state": "breakdown", "verdict_reason": "test"}
        session.on_interrogation_ending(state_event)

        # Story should have advanced
        assert session._chapter_result is not None
        assert session._chapter_result["result"] == "win"
        assert session.story_engine.current_chapter_id == "ending_good"
