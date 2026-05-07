"""Tests for scripts.validate_case.validate_case and its sub-checks.

Covers three scenarios:
1. A correct case that passes all validation checks.
2. A case with a missing motive element in the truth.
3. A case where multiple suspects cover all three elements (non-unique culprit).
"""

from scripts.validate_case import (
    check_motive_means_opportunity,
    check_schema,
    check_unique_culprit,
    validate_case,
)


# ---------------------------------------------------------------------------
# Hand-crafted test data
# ---------------------------------------------------------------------------

# A well-formed case that should pass all three validation checks.
# - truth contains motive (因怨恨), means (用锄头), opportunity (争执中)
# - only the culprit (李四) covers all three elements via knowledge
# - the other suspect (王芳) covers zero elements
VALID_CASE = {
    "case_id": "vc_001",
    "title": "村庄命案",
    "victim": "老张",
    "cause_of_death": "钝器击打",
    "crime_scene": "村口工具房",
    "truth": "邻居李四因怨恨老张，争执中用锄头打死老张。",
    "culprit_name": "李四",
    "suspects": [
        {
            "name": "李四",
            "role": "邻居",
            "personality": "脾气暴躁",
            "knowledge": "我怨恨老张很久了，那天争执中我用锄头打了他。",
            "forbidden_to_reveal": ["锄头", "打死", "我打的"],
        },
        {
            "name": "王芳",
            "role": "路人",
            "personality": "胆小怕事",
            "knowledge": "我那天不在家，回来发现他死了。",
            "forbidden_to_reveal": ["我杀的"],
        },
    ],
    "evidences": [
        {"id": "e1", "name": "沾血的锄头", "description": "锄头上有血迹", "related_suspect": "李四"},
    ],
    "interrogation_time_limit_sec": 600,
}

# A case whose truth is missing any motive keyword (因/因为/怨恨/报复/…).
# Means (用铁锤) and opportunity (争执中) are still present.
MISSING_MOTIVE_CASE = {
    "case_id": "vc_002",
    "title": "工厂事故案",
    "victim": "陈明",
    "cause_of_death": "钝器击打",
    "crime_scene": "工厂仓库",
    "truth": "工人赵六和陈明在仓库争执中用铁锤击打陈明头部致死。",
    "culprit_name": "赵六",
    "suspects": [
        {
            "name": "赵六",
            "role": "工友",
            "personality": "沉默寡言",
            "knowledge": "那天争执中我用铁锤打了他。",
            "forbidden_to_reveal": ["铁锤", "我打的"],
        },
        {
            "name": "周七",
            "role": "保安",
            "personality": "正直",
            "knowledge": "我听到仓库有争吵声，赶过去时陈明已经倒地。",
            "forbidden_to_reveal": ["我杀的"],
        },
    ],
    "evidences": [
        {"id": "e1", "name": "铁锤", "description": "仓库铁锤上有血迹", "related_suspect": "赵六"},
    ],
    "interrogation_time_limit_sec": 600,
}

# A case where *both* suspects' knowledge covers motive, means, and opportunity,
# making the culprit non-unique from the coverage perspective.
MULTIPLE_CULPRIT_CASE = {
    "case_id": "vc_003",
    "title": "茶馆投毒案",
    "victim": "钱掌柜",
    "cause_of_death": "中毒",
    "crime_scene": "茶馆后院",
    "truth": "伙计孙八因怨恨钱掌柜，争执中用毒药毒死了钱掌柜。",
    "culprit_name": "孙八",
    "suspects": [
        {
            "name": "孙八",
            "role": "伙计",
            "personality": "阴沉",
            "knowledge": "我怨恨钱掌柜，那天争执中我用毒药毒死了他。",
            "forbidden_to_reveal": ["毒药", "我毒的"],
        },
        {
            "name": "吴九",
            "role": "账房",
            "personality": "精明",
            "knowledge": "我也怨恨钱掌柜，那天争执中我看到了毒药。",
            "forbidden_to_reveal": ["我杀的"],
        },
    ],
    "evidences": [
        {"id": "e1", "name": "毒药瓶", "description": "后院发现毒药瓶", "related_suspect": "孙八"},
    ],
    "interrogation_time_limit_sec": 600,
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestValidateCaseCorrectCase:
    """Scenario 1: a correct case should pass all validation checks."""

    def test_schema_check_passes(self):
        """check_schema should return True for a well-formed case."""
        passed, message = check_schema(VALID_CASE)
        assert passed, f"Schema check failed: {message}"

    def test_motive_means_opportunity_check_passes(self):
        """check_motive_means_opportunity should pass when truth has all three
        elements and suspects' combined knowledge covers them."""
        passed, message = check_motive_means_opportunity(VALID_CASE)
        assert passed, f"Motive-means-opportunity check failed: {message}"

    def test_unique_culprit_check_passes(self):
        """check_unique_culprit should pass when exactly one suspect covers
        all three elements."""
        passed, message = check_unique_culprit(VALID_CASE)
        assert passed, f"Unique culprit check failed: {message}"

    def test_validate_case_all_pass(self):
        """validate_case should return all_pass=True with three passing results."""
        all_pass, results = validate_case(VALID_CASE)
        assert all_pass, f"Overall validation failed: {results}"
        assert len(results) == 3
        for r in results:
            assert r.startswith("[通过]"), f"Unexpected failure: {r}"


class TestValidateCaseMissingMotive:
    """Scenario 2: a case whose truth lacks a motive element."""

    def test_schema_check_still_passes(self):
        """The case structurally conforms to the JSON schema; only logic
        checks should catch the missing motive."""
        passed, message = check_schema(MISSING_MOTIVE_CASE)
        assert passed, f"Schema check unexpectedly failed: {message}"

    def test_motive_means_opportunity_fails(self):
        """check_motive_means_opportunity should fail because the truth
        contains no motive keyword."""
        passed, message = check_motive_means_opportunity(MISSING_MOTIVE_CASE)
        assert not passed, "Expected failure due to missing motive"
        assert "motive" in message, f"Error message should mention 'motive': {message}"

    def test_validate_case_overall_fails(self):
        """validate_case should return all_pass=False."""
        all_pass, results = validate_case(MISSING_MOTIVE_CASE)
        assert not all_pass, "Expected overall validation to fail"
        # At least one result should be a failure
        failed = [r for r in results if r.startswith("[失败]")]
        assert len(failed) >= 1, f"Expected at least one failure: {results}"


class TestValidateCaseMultipleCulprits:
    """Scenario 3: multiple suspects cover all three elements."""

    def test_schema_check_passes(self):
        """The case structurally conforms to the JSON schema."""
        passed, message = check_schema(MULTIPLE_CULPRIT_CASE)
        assert passed, f"Schema check unexpectedly failed: {message}"

    def test_motive_means_opportunity_passes(self):
        """check_motive_means_opportunity should still pass because all
        elements are present and covered by suspects' knowledge."""
        passed, message = check_motive_means_opportunity(MULTIPLE_CULPRIT_CASE)
        assert passed, f"Motive-means-opportunity check failed: {message}"

    def test_unique_culprit_detects_multiple(self):
        """check_unique_culprit should detect that multiple suspects cover
        all three elements.  The function returns True (non-unique culprit
        is not a hard failure) but the message must mention the situation."""
        passed, message = check_unique_culprit(MULTIPLE_CULPRIT_CASE)
        # The current implementation returns True for multiple coverage
        assert "多个嫌疑人覆盖全部三要素" in message, (
            f"Expected message about multiple suspects, got: {message}"
        )

    def test_validate_case_catches_non_unique(self):
        """validate_case results should contain a message about multiple
        suspects covering all three elements."""
        all_pass, results = validate_case(MULTIPLE_CULPRIT_CASE)
        # Concatenate all results to search for the non-unique-culprit signal
        combined = " ".join(results)
        assert "多个嫌疑人覆盖全部三要素" in combined, (
            f"Expected non-unique-culprit detection in results: {results}"
        )
