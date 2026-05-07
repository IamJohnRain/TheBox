"""Psychological collapse tool."""

import logging

from core.game_config import CONFESSION_LEVELS
from core.tools import Tool, register_tool
from schemas.events import ConfessionUpdateEvent, NewMessageEvent

logger = logging.getLogger("thebox")


@register_tool
class PsychCollapseTool(Tool):
    """心理崩溃：供词直接+1级，但消耗5AP。"""

    name = "psych_collapse"
    display_name = "心理崩溃"
    max_uses = 1
    unlock_level = 18
    cost_ap = 5

    def execute(self, engine, suspect, content: str):
        """供词直接+1级，但消耗5AP。"""
        old_level = suspect.confession_level

        # 模拟高压条件，强制满足升级所需的压力值
        suspect.pressure = 100

        # 计算 has_evidence
        has_evidence = any(
            engine._find_evidence(eid).get("related_suspect") == suspect.name
            for eid in engine.presented_evidence_ids
            if engine._find_evidence(eid) is not None
        )

        # 使用正常的升级检查
        new_level = suspect.check_confession_upgrade(has_evidence)

        # 如果正常检查不通过，强制升一级
        if new_level is None and suspect.confession_level < 4:
            suspect.confession_level += 1
            suspect.confession_progress = 0.0
            new_level = suspect.confession_level

        events = [
            NewMessageEvent(
                type="new_message",
                role="system",
                content=f"【心理崩溃】{suspect.name} 的供词层级提升至 {suspect.confession_level}！（行动点 -5）",
                suspect_name=None,
            ),
        ]

        if new_level is not None and new_level > old_level:
            level_name = CONFESSION_LEVELS.get(suspect.confession_level, {}).get("name", "未知")
            events.append(
                ConfessionUpdateEvent(
                    type="confession_update",
                    suspect_index=engine.current_suspect_index,
                    confession_level=suspect.confession_level,
                    confession_progress=0.0,
                    level_name=level_name,
                )
            )

        return events
