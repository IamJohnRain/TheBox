"""Gameplay configuration loader.

All tunable values come from config/gameplay_balance.json.
Business logic should import accessors from this module instead of hardcoding numbers.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("thebox")

# Default config path
_CONFIG_DIR = Path(__file__).parent.parent / "config"
_DEFAULT_CONFIG_PATH = _CONFIG_DIR / "gameplay_balance.json"

# Global config cache
_GAMEPLAY_CONFIG: Optional[Dict[str, Any]] = None


def load_gameplay_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load gameplay configuration from JSON file.

    Priority:
    1. THEBOX_GAMEPLAY_CONFIG env var
    2. config_path parameter
    3. Default config/gameplay_balance.json
    """
    global _GAMEPLAY_CONFIG

    # Determine config path
    env_path = os.environ.get("THEBOX_GAMEPLAY_CONFIG")
    if env_path:
        path = Path(env_path)
    elif config_path:
        path = Path(config_path)
    else:
        path = _DEFAULT_CONFIG_PATH

    if not path.exists():
        logger.warning(f"Config file not found: {path}, using defaults")
        _GAMEPLAY_CONFIG = _get_default_config()
        return _GAMEPLAY_CONFIG

    try:
        with open(path, "r", encoding="utf-8") as f:
            _GAMEPLAY_CONFIG = json.load(f)
        logger.info(f"Loaded gameplay config from {path}")
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to load config: {e}, using defaults")
        _GAMEPLAY_CONFIG = _get_default_config()

    return _GAMEPLAY_CONFIG


def get_gameplay_config() -> Dict[str, Any]:
    """Get the current gameplay config, loading if necessary."""
    if _GAMEPLAY_CONFIG is None:
        load_gameplay_config()
    return _GAMEPLAY_CONFIG


def _get_default_config() -> Dict[str, Any]:
    """Return hardcoded default config as fallback."""
    return {
        "config_version": 1,
        "confession": {
            "levels": {
                "0": {"name": "否认", "desc": "完全否认一切"},
                "1": {"name": "动摇", "desc": "情绪波动，出现紧张、回避"},
                "2": {"name": "部分承认", "desc": "承认部分事实，但隐瞒关键"},
                "3": {"name": "关键突破", "desc": "透露动机/手段/时机之一"},
                "4": {"name": "完全崩溃", "desc": "完整供述真相"},
            },
            "thresholds": {
                "0": {"pressure": 40, "min_turns": 3, "requires_evidence": False},
                "1": {"pressure": 55, "min_turns": 5, "requires_evidence": True},
                "2": {"pressure": 70, "min_turns": 7, "requires_evidence": True},
                "3": {"pressure": 85, "min_turns": 10, "requires_evidence": True},
            },
            "pressure_window": 5,
            "progress_rate": {"low": 0.02, "medium": 0.05, "high": 0.10, "panic": 0.15},
        },
        "pressure": {
            "initial": 20,
            "segments": {"low": [0, 30], "medium": [30, 60], "high": [60, 80], "panic": [80, 100]},
            "soft_factor": {"min": 0.3, "max": 1.5},
            "per_turn": {
                "decay_zone": [0, 30],
                "decay_rate": -1,
                "stable_zone": [30, 70],
                "stable_rate": 0,
                "growth_zone": [70, 100],
                "growth_rate": 1,
                "floor": 15,
            },
        },
        "evidence": {
            "default_uses": 4,
            "pressure_base": {"physical": 18, "document": 12, "testimony": 9},
            "strength_multiplier": 0.1,
            "fear_delta": {"correct": 8, "wrong": -10},
            "chain_bonus": 10,
        },
        "fear": {
            "default": 50,
            "neutral": 50,
            "per_turn_decay": -1,
            "provocation_threshold": 15,
        },
        "dimensions": {
            "bounds": {
                "fear": {"min": 0, "max": 100},
                "defiance": {"min": 5, "max": 100},
                "empathy_susceptibility": {"min": 0, "max": 95},
                "deception_skill": {"min": 5, "max": 100},
                "loyalty": {"min": 0, "max": 100},
                "credibility": {"min": 0, "max": 100},
            },
            "personality_weights": {"primary": 0.7, "secondary": 0.3},
            "personality_dimensions": {
                "胆小": {"fear": 80, "defiance": 20, "empathy_susceptibility": 70, "deception_skill": 15, "loyalty": 40},
                "冷静": {"fear": 30, "defiance": 40, "empathy_susceptibility": 40, "deception_skill": 70, "loyalty": 50},
                "暴躁": {"fear": 40, "defiance": 80, "empathy_susceptibility": 20, "deception_skill": 25, "loyalty": 30},
                "孤僻": {"fear": 50, "defiance": 60, "empathy_susceptibility": 30, "deception_skill": 55, "loyalty": 70},
                "狡猾": {"fear": 25, "defiance": 50, "empathy_susceptibility": 20, "deception_skill": 85, "loyalty": 20},
                "忠诚": {"fear": 45, "defiance": 30, "empathy_susceptibility": 60, "deception_skill": 30, "loyalty": 90},
                "脆弱": {"fear": 75, "defiance": 15, "empathy_susceptibility": 80, "deception_skill": 10, "loyalty": 35},
                "固执": {"fear": 35, "defiance": 85, "empathy_susceptibility": 25, "deception_skill": 40, "loyalty": 60},
            },
        },
        "interaction_limits": {
            "chat_turns_per_suspect": 12,
            "pressure_uses_per_suspect": 2,
            "empathy_uses_per_suspect": 2,
            "second_use_multiplier": 0.5,
        },
        "scoring": {
            "outcome_caps": {"partial": 74, "fail": 59, "innocent_breakdown": 49},
            "mistake_penalty": {"weights": [15, 15, 10, 10], "score_floor": 20},
        },
        "difficulty": {
            "presets": {
                "easy": {"suspects": 2, "total_ap": 26, "evidence_uses": 4, "keywords": 3, "unlock_level": 1},
                "normal": {"suspects": "2-3", "total_ap": 22, "evidence_uses": 4, "keywords": 2, "unlock_level": 5},
                "hard": {"suspects": "3-4", "total_ap": 19, "evidence_uses": 4, "keywords": 2, "unlock_level": 10},
                "nightmare": {"suspects": "4+", "total_ap": 16, "evidence_uses": 3, "keywords": 1, "unlock_level": 15},
            },
        },
        "experience": {
            "per_confession_level": 10,
            "per_presented_evidence": 5,
            "completion": 20,
        },
        "action_points": {
            "default_total": 22,
            "costs": {"chat": 1, "pressure": 2, "empathy": 2, "present_evidence": 2},
            "penalties": {"wrong_evidence": 2, "wrong_pressure": 1, "wrong_empathy": 1, "innocent_breakdown": 3},
        },
        "rebuttal": {
            "pressure_threshold_hard": 80,
            "pressure_threshold_soft": 60,
            "credibility_bonus_success": 10,
            "credibility_penalty_fail": 5,
            "deception_threshold_base": 80,
            "deception_threshold_scale": 0.2,
        },
        "proactive_speech": {
            "pressure_threshold": 70,
            "turn_interval": 5,
            "probability_divisor": 300,
        },
        "progression": {
            "experience_curve": [
                0, 50, 110, 180, 260, 350, 460, 580, 720, 880,
                1060, 1260, 1480, 1720, 1980, 2260, 2560, 2880, 3220, 3580,
            ],
            "level_unlocks": {
                "1": {"tools": [], "evidence_uses": 4, "desc": "基础审讯"},
                "2": {"tools": ["psych_profile_basic"], "evidence_uses": 4, "desc": "初级心理侧写"},
                "5": {"tools": [], "evidence_uses": 5, "desc": "证据次数+1"},
                "10": {"tools": ["psych_profile_advanced", "silent_pressure"], "evidence_uses": 6, "desc": "高级侧写"},
                "11": {"tools": [], "evidence_uses": 6, "ap_bonus": 2, "desc": "AP+2"},
                "15": {"tools": ["psych_profile_master"], "evidence_uses": 7, "desc": "大师侧写"},
                "16": {"tools": [], "evidence_uses": 7, "ap_bonus": 2, "desc": "AP+2"},
                "18": {"tools": [], "evidence_uses": 8, "desc": "证据次数+1"},
                "20": {"tools": [], "evidence_uses": 8, "desc": "审讯大师"},
            },
        },
    }


# ──────────────────────────────────────────────
# Accessor functions - business logic should use these
# ──────────────────────────────────────────────


def get_action_cost(action_type: str) -> int:
    """Get AP cost for an action type."""
    config = get_gameplay_config()
    return config["action_points"]["costs"].get(action_type, 1)


def get_ap_penalty(penalty_type: str) -> int:
    """Get AP penalty for a mistake type."""
    config = get_gameplay_config()
    return config["action_points"]["penalties"].get(penalty_type, 0)


def get_evidence_pressure_base(evidence_type: str) -> int:
    """Get base pressure increment for evidence type."""
    config = get_gameplay_config()
    return config["evidence"]["pressure_base"].get(evidence_type, 10)


def get_confession_threshold(level: int) -> Dict[str, Any]:
    """Get confession upgrade threshold for a level."""
    config = get_gameplay_config()
    return config["confession"]["thresholds"].get(str(level), {})


def get_confession_levels() -> Dict[str, Dict[str, str]]:
    """Get all confession level definitions."""
    config = get_gameplay_config()
    return config["confession"]["levels"]


def get_dimension_bounds(name: str) -> Dict[str, int]:
    """Get min/max bounds for a dimension."""
    config = get_gameplay_config()
    return config["dimensions"]["bounds"].get(name, {"min": 0, "max": 100})


def get_pressure_segments() -> Dict[str, List[int]]:
    """Get pressure segment definitions."""
    config = get_gameplay_config()
    return config["pressure"]["segments"]


def get_interaction_limits() -> Dict[str, int]:
    """Get interaction limit values."""
    config = get_gameplay_config()
    return config["interaction_limits"]


def get_evidence_chain_bonus() -> int:
    """Get evidence chain bonus pressure."""
    config = get_gameplay_config()
    return config.get("evidence", {}).get("chain_bonus", 10)


def get_rebuttal_config() -> Dict[str, Any]:
    """Get rebuttal mechanism configuration."""
    config = get_gameplay_config()
    return config.get("rebuttal", {
        "pressure_threshold_hard": 80,
        "pressure_threshold_soft": 60,
        "credibility_bonus_success": 10,
        "credibility_penalty_fail": 5,
        "deception_threshold_base": 80,
        "deception_threshold_scale": 0.2,
    })


def get_proactive_speech_config() -> Dict[str, Any]:
    """Get proactive speech (反扑) configuration."""
    config = get_gameplay_config()
    return config.get("proactive_speech", {
        "pressure_threshold": 70,
        "turn_interval": 5,
        "probability_divisor": 300,
    })


def get_scoring_config() -> Dict[str, Any]:
    """Get scoring system configuration (outcome caps, mistake penalty)."""
    config = get_gameplay_config()
    return config.get("scoring", {
        "outcome_caps": {"partial": 74, "fail": 59, "innocent_breakdown": 49},
        "mistake_penalty": {"weights": [15, 15, 10, 10], "score_floor": 20},
    })


def get_difficulty_config() -> Dict[str, Any]:
    """Get difficulty presets configuration."""
    config = get_gameplay_config()
    return config.get("difficulty", {
        "presets": {
            "easy": {"suspects": 2, "total_ap": 26, "evidence_uses": 4, "keywords": 3, "unlock_level": 1},
            "normal": {"suspects": "2-3", "total_ap": 22, "evidence_uses": 4, "keywords": 2, "unlock_level": 5},
            "hard": {"suspects": "3-4", "total_ap": 19, "evidence_uses": 4, "keywords": 2, "unlock_level": 10},
            "nightmare": {"suspects": "4+", "total_ap": 16, "evidence_uses": 3, "keywords": 1, "unlock_level": 15},
        },
    })


def get_experience_config() -> Dict[str, Any]:
    """Get experience calculation configuration."""
    config = get_gameplay_config()
    return config.get("experience", {
        "per_confession_level": 10,
        "per_presented_evidence": 5,
        "completion": 20,
    })


def get_experience_curve() -> List[int]:
    """Get the experience curve thresholds for leveling up.

    Returns a list where index = level and value = XP threshold to reach that level.
    e.g. [0, 50, 110, ...] means level 1 starts at 0 XP, level 2 at 50 XP, level 3 at 110 XP.
    """
    config = get_gameplay_config()
    return config.get("progression", {}).get("experience_curve", [0, 50, 110, 180, 260])


def get_level_unlocks() -> Dict[int, Dict[str, Any]]:
    """Get level unlock definitions.

    Returns a dict keyed by level number with tools, evidence_uses, ap_bonus, etc.
    """
    config = get_gameplay_config()
    raw = config.get("progression", {}).get("level_unlocks", {})
    return {int(k): v for k, v in raw.items()}


# ──────────────────────────────────────────────
# Compatibility exports - derived from config at import time
# ──────────────────────────────────────────────

# These will be populated by _init_compatibility_exports()
DEFAULT_TOTAL_ACTION_POINTS: int = 0
DEFAULT_INITIAL_PRESSURE: int = 0
DEFAULT_EVIDENCE_USES: int = 0
EVIDENCE_PRESSURE_BASE: Dict[str, int] = {}
EVIDENCE_STRENGTH_MULTIPLIER: float = 0.0
AP_PENALTY: Dict[str, int] = {}
ACTION_AP_COST: Dict[str, int] = {}

CONFESSION_LEVELS: Dict[int, Dict[str, str]] = {}
CONFESSION_THRESHOLDS: Dict[int, Dict[str, Any]] = {}
CONFESSION_PROGRESS_RATE: Dict[str, float] = {}

PRESSURE_SEGMENTS: Dict[str, tuple] = {}
PRESSURE_SOFT_FACTOR_MIN: float = 0.0
PRESSURE_SOFT_FACTOR_MAX: float = 0.0
PRESSURE_PER_TURN_DYNAMICS: Dict[str, Any] = {}

DEFAULT_FEAR: int = 0
FEAR_NEUTRAL: int = 0
FEAR_PER_TURN_DECAY: int = 0
FEAR_PROVOCATION_THRESHOLD: int = 0
FEAR_PENALTY_WRONG_EVIDENCE: int = 0

DIMENSION_BOUNDS: Dict[str, Dict[str, int]] = {}
PERSONALITY_DIMENSIONS: Dict[str, Dict[str, int]] = {}
PERSONALITY_PRIMARY_WEIGHT: float = 0.0
PERSONALITY_SECONDARY_WEIGHT: float = 0.0

CHAT_TURNS_PER_SUSPECT: int = 0
PRESSURE_USES_PER_SUSPECT: int = 0
EMPATHY_USES_PER_SUSPECT: int = 0

# Phase 2 config exports
EVIDENCE_CHAIN_BONUS: int = 0
REBUTTAL_DECAY_CONFIG: Dict[str, Any] = {}
PROACTIVE_SPEECH_CONFIG: Dict[str, Any] = {}

# Phase 3b config exports
EXPERIENCE_CURVE: List[int] = []
LEVEL_UNLOCKS: Dict[int, Dict[str, Any]] = {}

# Phase 4 config exports
SCORING_CONFIG: Dict[str, Any] = {}
DIFFICULTY_CONFIG: Dict[str, Any] = {}
EXPERIENCE_CONFIG: Dict[str, Any] = {}


def _init_compatibility_exports():
    """Initialize compatibility aliases from config."""
    global DEFAULT_TOTAL_ACTION_POINTS, DEFAULT_INITIAL_PRESSURE, DEFAULT_EVIDENCE_USES
    global EVIDENCE_PRESSURE_BASE, EVIDENCE_STRENGTH_MULTIPLIER, AP_PENALTY
    global CONFESSION_LEVELS, CONFESSION_THRESHOLDS, PRESSURE_SEGMENTS
    global CONFESSION_PROGRESS_RATE, DEFAULT_FEAR, FEAR_NEUTRAL
    global PRESSURE_SOFT_FACTOR_MIN, PRESSURE_SOFT_FACTOR_MAX
    global FEAR_PER_TURN_DECAY, FEAR_PROVOCATION_THRESHOLD, FEAR_PENALTY_WRONG_EVIDENCE
    global DIMENSION_BOUNDS, PERSONALITY_DIMENSIONS, PERSONALITY_PRIMARY_WEIGHT, PERSONALITY_SECONDARY_WEIGHT
    global CHAT_TURNS_PER_SUSPECT, PRESSURE_USES_PER_SUSPECT, EMPATHY_USES_PER_SUSPECT
    global ACTION_AP_COST, PRESSURE_PER_TURN_DYNAMICS
    global EVIDENCE_CHAIN_BONUS, REBUTTAL_DECAY_CONFIG, PROACTIVE_SPEECH_CONFIG
    global EXPERIENCE_CURVE, LEVEL_UNLOCKS
    global SCORING_CONFIG, DIFFICULTY_CONFIG, EXPERIENCE_CONFIG

    config = get_gameplay_config()

    DEFAULT_TOTAL_ACTION_POINTS = config["action_points"]["default_total"]
    DEFAULT_INITIAL_PRESSURE = config["pressure"]["initial"]
    DEFAULT_EVIDENCE_USES = config["evidence"]["default_uses"]
    EVIDENCE_PRESSURE_BASE = config["evidence"]["pressure_base"]
    EVIDENCE_STRENGTH_MULTIPLIER = config["evidence"]["strength_multiplier"]
    AP_PENALTY = config["action_points"]["penalties"]
    ACTION_AP_COST = config["action_points"]["costs"]

    CONFESSION_LEVELS = {int(k): v for k, v in config["confession"]["levels"].items()}
    CONFESSION_THRESHOLDS = {int(k): v for k, v in config["confession"]["thresholds"].items()}
    CONFESSION_PROGRESS_RATE = config["confession"]["progress_rate"]

    PRESSURE_SEGMENTS = {k: tuple(v) for k, v in config["pressure"]["segments"].items()}
    PRESSURE_SOFT_FACTOR_MIN = config["pressure"]["soft_factor"]["min"]
    PRESSURE_SOFT_FACTOR_MAX = config["pressure"]["soft_factor"]["max"]
    PRESSURE_PER_TURN_DYNAMICS = {
        "decay_zone": tuple(config["pressure"]["per_turn"]["decay_zone"]),
        "decay_rate": config["pressure"]["per_turn"]["decay_rate"],
        "stable_zone": tuple(config["pressure"]["per_turn"]["stable_zone"]),
        "stable_rate": config["pressure"]["per_turn"]["stable_rate"],
        "growth_zone": tuple(config["pressure"]["per_turn"]["growth_zone"]),
        "growth_rate": config["pressure"]["per_turn"]["growth_rate"],
        "pressure_floor": config["pressure"]["per_turn"]["floor"],
    }

    DEFAULT_FEAR = config["fear"]["default"]
    FEAR_NEUTRAL = config["fear"]["neutral"]
    FEAR_PER_TURN_DECAY = config["fear"]["per_turn_decay"]
    FEAR_PROVOCATION_THRESHOLD = config["fear"]["provocation_threshold"]
    FEAR_PENALTY_WRONG_EVIDENCE = config["evidence"]["fear_delta"]["wrong"]

    DIMENSION_BOUNDS = config["dimensions"]["bounds"]
    PERSONALITY_DIMENSIONS = config["dimensions"].get("personality_dimensions", {})
    PERSONALITY_PRIMARY_WEIGHT = config["dimensions"]["personality_weights"]["primary"]
    PERSONALITY_SECONDARY_WEIGHT = config["dimensions"]["personality_weights"]["secondary"]

    CHAT_TURNS_PER_SUSPECT = config["interaction_limits"]["chat_turns_per_suspect"]
    PRESSURE_USES_PER_SUSPECT = config["interaction_limits"]["pressure_uses_per_suspect"]
    EMPATHY_USES_PER_SUSPECT = config["interaction_limits"]["empathy_uses_per_suspect"]

    # Phase 2 config exports
    EVIDENCE_CHAIN_BONUS = config.get("evidence", {}).get("chain_bonus", 10)
    REBUTTAL_DECAY_CONFIG = config.get("rebuttal", {
        "pressure_threshold_hard": 80,
        "pressure_threshold_soft": 60,
        "credibility_bonus_success": 10,
        "credibility_penalty_fail": 5,
        "deception_threshold_base": 80,
        "deception_threshold_scale": 0.2,
    })
    PROACTIVE_SPEECH_CONFIG = config.get("proactive_speech", {
        "pressure_threshold": 70,
        "turn_interval": 5,
        "probability_divisor": 300,
    })

    # Phase 3b config exports
    EXPERIENCE_CURVE = config.get("progression", {}).get("experience_curve", [0, 50, 110, 180, 260])
    LEVEL_UNLOCKS = {int(k): v for k, v in config.get("progression", {}).get("level_unlocks", {}).items()}

    # Phase 4 config exports
    SCORING_CONFIG = config.get("scoring", {
        "outcome_caps": {"partial": 74, "fail": 59, "innocent_breakdown": 49},
        "mistake_penalty": {"weights": [15, 15, 10, 10], "score_floor": 20},
    })
    DIFFICULTY_CONFIG = config.get("difficulty", {
        "presets": {
            "easy": {"suspects": 2, "total_ap": 26, "evidence_uses": 4, "keywords": 3, "unlock_level": 1},
            "normal": {"suspects": "2-3", "total_ap": 22, "evidence_uses": 4, "keywords": 2, "unlock_level": 5},
            "hard": {"suspects": "3-4", "total_ap": 19, "evidence_uses": 4, "keywords": 2, "unlock_level": 10},
            "nightmare": {"suspects": "4+", "total_ap": 16, "evidence_uses": 3, "keywords": 1, "unlock_level": 15},
        },
    })
    EXPERIENCE_CONFIG = config.get("experience", {
        "per_confession_level": 10,
        "per_presented_evidence": 5,
        "completion": 20,
    })


# Initialize on module load
_init_compatibility_exports()
