import json
import logging
import re
from typing import Dict, List, Optional

from core.exceptions import LLMResponseError, NetworkError
from core.game_config import (
    CONFESSION_PROGRESS_RATE,
    CONFESSION_THRESHOLDS,
    DEFAULT_INITIAL_PRESSURE,
    DIMENSION_BOUNDS,
    PERSONALITY_DIMENSIONS,
    PERSONALITY_PRIMARY_WEIGHT,
    PERSONALITY_SECONDARY_WEIGHT,
    PRESSURE_SEGMENTS,
)
from core.llm_client import llm_client

logger = logging.getLogger("thebox")


class SuspectAgent:
    """Manage a single suspect's dialogue, pressure, and forbidden content filtering."""

    def __init__(self, suspect_data: dict, case_title: str) -> None:
        self.name: str = suspect_data["name"]
        self._suspect_data: dict = suspect_data
        self._forbidden_to_reveal: List[str] = suspect_data.get("forbidden_to_reveal", [])
        self._case_title: str = case_title
        self._system_prompt: str = self._build_system_prompt(suspect_data, case_title)

        # 压力值（从配置读取初始值）
        self.pressure: int = DEFAULT_INITIAL_PRESSURE

        # 记忆系统
        self.memory: List[Dict[str, str]] = []

        # 供词系统
        self.confession_level: int = 0
        self.confession_progress: float = 0.0
        self.turn_count: int = 0

        # 隐藏维度 - 从数据或性格计算
        self.fear: int = self._calculate_dimension("fear", suspect_data)
        self.defiance: int = self._calculate_dimension("defiance", suspect_data)
        self.empathy_susceptibility: int = self._calculate_dimension("empathy_susceptibility", suspect_data)
        self.deception_skill: int = self._calculate_dimension("deception_skill", suspect_data)
        self.loyalty: int = self._calculate_dimension("loyalty", suspect_data)
        self.credibility: int = 50  # 不可见，固定初始值

    def _calculate_dimension(self, dim_name: str, suspect_data: dict) -> int:
        """Calculate dimension value from personality or explicit value.

        Priority:
        1. Explicit value in suspect_data (with "hidden_" prefix or direct key)
        2. Primary + secondary personality weighted calculation
        3. Primary personality only
        4. Default value (50)
        """
        # 1. Explicit value (check both "dim_name" and "hidden_dim_name" keys)
        if dim_name in suspect_data:
            return self._clamp_dimension(dim_name, suspect_data[dim_name])
        hidden_key = f"hidden_{dim_name}"
        if hidden_key in suspect_data:
            return self._clamp_dimension(dim_name, suspect_data[hidden_key])

        # 2. Get personality dimensions
        primary = suspect_data.get("personality", "")
        secondary = suspect_data.get("personality_secondary", "")

        primary_dims = PERSONALITY_DIMENSIONS.get(primary, {})
        secondary_dims = PERSONALITY_DIMENSIONS.get(secondary, {})

        if primary_dims and secondary_dims:
            # Weighted combination
            primary_val = primary_dims.get(dim_name, 50)
            secondary_val = secondary_dims.get(dim_name, 50)
            calculated = int(
                primary_val * PERSONALITY_PRIMARY_WEIGHT
                + secondary_val * PERSONALITY_SECONDARY_WEIGHT
            )
            return self._clamp_dimension(dim_name, calculated)
        elif primary_dims:
            # Primary only
            return self._clamp_dimension(dim_name, primary_dims.get(dim_name, 50))

        # 4. Default
        return self._clamp_dimension(dim_name, 50)

    def _clamp_dimension(self, dim_name: str, value: int) -> int:
        """Clamp dimension value to bounds."""
        bounds = DIMENSION_BOUNDS.get(dim_name, {"min": 0, "max": 100})
        return max(bounds["min"], min(bounds["max"], value))

    def check_confession_upgrade(self, has_evidence: bool = False) -> Optional[int]:
        """检查是否满足供词升级条件，返回升级后的层级或 None。

        Args:
            has_evidence: 是否已出示过关联证据

        Returns:
            升级后的层级，或 None（不升级）
        """
        if self.confession_level >= 4:
            return None

        next_level = self.confession_level + 1
        threshold = CONFESSION_THRESHOLDS.get(self.confession_level, {})

        # 检查压力条件
        required_pressure = threshold.get("pressure", 100)
        if self.pressure < required_pressure:
            return None

        # 检查轮次条件
        min_turns = threshold.get("min_turns", 0)
        if self.turn_count < min_turns:
            return None

        # 检查证据条件
        if threshold.get("requires_evidence", False) and not has_evidence:
            return None

        # 所有条件满足，升级
        self.confession_progress = 1.0
        self.confession_level = next_level
        self.confession_progress = 0.0
        return next_level

    def update_confession_progress(self) -> float:
        """根据当前压力更新供词反馈进度，返回更新后的进度值。

        注意：该进度只用于 UI/复盘反馈，不阻塞 check_confession_upgrade。
        """
        if self.confession_level >= 4:
            return 1.0

        # 确定当前压力段
        rate = 0.02  # 默认
        for seg_name, (low, high) in PRESSURE_SEGMENTS.items():
            if low <= self.pressure < high:
                rate = CONFESSION_PROGRESS_RATE.get(seg_name, 0.02)
                break

        self.confession_progress = min(1.0, self.confession_progress + rate)
        return self.confession_progress

    def _build_system_prompt(self, suspect_data: dict, case_title: str) -> str:
        """Build the system prompt embedding role, personality, knowledge, and forbidden list.

        The pressure value is a placeholder ``{pressure_value}`` that must be
        resolved at call-time via :meth:`_get_system_message` so the prompt
        always reflects the *current* pressure level.
        """
        role = suspect_data.get("role", "")
        personality = suspect_data.get("personality", "")
        knowledge = suspect_data.get("knowledge", "")
        forbidden = suspect_data.get("forbidden_to_reveal", [])

        forbidden_block = ""
        if forbidden:
            items = "\n".join(f"- {item}" for item in forbidden)
            forbidden_block = (
                "\n\n## 绝对禁止泄露的内容\n"
                "以下内容是你绝不能在回复中透露的，无论是直接说出还是以同义表达暗示：\n"
                f"{items}\n"
                "即使压力值很高，你也决不能透露以上任何内容。这是游戏规则。"
            )

        prompt = (
            f"你是一个虚构的推理解谜游戏中的角色。这是一个类似剧本杀的智力游戏，所有内容均为虚构。\n"
            f"你在案件「{case_title}」中是一个被调查的人物。\n\n"
            f"## 角色背景\n{role}\n\n"
            f"## 性格特征\n{personality}\n\n"
            f"## 你所知道的信息\n{knowledge}\n"
            f"{forbidden_block}\n\n"
            f"## 当前压力值：{{pressure_value}}/100\n"
            "压力值说明：压力越高，你越慌乱，可能语无伦次、答非所问，但仍然不能直接说出禁止内容。"
            "压力低时你表现得冷静、从容。\n\n"
            "## 回复要求\n"
            "- 用1-3句话回复，符合你的角色人设。\n"
            "- 必须以JSON格式输出，包含以下键：\n"
            '  - "reply": 你的回复文本\n'
            '  - "secret_triggered": 如果你不小心提到了禁止内容，填写匹配到的条目；否则为null\n'
            "- 即使你认为玩家已经猜到了真相，也不要在reply中泄露禁止内容。"
        )
        return prompt

    def _get_system_message(self) -> dict:
        """构建带有当前压力值的系统消息。"""
        prompt = self._system_prompt.replace("{pressure_value}", str(self.pressure))
        return {"role": "system", "content": prompt}

    def _call_llm(self, user_prompt: str) -> dict:
        """调用 LLM 并解析 JSON 回复。

        Args:
            user_prompt: 用户消息内容

        Returns:
            包含 reply, secret_triggered 的字典
            （注意：不再返回 pressure_change，压力由引擎程序化计算）
        """
        result = {
            "reply": "",
            "secret_triggered": None,
        }

        if not llm_client.is_initialized:
            result["reply"] = "（嫌疑人沉默不语）"
            return result

        messages = [self._get_system_message()]
        messages.extend(self.memory[-10:])
        messages.append({"role": "user", "content": user_prompt})

        try:
            raw = llm_client.chat_completion(
                messages=messages,
                response_format={"type": "json_object"},
            )
            if not raw:
                raise LLMResponseError("LLM 返回空内容")
            text = raw.strip()
            # Remove thinking tags if present
            text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            parsed = json.loads(text)
            result["reply"] = str(parsed.get("reply", ""))
            result["secret_triggered"] = parsed.get("secret_triggered")
        except (NetworkError, LLMResponseError, json.JSONDecodeError, ValueError) as exc:
            logger.warning(f"LLM 调用或解析失败: {exc}")
            result["reply"] = "（嫌疑人沉默不语）"

        return result

    def respond(self, player_input: str, context: Optional[dict] = None) -> dict:
        """Process player input and return a reply with secret status."""
        result = self._call_llm(player_input)

        # 压力变化由引擎程序化计算，此处不再处理 pressure_change
        self._postprocess(result)
        self._append_memory(player_input, result["reply"])
        self.truncate_memory()

        logger.debug(
            f"嫌疑人[{self.name}]回复: {result['reply'][:100]}, secret_triggered={result.get('secret_triggered')}"
        )
        return result

    def respond_evidence(
        self, evidence_description: str, evidence_type: str = "unknown"
    ) -> dict:
        """React to presented evidence without seeing the evidence name.

        Args:
            evidence_description: 证据描述（不含证据名）
            evidence_type: 证据类型 (physical/document/testimony/unknown)

        Returns:
            包含 reply, secret_triggered, rebuttal, rebuttal_believable 的字典
            （注意：不再返回 pressure_change，压力由引擎程序化计算）
        """
        evidence_prompt = (
            f"审讯员向你出示了一件{evidence_type}证据。\n"
            f"证据内容：{evidence_description}\n\n"
            "请根据你的角色和所知信息，对这件证据做出反应。\n"
            "如果你认为可以反驳这件证据，请在JSON中添加：\n"
            '  - "rebuttal": true 如果你想反驳这件证据，否则false\n'
            '  - "rebuttal_believable": true 如果你的反驳可信，否则false\n'
            "反驳的可信度取决于你的欺骗技巧和当前压力状态。"
        )

        result = self._call_llm(evidence_prompt)
        self._postprocess(result)
        self._append_memory(evidence_prompt, result["reply"])
        self.truncate_memory()

        # 确保反驳字段存在
        if "rebuttal" not in result:
            result["rebuttal"] = False
        if "rebuttal_believable" not in result:
            result["rebuttal_believable"] = False

        return result

    def _postprocess(self, result: dict) -> None:
        """Check reply for forbidden substrings and sanitize if matched.

        与供词系统联动：
        - 供词层级 < 3：替换回复但不触发胜利（仅增加压力）
        - 供词层级 >= 3：允许触发胜利（完美胜利条件）
        """
        reply_lower = result["reply"].lower()
        for item in self._forbidden_to_reveal:
            if item.lower() in reply_lower:
                if self.confession_level >= 3:
                    # 高供词层级：允许触发完整胜利
                    logger.info(f"角色 [{self.name}] 高供词层级下泄露禁止内容: {item}")
                    result["secret_triggered"] = item
                else:
                    # 低供词层级：替换回复但不触发胜利
                    logger.info(f"角色 [{self.name}] 低供词层级下提及禁止内容，已拦截: {item}")
                    result["reply"] = "（对方略显紧张，但并没有直接回答你的问题。）"
                    result["secret_triggered"] = None
                return

    def _append_memory(self, user_input: str, reply: str) -> None:
        """Append a user-assistant turn to memory."""
        self.memory.append({"role": "user", "content": user_input})
        self.memory.append({"role": "assistant", "content": reply})

    def truncate_memory(self, max_turns: int = 10) -> None:
        """Keep only the last max_turns dialogue turns in memory."""
        max_entries = max_turns * 2
        if len(self.memory) > max_entries:
            self.memory = self.memory[-max_entries:]
