"""LLM-based scoring system for interrogation sessions."""

import json
import logging
from typing import Dict, Any

from core.llm_client import llm_client

logger = logging.getLogger("thebox")


# 评分维度定义
SCORING_DIMENSIONS = {
    "confession_depth": {"weight": 0.20, "desc": "供词深度"},
    "ap_efficiency": {"weight": 0.10, "desc": "行动效率"},
    "evidence_usage": {"weight": 0.10, "desc": "证据利用"},
    "pressure_accuracy": {"weight": 0.15, "desc": "施压精准度"},
    "evidence_accuracy": {"weight": 0.15, "desc": "证据精准度"},
    "mistake_penalty": {"weight": 0.10, "desc": "错误惩罚"},
    "interrogation_strategy": {"weight": 0.10, "desc": "审讯策略"},
    "reasoning_accuracy": {"weight": 0.10, "desc": "推理准确"},
}

GRADE_THRESHOLDS = [("S", 90), ("A", 75), ("B", 60), ("C", 40), ("D", 0)]
GRADE_VALUE = {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1}
GRADE_EXP_MULTIPLIER = {"S": 1.5, "A": 1.2, "B": 1.0, "C": 0.8, "D": 0.5}


def calculate_score(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """计算审讯评分。

    Args:
        session_data: 审讯会话数据，包含各维度原始值。

    Returns:
        包含 dimensions, total_score, grade, grade_value, exp_multiplier, detail 的字典。
    """
    from core.game_config import get_scoring_config

    scoring_config = get_scoring_config()
    scores: Dict[str, int] = {}

    # 行动效率
    ap_remaining = session_data.get("ap_remaining", 0)
    total_ap = session_data.get("total_ap", 1)
    scores["ap_efficiency"] = min(100, int((ap_remaining / max(total_ap, 1)) * 100))

    # 证据利用
    correct_evidence = session_data.get("correct_evidence_count", 0)
    related_count = session_data.get("related_evidence_count", 0)
    evidence_uses = session_data.get("evidence_uses", 4)
    if related_count > 0:
        max_possible = min(evidence_uses, related_count)
        scores["evidence_usage"] = min(100, int((correct_evidence / max_possible) * 100))
    else:
        scores["evidence_usage"] = 0

    # 供词深度（非线性映射）
    confession_level = session_data.get("confession_level", 0)
    confession_score_map = {0: 15, 1: 40, 2: 65, 3: 85, 4: 100}
    scores["confession_depth"] = confession_score_map.get(confession_level, 0)

    # 施压精准度
    pressure_count = session_data.get("pressure_count", 0)
    pressure_on_culprit = session_data.get("pressure_on_culprit", 0)
    if pressure_count > 0:
        scores["pressure_accuracy"] = min(100, int((pressure_on_culprit / pressure_count) * 100))
    else:
        scores["pressure_accuracy"] = 50

    # 证据精准度
    total_evidence_presented = session_data.get("total_evidence_presented", 0)
    if total_evidence_presented > 0:
        scores["evidence_accuracy"] = min(100, int((correct_evidence / total_evidence_presented) * 100))
    else:
        scores["evidence_accuracy"] = 50

    # 错误惩罚
    mistake_log = session_data.get("mistake_log", [])
    mistake_count = len(mistake_log)
    innocent_breakdown = any(m.get("type") == "innocent_breakdown" for m in mistake_log)
    penalty_weights = scoring_config.get("mistake_penalty", {}).get("weights", [15, 15, 10, 10])
    total_penalty = sum(penalty_weights[min(i, len(penalty_weights) - 1)] for i in range(mistake_count))
    mistake_score = max(scoring_config.get("mistake_penalty", {}).get("score_floor", 20), 100 - total_penalty)
    if innocent_breakdown:
        mistake_score = max(20, mistake_score - 30)
    scores["mistake_penalty"] = mistake_score

    # LLM 评分
    llm_scores = _llm_score(session_data)
    scores["interrogation_strategy"] = llm_scores.get("interrogation_strategy", 50)
    scores["reasoning_accuracy"] = llm_scores.get("reasoning_accuracy", 50)

    # 加权总分
    total = 0
    for dim, config in SCORING_DIMENSIONS.items():
        total += scores.get(dim, 0) * config["weight"]
    total = int(total)

    # 结果封顶
    outcome = session_data.get("outcome", "win" if confession_level >= 4 else "fail")
    outcome_caps = scoring_config.get("outcome_caps", {"partial": 74, "fail": 59, "innocent_breakdown": 49})
    if outcome == "partial":
        total = min(total, outcome_caps["partial"])
    elif outcome == "fail":
        total = min(total, outcome_caps["fail"])
    if innocent_breakdown:
        total = min(total, outcome_caps["innocent_breakdown"])

    # 评级
    grade = "D"
    for g, threshold in GRADE_THRESHOLDS:
        if total >= threshold:
            grade = g
            break

    return {
        "dimensions": scores,
        "total_score": total,
        "grade": grade,
        "grade_value": GRADE_VALUE[grade],
        "exp_multiplier": GRADE_EXP_MULTIPLIER.get(grade, 1.0),
        "detail": llm_scores.get("detail", ""),
    }


def _llm_score(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """调用 LLM 进行评分。

    Args:
        session_data: 审讯会话数据。

    Returns:
        包含 interrogation_strategy, reasoning_accuracy, detail 的字典。
    """
    if not llm_client.is_initialized:
        return {"interrogation_strategy": 50, "reasoning_accuracy": 50, "detail": "LLM 未初始化"}

    truth = session_data.get("truth", "")
    memory = session_data.get("memory_summary", "")[:2000]  # 截断
    tools = session_data.get("used_tools", [])

    prompt = f"""你是一个游戏评分专家。请对以下审讯表现进行评分。

案件真相: {truth}

审讯对话摘要:
{memory}

使用过的工具: {', '.join(tools) if tools else '无'}

请从以下两个维度评分（0-100分）：
1. 审讯策略（interrogation_strategy）：施压/共情交替、工具使用时机
2. 推理准确（reasoning_accuracy）：提问和推理是否接近真相

请以 JSON 格式输出：
{{
    "interrogation_strategy": 分数,
    "reasoning_accuracy": 分数,
    "detail": "简短评语（50字以内）"
}}"""

    try:
        raw = llm_client.chat_completion(
            messages=[{"role": "system", "content": prompt}],
            response_format={"type": "json_object"},
        )
        return json.loads(raw)
    except Exception as exc:
        logger.warning(f"LLM 评分失败: {exc}")
        return {"interrogation_strategy": 50, "reasoning_accuracy": 50, "detail": "评分失败"}


def calculate_experience(score_result: Dict[str, Any], session_data: Dict[str, Any]) -> int:
    """计算经验结算。

    Args:
        score_result: calculate_score 的返回值。
        session_data: 审讯会话数据。

    Returns:
        获得的经验值。
    """
    from core.game_config import get_experience_config

    exp_config = get_experience_config()

    base_exp = 0

    # 供词等级经验
    confession_level = session_data.get("confession_level", 0)
    per_confession = exp_config.get("per_confession_level", 10)
    base_exp += confession_level * per_confession

    # 出示证据经验
    evidence_presented = session_data.get("total_evidence_presented", 0)
    per_evidence = exp_config.get("per_presented_evidence", 5)
    base_exp += evidence_presented * per_evidence

    # 完成奖励
    completion = exp_config.get("completion", 20)
    base_exp += completion

    # 评级乘数
    multiplier = score_result.get("exp_multiplier", 1.0)
    total_exp = int(base_exp * multiplier)

    return total_exp


def get_difficulty_preset(difficulty: str) -> Dict[str, Any]:
    """获取指定难度的预设配置。

    Args:
        difficulty: 难度名称 (easy/normal/hard/nightmare)。

    Returns:
        难度预设配置字典。

    Raises:
        ValueError: 如果难度名称无效。
    """
    from core.game_config import get_difficulty_config

    difficulty_config = get_difficulty_config()
    presets = difficulty_config.get("presets", {})
    if difficulty not in presets:
        raise ValueError(f"无效难度: {difficulty}，可选: {list(presets.keys())}")
    return presets[difficulty]


def get_available_difficulties(player_level: int) -> list:
    """根据玩家等级获取可用的难度列表。

    Args:
        player_level: 玩家当前等级。

    Returns:
        可用难度名称列表。
    """
    from core.game_config import get_difficulty_config

    difficulty_config = get_difficulty_config()
    presets = difficulty_config.get("presets", {})
    available = []
    for name, preset in presets.items():
        unlock_level = preset.get("unlock_level", 1)
        if player_level >= unlock_level:
            available.append(name)
    return available
