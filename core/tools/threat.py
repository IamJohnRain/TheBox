"""Threat tool."""

import logging

from core.tools import Tool, register_tool
from schemas.events import NewMessageEvent

logger = logging.getLogger("thebox")


@register_tool
class ThreatTool(Tool):
    """威胁：对嫌疑人施加高压，压力+20。高压时嫌疑人沉默。"""

    name = "threat"
    display_name = "威胁"
    max_uses = 1
    unlock_level = 14
    cost_ap = 0

    def execute(self, engine, suspect, content: str):
        """威胁，压力+20。高压时嫌疑人沉默。"""
        suspect.pressure = max(0, min(100, suspect.pressure + 20))

        # 压力驱动：pressure>70 时大概率沉默
        if suspect.pressure > 70:
            reply = "（嫌疑人沉默不语，拒绝回答）"
        else:
            result = suspect.respond(f"审讯员威胁道: {content}")
            reply = result["reply"]

        return [
            NewMessageEvent(type="new_message", role="player", content=f"[威胁] {content}", suspect_name=None),
            NewMessageEvent(type="new_message", role="suspect", content=reply, suspect_name=suspect.name),
        ]
