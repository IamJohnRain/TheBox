"""Tests for constrained case generator - Phase 9."""

from unittest.mock import patch


class TestConstrainedGeneration:
    """Test constrained case generation."""

    def test_basic_constraints(self):
        """Should generate case with basic constraints."""
        from core.case_generator import generate_case_with_constraints

        constraints = {
            "background": "一起工厂失窃案",
            "difficulty": "easy",
        }

        with patch("core.case_generator.generate_case") as mock_gen:
            mock_gen.return_value = {
                "case_id": "test",
                "title": "测试案件",
                "victim": "测试",
                "cause_of_death": "无",
                "crime_scene": "工厂",
                "truth": "测试真相",
                "culprit_name": "张三",
                "suspects": [
                    {
                        "name": "张三",
                        "role": "工人",
                        "personality": "暴躁",
                        "knowledge": "知道",
                        "forbidden_to_reveal": ["秘密"],
                    }
                ],
                "evidences": [],
            }

            case_data = generate_case_with_constraints(constraints)

            assert case_data["case_id"] == "test"
            mock_gen.assert_called_once()

    def test_story_variables_injection(self):
        """Should inject story variables into background."""
        from core.case_generator import generate_case_with_constraints

        constraints = {"background": "测试案件"}
        story_variables = {"met_informant": True, "key_clue": "日记"}

        with patch("core.case_generator.generate_case") as mock_gen:
            mock_gen.return_value = {
                "case_id": "test",
                "culprit_name": "张三",
                "suspects": [],
                "evidences": [],
            }

            generate_case_with_constraints(constraints, story_variables)

            # Check that background includes variables
            call_args = mock_gen.call_args
            background = call_args[0][0] if call_args[0] else call_args[1].get("background", "")
            assert "met_informant" in background or "日记" in background

    def test_require_variables_injection(self):
        """Should inject require_variables into background."""
        from core.case_generator import generate_case_with_constraints

        constraints = {
            "background": "测试案件",
            "require_variables": {"must_mention": "红色日记本"},
        }

        with patch("core.case_generator.generate_case") as mock_gen:
            mock_gen.return_value = {
                "case_id": "test",
                "culprit_name": "张三",
                "suspects": [],
                "evidences": [],
            }

            generate_case_with_constraints(constraints)

            call_args = mock_gen.call_args
            background = call_args[0][0]
            assert "红色日记本" in background

    def test_suspect_count_hint_in_background(self):
        """Should add suspect count hint to background."""
        from core.case_generator import generate_case_with_constraints

        constraints = {
            "background": "测试案件",
            "suspect_count": {"min": 3, "max": 4},
        }

        with patch("core.case_generator.generate_case") as mock_gen:
            mock_gen.return_value = {
                "case_id": "test",
                "culprit_name": "张三",
                "suspects": [],
                "evidences": [],
            }

            generate_case_with_constraints(constraints)

            call_args = mock_gen.call_args
            background = call_args[0][0]
            assert "3" in background and "4" in background

    def test_suspect_count_warning_on_insufficient(self):
        """Should warn when generated suspect count is below minimum."""
        from core.case_generator import generate_case_with_constraints

        constraints = {
            "background": "测试案件",
            "suspect_count": {"min": 3, "max": 5},
        }

        with patch("core.case_generator.generate_case") as mock_gen:
            mock_gen.return_value = {
                "case_id": "test",
                "culprit_name": "张三",
                "suspects": [{"name": "张三"}],
                "evidences": [],
            }

            with patch("core.case_generator.logger") as mock_logger:
                generate_case_with_constraints(constraints)
                mock_logger.warning.assert_called()

    def test_default_background(self):
        """Should use default background when none provided."""
        from core.case_generator import generate_case_with_constraints

        constraints = {}

        with patch("core.case_generator.generate_case") as mock_gen:
            mock_gen.return_value = {
                "case_id": "test",
                "culprit_name": "张三",
                "suspects": [],
                "evidences": [],
            }

            generate_case_with_constraints(constraints)

            call_args = mock_gen.call_args
            background = call_args[0][0]
            assert "神秘的案件" in background

    def test_difficulty_embedded_in_background(self):
        """Should embed difficulty hint into background for non-normal difficulty."""
        from core.case_generator import generate_case_with_constraints

        constraints = {
            "background": "测试案件",
            "difficulty": "hard",
        }

        with patch("core.case_generator.generate_case") as mock_gen:
            mock_gen.return_value = {
                "case_id": "test",
                "culprit_name": "张三",
                "suspects": [],
                "evidences": [],
            }

            generate_case_with_constraints(constraints)

            call_args = mock_gen.call_args
            background = call_args[0][0]
            assert "困难难度" in background

    def test_normal_difficulty_no_hint(self):
        """Should not add difficulty hint for normal difficulty."""
        from core.case_generator import generate_case_with_constraints

        constraints = {
            "background": "测试案件",
            "difficulty": "normal",
        }

        with patch("core.case_generator.generate_case") as mock_gen:
            mock_gen.return_value = {
                "case_id": "test",
                "culprit_name": "张三",
                "suspects": [],
                "evidences": [],
            }

            generate_case_with_constraints(constraints)

            call_args = mock_gen.call_args
            background = call_args[0][0]
            # Background should just be the base, no difficulty hint
            assert "难度要求" not in background


class TestStoryEngineGenerated:
    """Test StoryEngine with generated chapters."""

    def test_generated_chapter_calls_generator(self):
        """Generated chapters should call generate_case_with_constraints."""
        from core.story_engine import StoryEngine

        story_data = {
            "story_id": "test",
            "title": "测试",
            "chapters": [
                {
                    "chapter_id": "ch01",
                    "seq": 1,
                    "title": "生成章节",
                    "type": "generated",
                    "narrative": {"opening": "测试"},
                    "case_constraints": {"background": "测试"},
                    "branch": {"conditions": [{"next": "ending"}]},
                }
            ],
            "endings": [{"id": "ending", "title": "结局", "desc": "结束"}],
        }

        engine = StoryEngine(story_data)

        with patch("core.case_generator.generate_case_with_constraints") as mock_gen:
            mock_gen.return_value = {
                "case_id": "gen_01",
                "culprit_name": "张三",
                "suspects": [{"name": "张三"}],
                "evidences": [],
            }

            case_data = engine.start_chapter()

            assert case_data["case_id"] == "gen_01"
            mock_gen.assert_called_once()

    def test_generated_chapter_passes_story_variables(self):
        """Generated chapters should pass story variables to generator."""
        from core.story_engine import StoryEngine

        story_data = {
            "story_id": "test",
            "title": "测试",
            "chapters": [
                {
                    "chapter_id": "ch01",
                    "seq": 1,
                    "title": "生成章节",
                    "type": "generated",
                    "narrative": {"opening": "测试"},
                    "case_constraints": {"background": "测试"},
                    "branch": {"conditions": [{"next": "ending"}]},
                }
            ],
            "endings": [{"id": "ending", "title": "结局", "desc": "结束"}],
        }

        engine = StoryEngine(story_data)
        engine.story_variables = {"met_informant": True}

        with patch("core.case_generator.generate_case_with_constraints") as mock_gen:
            mock_gen.return_value = {
                "case_id": "gen_01",
                "culprit_name": "张三",
                "suspects": [{"name": "张三"}],
                "evidences": [],
            }

            engine.start_chapter()

            call_kwargs = mock_gen.call_args
            assert call_kwargs[1].get("story_variables") == {"met_informant": True} or (
                len(call_kwargs[0]) > 1 and call_kwargs[0][1] == {"met_informant": True}
            )

    def test_generated_chapter_merges_carried_evidence(self):
        """Generated chapters should merge carried evidence."""
        from core.story_engine import StoryEngine

        story_data = {
            "story_id": "test",
            "title": "测试",
            "chapters": [
                {
                    "chapter_id": "ch01",
                    "seq": 1,
                    "title": "生成章节",
                    "type": "generated",
                    "narrative": {"opening": "测试"},
                    "case_constraints": {"background": "测试"},
                    "branch": {"conditions": [{"next": "ending"}]},
                }
            ],
            "endings": [{"id": "ending", "title": "结局", "desc": "结束"}],
        }

        engine = StoryEngine(story_data)
        engine.carried_evidence = [
            {"id": "ev_carry", "name": "携带的证据", "description": "从上一章带来的证据"}
        ]

        with patch("core.case_generator.generate_case_with_constraints") as mock_gen:
            mock_gen.return_value = {
                "case_id": "gen_01",
                "culprit_name": "张三",
                "suspects": [{"name": "张三"}],
                "evidences": [],
            }

            case_data = engine.start_chapter()

            # Carried evidence should be merged in
            evidence_ids = [e["id"] for e in case_data["evidences"]]
            assert "ev_carry" in evidence_ids

    def test_scripted_chapter_still_works(self):
        """Scripted chapters should still work after generated chapter support."""
        from core.story_engine import StoryEngine

        story_data = {
            "story_id": "test",
            "title": "测试",
            "chapters": [
                {
                    "chapter_id": "ch01",
                    "seq": 1,
                    "title": "脚本章节",
                    "type": "scripted",
                    "narrative": {"opening": "测试"},
                    "case_data": {
                        "case_id": "scripted_01",
                        "culprit_name": "李四",
                        "suspects": [{"name": "李四"}],
                        "evidences": [],
                    },
                    "branch": {"conditions": [{"next": "ending"}]},
                }
            ],
            "endings": [{"id": "ending", "title": "结局", "desc": "结束"}],
        }

        engine = StoryEngine(story_data)
        case_data = engine.start_chapter()

        assert case_data["case_id"] == "scripted_01"
