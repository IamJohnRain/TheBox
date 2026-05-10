"""Tests for GameSession coordinator - Phase 5."""

import pytest


class TestGameSessionModes:
    """Test GameSession mode management."""

    def test_initial_state(self):
        """Initial mode should be None."""
        from core.game_session import GameSession

        session = GameSession()
        assert session.mode is None
        assert session.engine is None

    def test_start_custom_mode(self, mock_case_simple):
        """Starting custom mode should create engine."""
        from core.game_session import GameSession

        session = GameSession()
        session.start_custom(mock_case_simple)

        assert session.mode == "custom"
        assert session.engine is not None
        assert session.engine.case["case_id"] == "test_001"

    def test_start_story_mode(self):
        """Starting story mode should set mode and load story engine."""
        from core.game_session import GameSession

        session = GameSession()
        session.start_story("test_story")

        assert session.mode == "story"
        assert session._story_id == "test_story"
        assert session.story_engine is not None

    def test_start_custom_mode_with_player(self, mock_case_simple):
        """Starting custom mode with player should init tools."""
        from core.game_session import GameSession
        from core.player import PlayerProfile

        player = PlayerProfile()
        session = GameSession()
        session.start_custom(mock_case_simple, player=player)

        assert session.player is player
        assert session.mode == "custom"

    def test_start_story_mode_with_player(self):
        """Starting story mode with player should store player ref."""
        from core.game_session import GameSession
        from core.player import PlayerProfile

        player = PlayerProfile()
        session = GameSession()
        session.start_story("test_story", player=player)

        assert session.player is player
        assert session.mode == "story"

    def test_start_chapter_raises_without_story_mode(self, mock_case_simple):
        """start_chapter should raise if not in story mode."""
        from core.game_session import GameSession, SessionModeError

        session = GameSession()
        session.start_custom(mock_case_simple)

        with pytest.raises(SessionModeError):
            session.start_chapter()


class TestChapterEvaluation:
    """Test chapter result evaluation."""

    def test_evaluate_win(self, mock_case_simple):
        """Win when culprit confesses."""
        from core.game_session import GameSession

        session = GameSession()
        session.start_custom(mock_case_simple)

        # Simulate win condition: select culprit and set high confession
        culprit_index = None
        for i, s in enumerate(session.engine.suspects):
            if s.name == mock_case_simple["culprit_name"]:
                culprit_index = i
                break

        if culprit_index is not None:
            session.engine.current_suspect_index = culprit_index
            suspect = session.engine.suspects[culprit_index]
            suspect.confession_level = 4
            session.engine.state = "breakdown"

            result = session.evaluate_chapter()
            assert result["result"] == "win"
            assert result["confession_level"] == 4
            assert result["suspect_name"] == mock_case_simple["culprit_name"]

    def test_evaluate_partial(self, mock_case_simple):
        """Partial when confession >= 2."""
        from core.game_session import GameSession

        session = GameSession()
        session.start_custom(mock_case_simple)

        suspect = session.engine.suspects[0]
        suspect.confession_level = 2

        result = session.evaluate_chapter()

        assert result["result"] == "partial"

    def test_evaluate_fail(self, mock_case_simple):
        """Fail when confession < 2 and no evidence."""
        from core.game_session import GameSession

        session = GameSession()
        session.start_custom(mock_case_simple)

        suspect = session.engine.suspects[0]
        suspect.confession_level = 0
        session.engine.state = "verdict"
        # Ensure no evidence presented
        session.engine.presented_evidence_ids = set()

        result = session.evaluate_chapter()

        assert result["result"] == "fail"

    def test_evaluate_partial_with_evidence_in_verdict(self, mock_case_simple):
        """Partial when in verdict state with evidence presented."""
        from core.game_session import GameSession

        session = GameSession()
        session.start_custom(mock_case_simple)

        suspect = session.engine.suspects[0]
        suspect.confession_level = 0
        session.engine.state = "verdict"
        session.engine.presented_evidence_ids = {"e1"}

        result = session.evaluate_chapter()

        assert result["result"] == "partial"

    def test_evaluate_no_engine_raises(self):
        """evaluate_chapter should raise without engine."""
        from core.game_session import GameSession, SessionModeError

        session = GameSession()

        with pytest.raises(SessionModeError):
            session.evaluate_chapter()

    def test_evaluate_result_fields(self, mock_case_simple):
        """ChapterResult should have all required fields."""
        from core.game_session import GameSession

        session = GameSession()
        session.start_custom(mock_case_simple)

        suspect = session.engine.suspects[0]
        suspect.confession_level = 2

        result = session.evaluate_chapter()

        assert "result" in result
        assert "confession_level" in result
        assert "evidence_count" in result
        assert "ap_remaining_pct" in result
        assert "suspect_name" in result
        assert "culprit_name" in result
        assert "verdict_reason" in result

    def test_evaluate_ap_remaining_pct(self, mock_case_simple):
        """ap_remaining_pct should be calculated correctly."""
        from core.game_session import GameSession

        session = GameSession()
        session.start_custom(mock_case_simple)

        suspect = session.engine.suspects[0]
        suspect.confession_level = 0
        # Set AP to half
        session.engine.action_points_remaining = session.engine.total_action_points // 2

        result = session.evaluate_chapter()

        assert 0.0 <= result["ap_remaining_pct"] <= 1.0


class TestSessionSerialization:
    """Test session save/load."""

    def test_to_dict(self, mock_case_simple):
        """to_dict should include mode and engine state."""
        from core.game_session import GameSession

        session = GameSession()
        session.start_custom(mock_case_simple)

        state = session.to_dict()

        assert state["mode"] == "custom"
        assert state["engine_state"] is not None
        assert state["engine_state"]["case_id"] == "test_001"

    def test_to_dict_no_engine(self):
        """to_dict with no engine should have None engine_state."""
        from core.game_session import GameSession

        session = GameSession()

        state = session.to_dict()

        assert state["mode"] is None
        assert state["engine_state"] is None

    def test_to_dict_story_mode(self):
        """to_dict in story mode should include story_id."""
        from core.game_session import GameSession

        session = GameSession()
        session.start_story("test_story")

        state = session.to_dict()

        assert state["mode"] == "story"
        assert state["story_id"] == "test_story"

    def test_from_dict_custom(self, mock_case_simple):
        """from_dict should restore custom mode session."""
        from core.game_session import GameSession

        session = GameSession()
        session.start_custom(mock_case_simple)

        state = session.to_dict()
        restored = GameSession.from_dict(state)

        assert restored.mode == "custom"
        assert restored.engine is not None
        assert restored.engine.case.get("case_id") == "test_001"


class TestOnInterrogationEnding:
    """Test on_interrogation_ending dispatch."""

    def test_custom_mode_logs_result(self, mock_case_simple):
        """In custom mode, on_interrogation_ending should evaluate without error."""
        from core.game_session import GameSession

        session = GameSession()
        session.start_custom(mock_case_simple)

        suspect = session.engine.suspects[0]
        suspect.confession_level = 3
        session.engine.state = "breakdown"

        # Should not raise
        session.on_interrogation_ending({"type": "state_change", "new_state": "breakdown"})

        # Chapter result should be cached
        assert session._chapter_result is not None

    def test_story_mode_without_engine_no_error(self):
        """Story mode with story_engine but no interrogation engine should raise."""
        from core.game_session import GameSession, SessionModeError

        session = GameSession()
        session.start_story("test_story")
        # No interrogation engine set, on_interrogation_ending should raise
        with pytest.raises(SessionModeError):
            session.on_interrogation_ending({"type": "state_change", "new_state": "breakdown"})


class TestGetProgress:
    """Test get_progress for story mode."""

    def test_get_progress_custom_mode(self, mock_case_simple):
        """Custom mode should return None for progress."""
        from core.game_session import GameSession

        session = GameSession()
        session.start_custom(mock_case_simple)

        assert session.get_progress() is None

    def test_get_progress_story_no_engine(self):
        """Story mode with story_engine should return progress."""
        from core.game_session import GameSession

        session = GameSession()
        session.start_story("test_story")

        progress = session.get_progress()
        assert progress is not None
        assert progress["story_id"] == "test_story"

    def test_get_progress_no_mode(self):
        """No mode should return None for progress."""
        from core.game_session import GameSession

        session = GameSession()

        assert session.get_progress() is None


class TestGetNarrative:
    """Test get_narrative."""

    def test_get_narrative_custom_mode(self, mock_case_simple):
        """Custom mode should return empty string."""
        from core.game_session import GameSession

        session = GameSession()
        session.start_custom(mock_case_simple)

        result = session.evaluate_chapter()
        assert session.get_narrative(result) == ""

    def test_get_narrative_no_mode(self):
        """No mode should return empty string."""
        from core.game_session import GameSession

        session = GameSession()

        assert session.get_narrative({}) == ""


class TestCompleteChapter:
    """Test complete_chapter."""

    def test_complete_chapter_custom_mode(self, mock_case_simple):
        """Custom mode should return None."""
        from core.game_session import GameSession

        session = GameSession()
        session.start_custom(mock_case_simple)

        result = session.evaluate_chapter()
        assert session.complete_chapter(result) is None

    def test_complete_chapter_no_mode(self):
        """No mode should return None."""
        from core.game_session import GameSession

        session = GameSession()

        assert session.complete_chapter({}) is None


class TestSessionModeError:
    """Test custom exception class."""

    def test_session_mode_error_is_thebox_error(self):
        """SessionModeError should inherit from TheBoxError."""
        from core.exceptions import TheBoxError
        from core.game_session import SessionModeError

        assert issubclass(SessionModeError, TheBoxError)

    def test_session_mode_error_message(self):
        """SessionModeError should carry message."""
        from core.game_session import SessionModeError

        err = SessionModeError("test error")
        assert str(err) == "test error"
