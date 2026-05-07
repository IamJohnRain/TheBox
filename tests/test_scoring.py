"""Tests for scoring system - Phase 4."""

import pytest


class TestScoringDimensions:
    """Test scoring dimension calculations."""

    def test_ap_efficiency(self):
        """AP efficiency should be remaining/total."""
        from core.scoring import calculate_score

        result = calculate_score({
            "ap_remaining": 10,
            "total_ap": 22,
            "confession_level": 0,
            "correct_evidence_count": 0,
            "related_evidence_count": 0,
            "total_evidence_presented": 0,
            "pressure_count": 0,
            "pressure_on_culprit": 0,
            "mistake_log": [],
        })

        # 10/22 = 45%
        assert result["dimensions"]["ap_efficiency"] == 45

    def test_confession_depth_nonlinear(self):
        """Confession depth should use nonlinear mapping."""
        from core.scoring import calculate_score

        for level, expected in [(0, 15), (1, 40), (2, 65), (3, 85), (4, 100)]:
            result = calculate_score({
                "confession_level": level,
                "ap_remaining": 0,
                "total_ap": 1,
                "correct_evidence_count": 0,
                "related_evidence_count": 0,
                "total_evidence_presented": 0,
                "pressure_count": 0,
                "pressure_on_culprit": 0,
                "mistake_log": [],
            })
            assert result["dimensions"]["confession_depth"] == expected

    def test_evidence_usage_with_related(self):
        """Evidence usage should reflect correct/related ratio."""
        from core.scoring import calculate_score

        result = calculate_score({
            "ap_remaining": 0,
            "total_ap": 22,
            "confession_level": 0,
            "correct_evidence_count": 3,
            "related_evidence_count": 4,
            "evidence_uses": 4,
            "total_evidence_presented": 3,
            "pressure_count": 0,
            "pressure_on_culprit": 0,
            "mistake_log": [],
        })

        # min(4, 4) = 4, 3/4 = 75%
        assert result["dimensions"]["evidence_usage"] == 75

    def test_evidence_usage_no_related(self):
        """Evidence usage should be 0 when no related evidence."""
        from core.scoring import calculate_score

        result = calculate_score({
            "ap_remaining": 0,
            "total_ap": 22,
            "confession_level": 0,
            "correct_evidence_count": 0,
            "related_evidence_count": 0,
            "total_evidence_presented": 0,
            "pressure_count": 0,
            "pressure_on_culprit": 0,
            "mistake_log": [],
        })

        assert result["dimensions"]["evidence_usage"] == 0

    def test_pressure_accuracy_with_data(self):
        """Pressure accuracy should reflect culprit/total ratio."""
        from core.scoring import calculate_score

        result = calculate_score({
            "ap_remaining": 0,
            "total_ap": 22,
            "confession_level": 0,
            "correct_evidence_count": 0,
            "related_evidence_count": 0,
            "total_evidence_presented": 0,
            "pressure_count": 4,
            "pressure_on_culprit": 3,
            "mistake_log": [],
        })

        # 3/4 = 75%
        assert result["dimensions"]["pressure_accuracy"] == 75

    def test_pressure_accuracy_no_data(self):
        """Pressure accuracy should default to 50 when no pressure used."""
        from core.scoring import calculate_score

        result = calculate_score({
            "ap_remaining": 0,
            "total_ap": 22,
            "confession_level": 0,
            "correct_evidence_count": 0,
            "related_evidence_count": 0,
            "total_evidence_presented": 0,
            "pressure_count": 0,
            "pressure_on_culprit": 0,
            "mistake_log": [],
        })

        assert result["dimensions"]["pressure_accuracy"] == 50


class TestOutcomeCaps:
    """Test outcome score caps."""

    def test_partial_cap(self):
        """Partial outcome should be capped at 74."""
        from core.scoring import calculate_score

        result = calculate_score({
            "outcome": "partial",
            "confession_level": 2,
            "ap_remaining": 20,
            "total_ap": 22,
            "correct_evidence_count": 3,
            "related_evidence_count": 3,
            "total_evidence_presented": 3,
            "pressure_count": 2,
            "pressure_on_culprit": 2,
            "mistake_log": [],
        })

        assert result["total_score"] <= 74

    def test_fail_cap(self):
        """Fail outcome should be capped at 59."""
        from core.scoring import calculate_score

        result = calculate_score({
            "outcome": "fail",
            "confession_level": 0,
            "ap_remaining": 0,
            "total_ap": 22,
            "correct_evidence_count": 0,
            "related_evidence_count": 0,
            "total_evidence_presented": 0,
            "pressure_count": 0,
            "pressure_on_culprit": 0,
            "mistake_log": [],
        })

        assert result["total_score"] <= 59

    def test_innocent_breakdown_cap(self):
        """Innocent breakdown should be capped at 49."""
        from core.scoring import calculate_score

        result = calculate_score({
            "outcome": "fail",
            "confession_level": 4,
            "ap_remaining": 10,
            "total_ap": 22,
            "correct_evidence_count": 0,
            "related_evidence_count": 0,
            "total_evidence_presented": 0,
            "pressure_count": 0,
            "pressure_on_culprit": 0,
            "mistake_log": [{"type": "innocent_breakdown"}],
        })

        assert result["total_score"] <= 49


class TestMistakePenalty:
    """Test mistake penalty calculation."""

    def test_no_mistakes_full_score(self):
        """No mistakes should give 100."""
        from core.scoring import calculate_score

        result = calculate_score({
            "confession_level": 0,
            "ap_remaining": 0,
            "total_ap": 1,
            "correct_evidence_count": 0,
            "related_evidence_count": 0,
            "total_evidence_presented": 0,
            "pressure_count": 0,
            "pressure_on_culprit": 0,
            "mistake_log": [],
        })

        assert result["dimensions"]["mistake_penalty"] == 100

    def test_mistakes_reduce_score(self):
        """Mistakes should reduce penalty score."""
        from core.scoring import calculate_score

        result = calculate_score({
            "confession_level": 0,
            "ap_remaining": 0,
            "total_ap": 1,
            "correct_evidence_count": 0,
            "related_evidence_count": 0,
            "total_evidence_presented": 0,
            "pressure_count": 0,
            "pressure_on_culprit": 0,
            "mistake_log": [{"type": "wrong_evidence"}, {"type": "wrong_pressure"}],
        })

        assert result["dimensions"]["mistake_penalty"] < 100

    def test_mistake_floor(self):
        """Mistake penalty should not go below score_floor."""
        from core.scoring import calculate_score

        result = calculate_score({
            "confession_level": 0,
            "ap_remaining": 0,
            "total_ap": 1,
            "correct_evidence_count": 0,
            "related_evidence_count": 0,
            "total_evidence_presented": 0,
            "pressure_count": 0,
            "pressure_on_culprit": 0,
            "mistake_log": [{"type": "wrong"}] * 20,
        })

        assert result["dimensions"]["mistake_penalty"] >= 20

    def test_innocent_breakdown_extra_penalty(self):
        """Innocent breakdown should apply extra penalty."""
        from core.scoring import calculate_score

        result = calculate_score({
            "confession_level": 0,
            "ap_remaining": 0,
            "total_ap": 1,
            "correct_evidence_count": 0,
            "related_evidence_count": 0,
            "total_evidence_presented": 0,
            "pressure_count": 0,
            "pressure_on_culprit": 0,
            "mistake_log": [{"type": "innocent_breakdown"}],
        })

        # 1 mistake: 100 - 15 = 85, then -30 for innocent_breakdown = 55
        assert result["dimensions"]["mistake_penalty"] == 55


class TestGradeCalculation:
    """Test grade calculation."""

    def test_grade_thresholds(self):
        """Grade should match thresholds."""
        from core.scoring import GRADE_THRESHOLDS

        assert GRADE_THRESHOLDS[0] == ("S", 90)
        assert GRADE_THRESHOLDS[1] == ("A", 75)
        assert GRADE_THRESHOLDS[2] == ("B", 60)
        assert GRADE_THRESHOLDS[3] == ("C", 40)
        assert GRADE_THRESHOLDS[4] == ("D", 0)

    def test_grade_s(self):
        """Score >= 90 should get S grade."""
        from core.scoring import calculate_score

        result = calculate_score({
            "outcome": "win",
            "confession_level": 4,
            "ap_remaining": 22,
            "total_ap": 22,
            "correct_evidence_count": 4,
            "related_evidence_count": 4,
            "total_evidence_presented": 4,
            "pressure_count": 4,
            "pressure_on_culprit": 4,
            "mistake_log": [],
        })

        assert result["grade"] == "S"
        assert result["grade_value"] == 5
        assert result["exp_multiplier"] == 1.5

    def test_grade_d(self):
        """Low score should get D grade."""
        from core.scoring import calculate_score

        result = calculate_score({
            "outcome": "fail",
            "confession_level": 0,
            "ap_remaining": 0,
            "total_ap": 22,
            "correct_evidence_count": 0,
            "related_evidence_count": 0,
            "total_evidence_presented": 0,
            "pressure_count": 0,
            "pressure_on_culprit": 0,
            "mistake_log": [],
        })

        assert result["grade"] == "D"
        assert result["grade_value"] == 1
        assert result["exp_multiplier"] == 0.5


class TestExperienceCalculation:
    """Test experience calculation."""

    def test_basic_experience(self):
        """Basic experience should include confession + evidence + completion."""
        from core.scoring import calculate_score, calculate_experience

        score_result = calculate_score({
            "outcome": "fail",
            "confession_level": 0,
            "ap_remaining": 0,
            "total_ap": 1,
            "correct_evidence_count": 0,
            "related_evidence_count": 0,
            "total_evidence_presented": 0,
            "pressure_count": 0,
            "pressure_on_culprit": 0,
            "mistake_log": [],
        })

        exp = calculate_experience(score_result, {
            "confession_level": 0,
            "total_evidence_presented": 0,
        })

        # 0*10 + 0*5 + 20 = 20, * 0.5 (D grade) = 10
        assert exp == 10

    def test_experience_with_multiplier(self):
        """Experience should be multiplied by grade multiplier."""
        from core.scoring import calculate_score, calculate_experience

        score_result = calculate_score({
            "outcome": "win",
            "confession_level": 4,
            "ap_remaining": 22,
            "total_ap": 22,
            "correct_evidence_count": 4,
            "related_evidence_count": 4,
            "total_evidence_presented": 4,
            "pressure_count": 4,
            "pressure_on_culprit": 4,
            "mistake_log": [],
        })

        exp = calculate_experience(score_result, {
            "confession_level": 4,
            "total_evidence_presented": 4,
        })

        # 4*10 + 4*5 + 20 = 80, * 1.5 (S grade) = 120
        assert exp == 120


class TestDifficultySystem:
    """Test difficulty preset system."""

    def test_easy_preset(self):
        """Easy difficulty should return correct preset."""
        from core.scoring import get_difficulty_preset

        preset = get_difficulty_preset("easy")
        assert preset["total_ap"] == 26
        assert preset["suspects"] == 2
        assert preset["unlock_level"] == 1

    def test_normal_preset(self):
        """Normal difficulty should return correct preset."""
        from core.scoring import get_difficulty_preset

        preset = get_difficulty_preset("normal")
        assert preset["total_ap"] == 22

    def test_invalid_difficulty(self):
        """Invalid difficulty should raise ValueError."""
        from core.scoring import get_difficulty_preset

        with pytest.raises(ValueError, match="无效难度"):
            get_difficulty_preset("impossible")

    def test_available_difficulties_low_level(self):
        """Low level player should only have easy difficulty."""
        from core.scoring import get_available_difficulties

        available = get_available_difficulties(player_level=1)
        assert "easy" in available
        assert "nightmare" not in available

    def test_available_difficulties_max_level(self):
        """High level player should have all difficulties."""
        from core.scoring import get_available_difficulties

        available = get_available_difficulties(player_level=20)
        assert "easy" in available
        assert "normal" in available
        assert "hard" in available
        assert "nightmare" in available


class TestLLMScoreFallback:
    """Test LLM score fallback behavior."""

    def test_llm_uninitialized_returns_defaults(self):
        """When LLM is not initialized, should return default scores."""
        from core.scoring import _llm_score

        result = _llm_score({})
        assert result["interrogation_strategy"] == 50
        assert result["reasoning_accuracy"] == 50
        assert result["detail"] == "LLM 未初始化"


class TestScoringResultStructure:
    """Test that calculate_score returns all required fields."""

    def test_result_has_all_fields(self):
        """calculate_score should return all required fields."""
        from core.scoring import calculate_score

        result = calculate_score({
            "confession_level": 0,
            "ap_remaining": 0,
            "total_ap": 1,
            "correct_evidence_count": 0,
            "related_evidence_count": 0,
            "total_evidence_presented": 0,
            "pressure_count": 0,
            "pressure_on_culprit": 0,
            "mistake_log": [],
        })

        assert "dimensions" in result
        assert "total_score" in result
        assert "grade" in result
        assert "grade_value" in result
        assert "exp_multiplier" in result
        assert "detail" in result

    def test_all_dimensions_present(self):
        """All 8 scoring dimensions should be present."""
        from core.scoring import calculate_score, SCORING_DIMENSIONS

        result = calculate_score({
            "confession_level": 0,
            "ap_remaining": 0,
            "total_ap": 1,
            "correct_evidence_count": 0,
            "related_evidence_count": 0,
            "total_evidence_presented": 0,
            "pressure_count": 0,
            "pressure_on_culprit": 0,
            "mistake_log": [],
        })

        for dim in SCORING_DIMENSIONS:
            assert dim in result["dimensions"], f"Missing dimension: {dim}"
