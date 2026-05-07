"""Dual interrogation tool."""

import logging

from core.tools import Tool, register_tool
from schemas.events import NewMessageEvent

logger = logging.getLogger("thebox")


@register_tool
class DualInterrogationTool(Tool):
    """多人对质：两名嫌疑人同时审讯，压力效果翻倍。"""

    name = "dual_interrogation"
    display_name = "多人对质"
    max_uses = 1
    unlock_level = 15
    cost_ap = 3

    def execute(self, engine, suspect, content: str):
        """两名嫌疑人同时审讯，压力效果翻倍。"""
        current_idx = engine.current_suspect_index
        other_idx = (current_idx + 1) % len(engine.suspects)
        other_suspect = engine.suspects[other_idx]

        # 当前嫌疑人压力+20
        suspect.pressure = max(0, min(100, suspect.pressure + 20))

        # 另一名嫌疑人反应（受loyalty影响）
        prompt = f"（另一名嫌疑人 {suspect.name} 被审讯员严厉质问，你在一旁听到...）"
        other_result = other_suspect.respond(prompt)

        # loyalty 检查
        loyalty_hint = ""
        if other_suspect.pressure > other_suspect.loyalty:
            loyalty_hint = f"\n注意：{other_suspect.name} 的忠诚度较低，在高压力下可能出卖同伙。"

        return [
            NewMessageEvent(
                type="new_message",
                role="system",
                content=f"【多人对质】两名嫌疑人被同时审讯。{loyalty_hint}",
                suspect_name=None,
            ),
            NewMessageEvent(
                type="new_message",
                role="player",
                content=f"[对质] 你如何看待 {suspect.name} 的供述？",
                suspect_name=None,
            ),
            NewMessageEvent(
                type="new_message",
                role="suspect",
                content=other_result["reply"],
                suspect_name=other_suspect.name,
            ),
        ]
