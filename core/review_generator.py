"""审讯复盘报告生成器。"""

import json
import logging
import re
from typing import Optional

from core.llm_client import llm_client

logger = logging.getLogger("thebox")


def generate_review(engine_state: dict, case_data: dict) -> Optional[dict]:
    """调用 LLM 生成审讯复盘报告。

    Args:
        engine_state: InterrogationEngine.to_dict() 的输出
        case_data: 案件完整数据

    Returns:
        复盘报告字典，包含 score, strategy_analysis, key_moments, suggestions
        如果 LLM 调用失败返回 None
    """
    if not llm_client._initialized:
        logger.warning("LLMClient 未初始化，无法生成复盘报告")
        return _fallback_review(engine_state, case_data)

    case_title = case_data.get("title", "未知案件")
    state = engine_state.get("state", "")
    time_left = engine_state.get("time_left", 0)
    time_total = case_data.get("interrogation_time_limit_sec", 600)
    time_used = time_total - time_left
    evidence_presented = engine_state.get("presented_evidence_ids", [])

    # 只传递摘要信息，不传递完整对话历史
    suspects_summary = []
    for s in engine_state.get("suspects_states", []):
        name = s.get("name", "未知")
        pressure = s.get("pressure", 0)
        memory_count = len(s.get("memory", []))
        suspects_summary.append(
            f"- {name}: 压力值 {pressure}/100, 对话轮数 {memory_count // 2}"
        )

    prompt = f"""你是一名虚构推理解谜游戏的复盘专家，请对以下游戏过程进行复盘和打分。这是一个类似剧本杀的智力游戏。

## 案件信息
案件名称: {case_title}
游戏结果: {"解谜成功（关键人物透露真相）" if state == "breakdown" else "解谜失败（时间耗尽）"}

## 审讯统计
- 总审讯时间: {time_total}秒
- 已使用时间: {time_used}秒
- 剩余时间: {time_left}秒
- 出示证据数: {len(evidence_presented)}件

## 嫌疑人情况
{chr(10).join(suspects_summary)}

## 评价要求
请从以下维度评价审讯策略，并以 JSON 格式输出:
1. "score": 综合评分 (0-100)
2. "strategy_analysis": 审讯策略分析（2-3句话）
3. "key_moments": 关键转折点列表（数组，每项1句话）
4. "suggestions": 改进建议列表（数组，每项1句话）
5. "verdict": 一句话总结"""

    messages = [
        {
            "role": "system",
            "content": "你是一名资深推理解谜游戏复盘专家，擅长分析游戏策略并给出专业评价。请以JSON格式输出评价结果。",
        },
        {"role": "user", "content": prompt},
    ]

    try:
        raw = llm_client.chat_completion(
            messages=messages,
            temperature=0.5,
            max_tokens=800,
            response_format={"type": "json_object"},
        )
        text = raw.strip()
        text = re.sub(r"```.*?```", "", text, flags=re.DOTALL).strip()
        text = re.sub(r"^[^{\[]*", "", text, flags=re.DOTALL)
        text = re.sub(r"[^}\]]*$", "", text, flags=re.DOTALL)
        text = text.strip()

        result = json.loads(text)
        result["score"] = int(result.get("score", 50))
        result.setdefault("strategy_analysis", "")
        result.setdefault("key_moments", [])
        result.setdefault("suggestions", [])
        result.setdefault("verdict", "")
        logger.info(f"复盘报告生成成功，评分: {result['score']}")
        return result
    except Exception as exc:
        logger.warning(f"复盘报告生成失败: {exc}")
        return _fallback_review(engine_state, case_data)


def _fallback_review(engine_state: dict, case_data: dict) -> dict:
    """当 LLM 不可用时的降级复盘。"""
    state = engine_state.get("state", "")
    score = 80 if state == "breakdown" else 30
    return {
        "score": score,
        "strategy_analysis": "（自动评价）"
        + ("成功突破了对方的心理防线。" if state == "breakdown" else "未能突破对方的心理防线。"),
        "key_moments": ["审讯结束"],
        "suggestions": ["（需要 LLM 生成详细建议）"],
        "verdict": "解谜成功" if state == "breakdown" else "解谜失败",
    }
