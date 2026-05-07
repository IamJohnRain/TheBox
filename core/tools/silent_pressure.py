"""Silent pressure tool."""

from core.tools import Tool, register_tool
from schemas.events import NewMessageEvent, SuspectUpdateEvent


@register_tool
class SilentPressureTool(Tool):
    """沉默施压：通过沉默增加嫌疑人压力。"""

    name = "silent_pressure"
    display_name = "沉默施压"
    max_uses = 2
    unlock_level = 10
    cost_ap = 1

    def execute(self, engine, suspect, content: str):
        suspect.pressure = max(0, min(100, suspect.pressure + 15))
        result = suspect.respond("（审讯员沉默地看着你，一言不发...）")
        return [
            NewMessageEvent(type="new_message", role="player", content="[沉默施压]", suspect_name=None),
            NewMessageEvent(type="new_message", role="suspect", content=result["reply"], suspect_name=suspect.name),
            SuspectUpdateEvent(
                type="suspect_update",
                suspect_index=engine.current_suspect_index,
                pressure=suspect.pressure,
                secret_triggered=result.get("secret_triggered"),
            ),
        ]
