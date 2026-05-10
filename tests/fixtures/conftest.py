import json
from pathlib import Path
from unittest.mock import Mock

import pytest

FIXTURES_DIR = Path(__file__).parent


@pytest.fixture
def mock_case_simple():
    with open(FIXTURES_DIR / "mock_cases" / "simple.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def mock_suspect_agent():
    from schemas.interface_definitions import SuspectAgentProtocol

    mock = Mock(spec=SuspectAgentProtocol)
    mock.name = "张三"
    mock.pressure = 50
    mock.fear = 50
    mock.defiance = 50
    mock.empathy_susceptibility = 50
    mock.deception_skill = 50
    mock.loyalty = 50
    mock.credibility = 50
    mock.confession_level = 0
    mock.confession_progress = 0.0
    mock.turn_count = 0
    mock._suspect_data = {"personality": "暴躁"}
    mock.respond.return_value = {
        "reply": "我是无辜的",
        "secret_triggered": None,
    }
    mock.respond_evidence.return_value = {
        "reply": "我是无辜的",
        "secret_triggered": None,
        "rebuttal": False,
        "rebuttal_believable": False,
    }
    mock.update_confession_progress.return_value = 0.02
    mock.check_confession_upgrade.return_value = None
    return mock


@pytest.fixture
def mock_engine(mock_case_simple):
    from schemas.interface_definitions import SuspectAgentProtocol

    try:
        from core.interrogation import InterrogationEngine

        engine = InterrogationEngine(mock_case_simple)
        for i in range(len(engine.suspects)):
            mock_agent = Mock(spec=SuspectAgentProtocol)
            mock_agent.name = engine.suspects[i].name
            mock_agent.pressure = 50
            mock_agent.fear = 50
            mock_agent.defiance = 50
            mock_agent.empathy_susceptibility = 50
            mock_agent.deception_skill = 50
            mock_agent.loyalty = 50
            mock_agent.credibility = 50
            mock_agent.confession_level = 0
            mock_agent.confession_progress = 0.0
            mock_agent.turn_count = 0
            mock_agent.memory = []
            mock_agent._suspect_data = {"personality": "暴躁"}
            mock_agent.respond.return_value = {
                "reply": "测试回复",
                "secret_triggered": None,
            }
            mock_agent.respond_evidence.return_value = {
                "reply": "测试回复",
                "secret_triggered": None,
                "rebuttal": False,
                "rebuttal_believable": False,
            }
            mock_agent.update_confession_progress.return_value = 0.02
            mock_agent.check_confession_upgrade.return_value = None
            engine.suspects[i] = mock_agent
        return engine
    except ImportError:
        return None


@pytest.fixture
def fake_llm():
    """Provide a FakeLLMClient for testing."""
    from tests.fixtures.fake_llm import FakeLLMClient

    return FakeLLMClient()


@pytest.fixture
def mock_case_with_culprit():
    """Mock case with culprit_name field for Phase 1 testing."""
    with open(FIXTURES_DIR / "mock_cases" / "simple.json", "r", encoding="utf-8") as f:
        case_data = json.load(f)
    # Ensure culprit_name exists
    if "culprit_name" not in case_data:
        case_data["culprit_name"] = "李四"
    return case_data


@pytest.fixture
def state_driven_suspect_cls():
    """Return the StateDrivenSuspect class for test use."""
    from tests.fixtures.state_driven_suspect import StateDrivenSuspect

    return StateDrivenSuspect


@pytest.fixture
def engine_with_state_driven(mock_case_simple, state_driven_suspect_cls):
    """Create an InterrogationEngine with StateDrivenSuspect instances.

    Each suspect auto-upgrades confession when thresholds are met.
    """
    from core.interrogation import InterrogationEngine

    engine = InterrogationEngine(mock_case_simple)
    engine.suspects = [state_driven_suspect_cls(s, mock_case_simple["title"]) for s in mock_case_simple["suspects"]]
    return engine
