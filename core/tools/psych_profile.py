"""Psychological profiling tools - three tiers."""

from core.tools import Tool, register_tool
from schemas.events import NewMessageEvent


@register_tool
class PsychProfileBasicTool(Tool):
    """初级心理侧写：显示性格和恐惧值。"""

    name = "psych_profile_basic"
    display_name = "心理侧写（初级）"
    max_uses = 1
    unlock_level = 2
    cost_ap = 0

    def execute(self, engine, suspect, content: str):
        personality = getattr(suspect, '_suspect_data', {}).get("personality", "未知")
        fear = suspect.fear
        msg = (
            f"【初级心理侧写】\n"
            f"性格: {personality}\n"
            f"恐惧值: {fear}/100\n"
            f"分析: {'对情感诉求较为敏感，共情可能有效' if fear > 60 else '较为冷静，需要更强的证据施压'}。"
        )
        return [NewMessageEvent(type="new_message", role="system", content=msg, suspect_name=None)]


@register_tool
class PsychProfileAdvancedTool(Tool):
    """高级心理侧写：显示性格、恐惧、抗压性和共情易感性。"""

    name = "psych_profile_advanced"
    display_name = "心理侧写（高级）"
    max_uses = 1
    unlock_level = 10
    cost_ap = 0

    def execute(self, engine, suspect, content: str):
        personality = getattr(suspect, '_suspect_data', {}).get("personality", "未知")
        fear = suspect.fear
        defiance = suspect.defiance
        empathy_sus = suspect.empathy_susceptibility
        msg = (
            f"【高级心理侧写】\n"
            f"性格: {personality}\n"
            f"恐惧值: {fear}/100\n"
            f"抗压性: {defiance}/100（{'极强' if defiance > 70 else '一般' if defiance > 30 else '较弱'}）\n"
            f"共情易感性: {empathy_sus}/100（{'高' if empathy_sus > 70 else '一般' if empathy_sus > 30 else '低'}）\n"
            f"策略建议: {'优先使用共情策略' if empathy_sus > defiance else '优先使用施压策略'}。"
        )
        return [NewMessageEvent(type="new_message", role="system", content=msg, suspect_name=None)]


@register_tool
class PsychProfileMasterTool(Tool):
    """大师级心理侧写：显示所有隐藏维度及综合评估。"""

    name = "psych_profile_master"
    display_name = "心理侧写（大师）"
    max_uses = 1
    unlock_level = 15
    cost_ap = 0

    def execute(self, engine, suspect, content: str):
        personality = getattr(suspect, '_suspect_data', {}).get("personality", "未知")
        fear = suspect.fear
        defiance = suspect.defiance
        empathy_sus = suspect.empathy_susceptibility
        deception = suspect.deception_skill
        loyalty = suspect.loyalty
        msg = (
            f"【大师级心理侧写】\n"
            f"性格: {personality}\n"
            f"恐惧值: {fear}/100\n"
            f"抗压性: {defiance}/100\n"
            f"共情易感性: {empathy_sus}/100\n"
            f"欺骗技巧: {deception}/100（{'极强' if deception > 70 else '一般' if deception > 30 else '较弱'}）\n"
            f"忠诚度: {loyalty}/100（{'极强' if loyalty > 70 else '一般' if loyalty > 30 else '较弱'}）\n"
            f"综合评估: {'心理防线坚固，需要证据链+施压组合突破' if defiance > 60 and deception > 60 else '存在弱点，可针对性突破'}。"
        )
        return [NewMessageEvent(type="new_message", role="system", content=msg, suspect_name=None)]
