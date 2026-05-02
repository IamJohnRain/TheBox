import json
import logging
from typing import Dict, List, Optional

from core.exceptions import LLMResponseError, NetworkError
from core.llm_client import llm_client

logger = logging.getLogger("thebox")


class SuspectAgent:
    """Manage a single suspect's dialogue, pressure, and forbidden content filtering."""

    def __init__(self, suspect_data: dict, case_title: str) -> None:
        self.name: str = suspect_data["name"]
        self.pressure: int = 50
        self.memory: List[Dict[str, str]] = []
        self._suspect_data: dict = suspect_data
        self._forbidden_to_reveal: List[str] = suspect_data.get("forbidden_to_reveal", [])
        self._case_title: str = case_title
        self._system_prompt: str = self._build_system_prompt(suspect_data, case_title)

    def _build_system_prompt(self, suspect_data: dict, case_title: str) -> str:
        """Build the system prompt embedding role, personality, knowledge, and forbidden list."""
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
                "即使压力值很高，你也决不能透露以上任何内容。"
            )

        prompt = (
            f"你是一起案件「{case_title}」中的嫌疑人。\n\n"
            f"## 角色背景\n{role}\n\n"
            f"## 性格特征\n{personality}\n\n"
            f"## 你所知道的信息\n{knowledge}\n"
            f"{forbidden_block}\n\n"
            f"## 当前压力值：{self.pressure}/100\n"
            "压力值说明：压力越高，你越慌乱，可能语无伦次、答非所问，但仍然不能直接说出禁止内容。"
            "压力低时你表现得冷静、从容。\n\n"
            "## 回复要求\n"
            "- 用1-3句话回复，符合你的角色人设。\n"
            "- 必须以JSON格式输出，包含以下键：\n"
            '  - "reply": 你的回复文本\n'
            '  - "pressure_change": 整数，正值表示压力增加，负值表示压力减少\n'
            '  - "secret_triggered": 如果你不小心提到了禁止内容，填写匹配到的条目；否则为null\n'
            "- 即使你认为玩家已经猜到了真相，也不要在reply中泄露禁止内容。"
        )
        return prompt

    def respond(self, player_input: str, context: Optional[dict] = None) -> dict:
        """Process player input and return a reply with pressure change and secret status."""
        result: Dict = {
            "reply": "",
            "pressure_change": 0,
            "secret_triggered": None,
        }

        if not llm_client.is_initialized:
            logger.warning("LLMClient 未初始化，返回默认回复")
            result["reply"] = "（嫌疑人沉默不语）"
            self._append_memory(player_input, result["reply"])
            return result

        messages = [{"role": "system", "content": self._system_prompt}]
        messages.extend(self.memory[-10:])
        messages.append({"role": "user", "content": player_input})

        try:
            raw = llm_client.chat_completion(
                messages=messages,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(raw)
            result["reply"] = str(parsed.get("reply", ""))
            result["pressure_change"] = int(parsed.get("pressure_change", 0))
            result["secret_triggered"] = parsed.get("secret_triggered")
        except (NetworkError, LLMResponseError, json.JSONDecodeError, ValueError) as exc:
            logger.warning(f"LLM 调用或解析失败: {exc}")
            result["reply"] = "（嫌疑人沉默不语）"
            result["pressure_change"] = 0
            result["secret_triggered"] = None

        self._postprocess(result)
        self.pressure = max(0, min(100, self.pressure + result["pressure_change"]))
        self._append_memory(player_input, result["reply"])
        self.truncate_memory()

        return result

    def _postprocess(self, result: dict) -> None:
        """Check reply for forbidden substrings and sanitize if matched."""
        reply_lower = result["reply"].lower()
        for item in self._forbidden_to_reveal:
            if item.lower() in reply_lower:
                logger.info(f"嫌疑人 [{self.name}] 泄露禁止内容，已替换: {item}")
                result["reply"] = "（嫌疑人略显紧张，但并没有直接回答你的问题。）"
                result["secret_triggered"] = item
                result["pressure_change"] += 20
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
