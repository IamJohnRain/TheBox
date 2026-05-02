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
    mock.respond.return_value = {
        "reply": "我是无辜的",
        "pressure_change": 0,
        "secret_triggered": None,
    }
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
            mock_agent.respond.return_value = {
                "reply": "测试回复",
                "pressure_change": 0,
                "secret_triggered": None,
            }
            engine.suspects[i] = mock_agent
        return engine
    except ImportError:
        return None
