"""Lie detector tool."""

import json
import logging

from core.llm_client import llm_client
from core.tools import Tool, register_tool
from schemas.events import NewMessageEvent

logger = logging.getLogger("thebox")


@register_tool
class LieDetectorTool(Tool):
    """测谎仪：让 LLM 判断嫌疑人上一句话的真假。

    注意：不传入嫌疑人 knowledge，只传入性格和对话上下文，
    避免泄露游戏关键信息。
    """

    name = "lie_detector"
    display_name = "测谎仪"
    max_uses = 2
    unlock_level = 4
    cost_ap = 0

    def execute(self, engine, suspect, content: str):
        """让 LLM 判断嫌疑人上一句话的真假。

        注意：不传入嫌疑人 knowledge，只传入性格和对话上下文。
        """
        # 获取嫌疑人最后一条回复
        last_reply = ""
        for msg in reversed(suspect.memory):
            if msg["role"] == "assistant":
                last_reply = msg["content"]
                break

        if not last_reply:
            return [NewMessageEvent(type="new_message", role="system", content="没有可分析的回复", suspect_name=None)]

        # 仅传入性格特征，不传入 knowledge
        personality = suspect._suspect_data.get("personality", "未知")

        judge_prompt = (
            f"你是一个测谎专家。请分析以下嫌疑人回复是否可能是谎言。\n\n"
            f"嫌疑人的性格: {personality}\n"
            f"嫌疑人的回复: \"{last_reply}\"\n\n"
            "请以 JSON 格式输出：\n"
            '- "result": "truthful"/"deceptive"/"uncertain"\n'
            '- "confidence": 0-100 的置信度\n'
            '- "reason": 简短的判断理由'
        )

        try:
            raw = llm_client.chat_completion(
                messages=[{"role": "system", "content": judge_prompt}],
                response_format={"type": "json_object"},
            )
            parsed = json.loads(raw)
            result_map = {"truthful": "疑似真实", "deceptive": "疑似虚假", "uncertain": "无法判断"}
            display = result_map.get(parsed.get("result", "uncertain"), "无法判断")
            reason = parsed.get("reason", "")
            msg = f"【测谎仪】{display}（置信度: {parsed.get('confidence', 50)}%）\n理由: {reason}"
        except Exception:
            logger.warning("测谎仪 LLM 调用或解析失败")
            msg = "【测谎仪】分析失败，无法得出结论"

        return [NewMessageEvent(type="new_message", role="system", content=msg, suspect_name=None)]
