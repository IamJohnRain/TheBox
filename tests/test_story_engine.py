"""Tests for StoryEngine - Phase 6."""

import pytest
from schemas.story import ChapterResult


class TestStoryLoader:
    """Test story loading."""

    def test_load_test_story(self):
        """Should load test story successfully."""
        from core.story_loader import load_story

        story = load_story("test_story")

        assert story["story_id"] == "test_story"
        assert len(story["chapters"]) == 2
        assert len(story["endings"]) == 2

    def test_load_nonexistent_raises(self):
        """Loading nonexistent story should raise."""
        from core.story_loader import StoryLoadError, load_story

        with pytest.raises(StoryLoadError):
            load_story("nonexistent")


class TestStoryEngine:
    """Test StoryEngine chapter flow."""

    def test_initial_chapter(self):
        """Should start at first chapter."""
        from core.story_loader import load_story
        from core.story_engine import StoryEngine

        story = load_story("test_story")
        engine = StoryEngine(story)

        assert engine.current_chapter_id == "ch01"

    def test_start_chapter_returns_case_data(self):
        """start_chapter should return case data."""
        from core.story_loader import load_story
        from core.story_engine import StoryEngine

        story = load_story("test_story")
        engine = StoryEngine(story)

        case_data = engine.start_chapter()

        assert case_data["case_id"] == "test_ch01"
        assert case_data["culprit_name"] == "嫌疑人A"

    def test_win_goes_to_ending(self):
        """Win result should go to ending."""
        from core.story_loader import load_story
        from core.story_engine import StoryEngine

        story = load_story("test_story")
        engine = StoryEngine(story)
        engine.start_chapter()

        result = ChapterResult(
            result="win",
            confession_level=4,
            evidence_count=1,
            ap_remaining_pct=0.5,
            suspect_name="嫌疑人A",
            culprit_name="嫌疑人A",
            verdict_reason="测试",
        )

        next_id = engine.complete_chapter(result)

        assert next_id == "ending_good"
        assert engine.is_ending(next_id)

    def test_partial_goes_to_next_chapter(self):
        """Partial result should go to next chapter."""
        from core.story_loader import load_story
        from core.story_engine import StoryEngine

        story = load_story("test_story")
        engine = StoryEngine(story)
        engine.start_chapter()

        result = ChapterResult(
            result="partial",
            confession_level=2,
            evidence_count=1,
            ap_remaining_pct=0.3,
            suspect_name="嫌疑人A",
            culprit_name="嫌疑人A",
            verdict_reason="测试",
        )

        next_id = engine.complete_chapter(result)

        assert next_id == "ch02"

    def test_get_narrative(self):
        """get_narrative should return correct text."""
        from core.story_loader import load_story
        from core.story_engine import StoryEngine

        story = load_story("test_story")
        engine = StoryEngine(story)

        result = ChapterResult(
            result="win",
            confession_level=4,
            evidence_count=1,
            ap_remaining_pct=0.5,
            suspect_name="嫌疑人A",
            culprit_name="嫌疑人A",
            verdict_reason="测试",
        )

        narrative = engine.get_narrative(result)

        assert "成功" in narrative


class TestGameSessionStory:
    """Test GameSession with story mode."""

    def test_start_story_loads_engine(self):
        """Starting story should load StoryEngine."""
        from core.game_session import GameSession

        session = GameSession()
        session.start_story("test_story")

        assert session.mode == "story"
        assert session.story_engine is not None
        assert session.story_engine.current_chapter_id == "ch01"
