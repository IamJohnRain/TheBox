"""Tool system — strategy pattern for interrogation tools."""

from abc import ABC, abstractmethod
from typing import Dict, List, Type

from schemas.events import UIEvent


class Tool(ABC):
    """审讯工具抽象基类。"""

    name: str = ""           # 工具标识名
    display_name: str = ""   # 显示名称
    max_uses: int = 1
    unlock_level: int = 1
    cost_ap: int = 0

    @abstractmethod
    def execute(self, engine, suspect, content: str) -> List[UIEvent]:
        """执行工具逻辑。"""
        ...


# 工具注册表
TOOL_REGISTRY: Dict[str, Type[Tool]] = {}


def register_tool(tool_class: Type[Tool]) -> Type[Tool]:
    """装饰器：注册工具类。"""
    TOOL_REGISTRY[tool_class.name] = tool_class
    return tool_class


def get_tool(name: str) -> Tool:
    """根据名称获取工具实例。"""
    tool_class = TOOL_REGISTRY.get(name)
    if tool_class is None:
        raise ValueError(f"未知工具: {name}")
    return tool_class()


# ── 自动注册所有工具模块 ──
from core.tools import psych_profile as _psych_profile  # noqa: E402, F401
from core.tools import silent_pressure as _silent_pressure  # noqa: E402, F401
from core.tools import lie_detector as _lie_detector  # noqa: E402, F401
from core.tools import threat as _threat  # noqa: E402, F401
from core.tools import dual_interrogation as _dual_interrogation  # noqa: E402, F401
from core.tools import psych_collapse as _psych_collapse  # noqa: E402, F401
