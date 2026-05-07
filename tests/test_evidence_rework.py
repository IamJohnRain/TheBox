"""Tests for evidence system rework - Phase 1c."""

import json
from unittest.mock import patch, MagicMock


class TestRespondEvidence:
    """Test respond_evidence method."""

    def test_respond_evidence_no_name_in_prompt(self, mock_case_simple):
        """respond_evidence should not include evidence name in prompt."""
        from core.suspect_agent import SuspectAgent

        suspect_data = mock_case_simple["suspects"][0]
        agent = SuspectAgent(suspect_data, mock_case_simple["title"])

        mock_response = json.dumps({"reply": "我不认识这个", "secret_triggered": None})

        with patch("core.suspect_agent.llm_client") as mock_llm:
            mock_llm.is_initialized = True
            mock_llm.chat_completion.return_value = mock_response

            agent.respond_evidence("锄头上有血迹", "physical")

            # Check that the prompt sent to LLM does not contain evidence name
            call_args = mock_llm.chat_completion.call_args
            messages = call_args.kwargs.get("messages", call_args[1].get("messages", []))
            user_msg = [m for m in messages if m["role"] == "user"][0]

            assert "沾血的锄头" not in user_msg["content"]  # evidence name not in prompt
            assert "physical" in user_msg["content"]  # evidence type in prompt
            assert "血迹" in user_msg["content"]  # description in prompt

    def test_respond_evidence_returns_correct_format(self, mock_case_simple):
        """respond_evidence should return reply and secret_triggered."""
        from core.suspect_agent import SuspectAgent

        suspect_data = mock_case_simple["suspects"][0]
        agent = SuspectAgent(suspect_data, mock_case_simple["title"])

        mock_response = json.dumps({"reply": "这不能说明什么", "secret_triggered": None})

        with patch("core.suspect_agent.llm_client") as mock_llm:
            mock_llm.is_initialized = True
            mock_llm.chat_completion.return_value = mock_response

            result = agent.respond_evidence("描述", "physical")

            assert "reply" in result
            assert "secret_triggered" in result
            assert "pressure_change" not in result


class TestPostprocessConfessionLink:
    """Test _postprocess links with confession system."""

    def test_low_confession_blocks_secret_trigger(self, mock_case_simple):
        """Low confession level should block secret_triggered."""
        from core.suspect_agent import SuspectAgent

        suspect_data = mock_case_simple["suspects"][0]
        agent = SuspectAgent(suspect_data, mock_case_simple["title"])
        agent.confession_level = 0  # Low level

        result = {"reply": "是的，是我用锄头打的", "secret_triggered": None}
        agent._postprocess(result)

        # Should be blocked and replaced
        assert result["secret_triggered"] is None
        assert "略显紧张" in result["reply"]

    def test_high_confession_allows_secret_trigger(self, mock_case_simple):
        """High confession level should allow secret_triggered."""
        from core.suspect_agent import SuspectAgent

        suspect_data = mock_case_simple["suspects"][0]
        agent = SuspectAgent(suspect_data, mock_case_simple["title"])
        agent.confession_level = 3  # High level

        result = {"reply": "是的，是我用锄头打的", "secret_triggered": None}
        agent._postprocess(result)

        # Should trigger secret
        assert result["secret_triggered"] == "锄头"

    def test_no_forbidden_content_passes_through(self, mock_case_simple):
        """When no forbidden content is found, reply passes through unchanged."""
        from core.suspect_agent import SuspectAgent

        suspect_data = mock_case_simple["suspects"][0]
        agent = SuspectAgent(suspect_data, mock_case_simple["title"])

        result = {"reply": "我不知道你在说什么", "secret_triggered": None}
        agent._postprocess(result)

        assert result["reply"] == "我不知道你在说什么"
        assert result["secret_triggered"] is None

    def test_default_confession_level_blocks(self, mock_case_simple):
        """Without confession_level attribute, default (0) should block."""
        from core.suspect_agent import SuspectAgent

        suspect_data = mock_case_simple["suspects"][0]
        agent = SuspectAgent(suspect_data, mock_case_simple["title"])
        # Don't set confession_level - should default to 0 via getattr

        result = {"reply": "是的，是我用锄头打的", "secret_triggered": None}
        agent._postprocess(result)

        assert result["secret_triggered"] is None
        assert "略显紧张" in result["reply"]

    def test_confession_level_2_blocks(self, mock_case_simple):
        """Confession level 2 (< 3) should still block."""
        from core.suspect_agent import SuspectAgent

        suspect_data = mock_case_simple["suspects"][0]
        agent = SuspectAgent(suspect_data, mock_case_simple["title"])
        agent.confession_level = 2

        result = {"reply": "是的，是我用锄头打的", "secret_triggered": None}
        agent._postprocess(result)

        assert result["secret_triggered"] is None


class TestCheckVictory:
    """Test _check_victory unified victory check."""

    def test_confession_level_4_triggers_victory(self, mock_case_simple):
        """Confession level 4 should trigger breakdown victory."""
        from core.interrogation import InterrogationEngine

        engine = InterrogationEngine(mock_case_simple)
        engine.state = "interrogating"
        suspect = engine.suspects[0]
        suspect.confession_level = 4

        result = {"reply": "我全招了", "secret_triggered": None}
        victory = engine._check_victory(suspect, result)

        assert victory is not None
        assert victory["new_state"] == "breakdown"

    def test_secret_with_high_confession_triggers_victory(self, mock_case_simple):
        """secret_triggered with confession >= 3 should trigger victory."""
        from core.interrogation import InterrogationEngine

        engine = InterrogationEngine(mock_case_simple)
        engine.state = "interrogating"
        suspect = engine.suspects[0]
        suspect.confession_level = 3

        result = {"reply": "我不小心...", "secret_triggered": "锄头"}
        victory = engine._check_victory(suspect, result)

        assert victory is not None
        assert victory["new_state"] == "breakdown"

    def test_secret_with_low_confession_no_victory(self, mock_case_simple):
        """secret_triggered with confession < 3 should NOT trigger victory."""
        from core.interrogation import InterrogationEngine

        engine = InterrogationEngine(mock_case_simple)
        engine.state = "interrogating"
        suspect = engine.suspects[0]
        suspect.confession_level = 2

        result = {"reply": "我不小心...", "secret_triggered": "锄头"}
        victory = engine._check_victory(suspect, result)

        assert victory is None

    def test_no_secret_no_confession_no_victory(self, mock_case_simple):
        """No secret_triggered and low confession should not trigger victory."""
        from core.interrogation import InterrogationEngine

        engine = InterrogationEngine(mock_case_simple)
        engine.state = "interrogating"
        suspect = engine.suspects[0]

        result = {"reply": "我不知道", "secret_triggered": None}
        victory = engine._check_victory(suspect, result)

        assert victory is None

    def test_default_confession_level_no_victory(self, mock_case_simple):
        """Default confession level (0) should not trigger victory from secret."""
        from core.interrogation import InterrogationEngine

        engine = InterrogationEngine(mock_case_simple)
        engine.state = "interrogating"
        # No confession_level set -> defaults to 0
        suspect = engine.suspects[0]

        result = {"reply": "我说了", "secret_triggered": "锄头"}
        victory = engine._check_victory(suspect, result)

        assert victory is None

    def test_confession_level_4_priority_over_secret(self, mock_case_simple):
        """Confession level 4 should trigger even without secret_triggered."""
        from core.interrogation import InterrogationEngine

        engine = InterrogationEngine(mock_case_simple)
        engine.state = "interrogating"
        suspect = engine.suspects[0]
        suspect.confession_level = 4

        result = {"reply": "我全招了", "secret_triggered": None}
        victory = engine._check_victory(suspect, result)

        assert victory is not None
        assert "崩溃认罪" in victory["verdict_reason"]

    def test_no_duplicate_breakdown_if_already_breakdown(self, mock_case_simple):
        """_check_victory should not set breakdown if already in breakdown state for confession level 4."""
        from core.interrogation import InterrogationEngine

        engine = InterrogationEngine(mock_case_simple)
        engine.state = "breakdown"
        suspect = engine.suspects[0]
        suspect.confession_level = 4

        result = {"reply": "我全招了", "secret_triggered": None}
        victory = engine._check_victory(suspect, result)

        # Already in breakdown, confession level 4 check has a guard
        assert victory is None


class TestEvidencePressureCalculation:
    """Test that evidence pressure is calculated programmatically."""

    def test_correct_evidence_increases_pressure_programmatically(self, mock_case_simple):
        """Presenting correct evidence should use programmatic pressure calculation."""
        from core.interrogation import InterrogationEngine

        engine = InterrogationEngine(mock_case_simple)
        engine.select_suspect(0)
        suspect = engine.suspects[0]
        initial_pressure = suspect.pressure

        evidence = mock_case_simple["evidences"][0]
        assert evidence["related_suspect"] == suspect.name

        engine.submit_action(
            "present_evidence", "看看这个证据", evidence_id=evidence["id"]
        )

        # Pressure should increase but NOT by hardcoded 20
        # With default config: base=18, strength=8, multiplier=0.1
        # delta = 18 * (1 + 8 * 0.1) = 18 * 1.8 = 32
        # With default fear=50, defiance=50, soft_factor calculation:
        # fear_factor = 50/50 = 1.0, defiance_factor = 1/(1+0.5) = 0.667
        # raw_factor = 0.667, soft_factor = max(0.3, min(1.5, 0.667)) = 0.667
        # delta = 32 * 0.667 ≈ 21
        # But since SuspectAgent doesn't have fear/defiance by default, getattr returns 50
        actual_change = suspect.pressure - initial_pressure
        assert actual_change > 0
        assert actual_change != 20  # Not hardcoded +20

    def test_wrong_evidence_no_pressure_increase(self, mock_case_simple):
        """Presenting wrong evidence should not increase pressure from the evidence itself."""
        from core.interrogation import InterrogationEngine

        engine = InterrogationEngine(mock_case_simple)
        engine.select_suspect(1)  # Select the non-matching suspect
        suspect = engine.suspects[1]
        # Set pressure to a stable zone value to avoid per-turn dynamics changing it
        suspect.pressure = 50
        initial_pressure = suspect.pressure

        non_matching = mock_case_simple["evidences"][0]
        assert non_matching["related_suspect"] != suspect.name

        engine.submit_action(
            "present_evidence", "看看这个", evidence_id=non_matching["id"]
        )

        assert suspect.pressure == initial_pressure

    def test_wrong_evidence_creates_mistake_log(self, mock_case_simple):
        """Presenting wrong evidence should be logged in mistake_log."""
        from core.interrogation import InterrogationEngine

        engine = InterrogationEngine(mock_case_simple)
        engine.select_suspect(1)  # Select non-matching suspect

        non_matching = mock_case_simple["evidences"][0]
        engine.submit_action(
            "present_evidence", "看看这个", evidence_id=non_matching["id"]
        )

        assert hasattr(engine, 'mistake_log')
        assert len(engine.mistake_log) == 1
        assert engine.mistake_log[0]["type"] == "wrong_evidence"
        assert engine.mistake_log[0]["evidence_id"] == non_matching["id"]

    def test_present_evidence_uses_respond_evidence(self, mock_case_simple):
        """Present evidence should call respond_evidence instead of respond."""
        from core.interrogation import InterrogationEngine

        engine = InterrogationEngine(mock_case_simple)
        engine.select_suspect(0)

        # Replace suspect with a mock
        mock_suspect = MagicMock()
        mock_suspect.name = "李四"
        mock_suspect.pressure = 50
        mock_suspect.fear = 50
        mock_suspect.defiance = 50
        mock_suspect.empathy_susceptibility = 50
        mock_suspect.deception_skill = 50
        mock_suspect.loyalty = 50
        mock_suspect.credibility = 50
        mock_suspect.confession_level = 0
        mock_suspect.confession_progress = 0.0
        mock_suspect.turn_count = 0
        mock_suspect.memory = []
        # Ensure _last_proactive_turn is an int for _check_proactive
        mock_suspect._last_proactive_turn = -999
        mock_suspect.respond_evidence.return_value = {
            "reply": "我不认识这个证据",
            "secret_triggered": None,
            "rebuttal": False,
            "rebuttal_believable": False,
        }
        engine.suspects[0] = mock_suspect

        evidence = mock_case_simple["evidences"][0]
        engine.submit_action(
            "present_evidence", "看看这个证据", evidence_id=evidence["id"]
        )

        # Should call respond_evidence, NOT respond
        mock_suspect.respond_evidence.assert_called_once()
        mock_suspect.respond.assert_not_called()

        # Check the arguments passed
        call_args = mock_suspect.respond_evidence.call_args
        # First positional arg should be description, not evidence name
        assert call_args[0][0] == evidence["description"]
        assert call_args[0][1] == evidence["type"]
        # Evidence name should NOT be in the call
        assert evidence["name"] not in str(call_args)

    def test_submit_action_victory_check_integrated(self, mock_case_simple):
        """submit_action should use _check_victory for victory determination."""
        from core.interrogation import InterrogationEngine

        engine = InterrogationEngine(mock_case_simple)
        engine.select_suspect(0)
        suspect = engine.suspects[0]
        suspect.confession_level = 3

        # Set up the suspect to return a secret_triggered result
        evidence = mock_case_simple["evidences"][0]
        # We need to mock respond_evidence to return a triggered result
        from unittest.mock import patch
        with patch.object(suspect, 'respond_evidence', return_value={
            "reply": "好吧，是我做的",
            "secret_triggered": "锄头",
        }):
            events = engine.submit_action(
                "present_evidence", "看看这个", evidence_id=evidence["id"]
            )

            # Should have a state_change event
            state_events = [e for e in events if e["type"] == "state_change"]
            assert len(state_events) == 1
            assert state_events[0]["new_state"] == "breakdown"
