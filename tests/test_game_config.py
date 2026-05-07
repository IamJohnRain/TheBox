"""Tests for gameplay configuration loader."""

import json


def test_default_config_loads():
    """Test that default config loads successfully."""
    from core.game_config import get_gameplay_config, DEFAULT_TOTAL_ACTION_POINTS

    config = get_gameplay_config()
    assert config is not None
    assert "action_points" in config
    assert DEFAULT_TOTAL_ACTION_POINTS == 22


def test_action_cost_accessor():
    """Test action cost accessor returns correct values."""
    from core.game_config import get_action_cost

    assert get_action_cost("chat") == 1
    assert get_action_cost("pressure") == 2
    assert get_action_cost("present_evidence") == 2
    assert get_action_cost("unknown") == 1  # default


def test_confession_threshold_accessor():
    """Test confession threshold accessor."""
    from core.game_config import get_confession_threshold

    threshold_0 = get_confession_threshold(0)
    assert threshold_0["pressure"] == 40
    assert threshold_0["min_turns"] == 3
    assert threshold_0["requires_evidence"] is False


def test_evidence_pressure_base():
    """Test evidence pressure base values."""
    from core.game_config import get_evidence_pressure_base, EVIDENCE_PRESSURE_BASE

    assert EVIDENCE_PRESSURE_BASE["physical"] == 18
    assert EVIDENCE_PRESSURE_BASE["document"] == 12
    assert EVIDENCE_PRESSURE_BASE["testimony"] == 9
    assert get_evidence_pressure_base("physical") == 18


def test_dimension_bounds():
    """Test dimension bounds accessor."""
    from core.game_config import get_dimension_bounds, DIMENSION_BOUNDS

    fear_bounds = get_dimension_bounds("fear")
    assert fear_bounds["min"] == 0
    assert fear_bounds["max"] == 100

    defiance_bounds = DIMENSION_BOUNDS["defiance"]
    assert defiance_bounds["min"] == 5  # defiance never goes to 0


def test_custom_config_override(tmp_path):
    """Test loading config from custom path via env var."""
    import os
    from core.game_config import load_gameplay_config, get_action_cost

    # Create custom config
    custom_config = {
        "config_version": 1,
        "action_points": {
            "default_total": 30,
            "costs": {"chat": 2, "pressure": 3, "empathy": 3, "present_evidence": 4},
            "penalties": {"wrong_evidence": 3, "wrong_pressure": 2, "wrong_empathy": 2, "innocent_breakdown": 5},
        },
    }

    config_file = tmp_path / "custom_config.json"
    config_file.write_text(json.dumps(custom_config))

    # Set env var and reload
    old_env = os.environ.get("THEBOX_GAMEPLAY_CONFIG")
    try:
        os.environ["THEBOX_GAMEPLAY_CONFIG"] = str(config_file)
        load_gameplay_config()

        assert get_action_cost("chat") == 2
        assert get_action_cost("pressure") == 3
    finally:
        if old_env:
            os.environ["THEBOX_GAMEPLAY_CONFIG"] = old_env
        elif "THEBOX_GAMEPLAY_CONFIG" in os.environ:
            del os.environ["THEBOX_GAMEPLAY_CONFIG"]
        # Reload default config
        load_gameplay_config()


def test_pressure_segments():
    """Test pressure segment definitions."""
    from core.game_config import PRESSURE_SEGMENTS

    assert PRESSURE_SEGMENTS["low"] == (0, 30)
    assert PRESSURE_SEGMENTS["medium"] == (30, 60)
    assert PRESSURE_SEGMENTS["high"] == (60, 80)
    assert PRESSURE_SEGMENTS["panic"] == (80, 100)
