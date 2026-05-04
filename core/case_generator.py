import json
import logging
import re
import uuid
from typing import Callable, Dict, Optional

import jsonschema

from core.exceptions import ContentFilterError, LLMResponseError, ValidationError
from core.llm_client import LLMClient

logger = logging.getLogger("thebox")

CASE_SCHEMA = {
    "type": "object",
    "required": [
        "case_id",
        "title",
        "victim",
        "cause_of_death",
        "crime_scene",
        "truth",
        "suspects",
        "evidences",
        "interrogation_time_limit_sec",
    ],
    "properties": {
        "case_id": {"type": "string"},
        "title": {"type": "string"},
        "victim": {"type": "string"},
        "cause_of_death": {"type": "string"},
        "crime_scene": {"type": "string"},
        "truth": {"type": "string"},
        "suspects": {
            "type": "array",
            "minItems": 2,
            "items": {
                "type": "object",
                "required": ["name", "role", "personality", "knowledge", "forbidden_to_reveal"],
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"},
                    "personality": {"type": "string"},
                    "knowledge": {"type": "string"},
                    "forbidden_to_reveal": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                    },
                },
                "additionalProperties": False,
            },
        },
        "evidences": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "name", "description"],
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "related_suspect": {"type": ["string", "null"]},
                },
                "additionalProperties": False,
            },
        },
        "interrogation_time_limit_sec": {"type": "integer", "minimum": 60},
    },
    "additionalProperties": False,
}


def _build_system_prompt(background: str) -> str:
    return f"""这是一个虚构的推理解谜游戏（类似剧本杀/密室逃脱），所有内容均为虚构的智力解谜场景，不涉及真实事件。

你是一个推理案件生成器。请根据以下背景故事生成一个完整的悬疑推理案件，严格以 JSON 格式输出。

背景故事：{background}

输出 JSON 必须严格遵循以下 Schema：
{{
  "case_id": "字符串，唯一标识",
  "title": "字符串，案件标题",
  "victim": "字符串，案件当事人姓名",
  "cause_of_death": "字符串，事件原因（如中毒、意外等推理小说常见设定）",
  "crime_scene": "字符串，事件发生地点描述",
  "truth": "字符串，案件真相（必须包含动机、手段、时机三个要素）",
  "suspects": [
    {{
      "name": "字符串，嫌疑人姓名",
      "role": "字符串，与当事人的关系/角色",
      "personality": "字符串，性格描述",
      "knowledge": "字符串，该嫌疑人所知道的信息",
      "forbidden_to_reveal": ["字符串列表，关键人物绝不能直接承认的关键词"]
    }}
  ],
  "evidences": [
    {{
      "id": "字符串，证据ID",
      "name": "字符串，证据名称",
      "description": "字符串，证据描述",
      "related_suspect": "字符串或null，相关嫌疑人"
    }}
  ],
  "interrogation_time_limit_sec": 整数，审讯时限（秒）
}}

重要约束：
1. 所有嫌疑人的 knowledge 并集必须能够推出 truth 中的完整真相。
2. 只有一个关键人物。关键人物的 knowledge 中可以暗示自己与事件的核心关联，但绝不能直接写"我是凶手"或直接坦白。
3. 关键人物的 forbidden_to_reveal 必须包含关键人物绝不能直接承认的关键词（如关键物证名称、核心行为等）。
4. 至少 2 个嫌疑人。
5. truth 必须明确包含动机、手段、时机三个要素。
6. 只输出 JSON，不要输出任何其他内容。
7. 请确保内容为推理小说风格的虚构情节，避免过于直白的暴力描述。"""


def _build_safe_system_prompt(background: str) -> str:
    return f"""这是一个虚构的逻辑推理解谜游戏，所有内容均为虚构，仅供娱乐。

你是一个逻辑谜题生成器。请根据以下背景生成一个悬疑推理谜题，严格以 JSON 格式输出。

背景：{background}

输出 JSON 必须严格遵循以下 Schema：
{{
  "case_id": "字符串，唯一标识",
  "title": "字符串，谜题标题",
  "victim": "字符串，谜题中心人物姓名",
  "cause_of_death": "字符串，事件发生的原因",
  "crime_scene": "字符串，事件发生的地点",
  "truth": "字符串，谜题的完整答案（必须包含动机、手段、时机三个要素）",
  "suspects": [
    {{
      "name": "字符串，人物姓名",
      "role": "字符串，与中心人物的关系/角色",
      "personality": "字符串，性格描述",
      "knowledge": "字符串，该人物所知道的信息",
      "forbidden_to_reveal": ["字符串列表，解答者不能直接从该人物口中获得的关键词"]
    }}
  ],
  "evidences": [
    {{
      "id": "字符串，线索ID",
      "name": "字符串，线索名称",
      "description": "字符串，线索描述",
      "related_suspect": "字符串或null，相关人物"
    }}
  ],
  "interrogation_time_limit_sec": 整数，解谜时限（秒）
}}

重要约束：
1. 所有人物的 knowledge 并集必须能够推出 truth 中的完整答案。
2. 只有一个核心人物。该人物的 knowledge 中可以暗示自己与事件的核心关联，但不能直接坦白。
3. 核心人物的 forbidden_to_reveal 必须包含该人物不能直接说出的关键词。
4. 至少 2 个人物。
5. truth 必须明确包含动机、手段、时机三个要素。
6. 只输出 JSON，不要输出任何其他内容。
7. 用推理小说、侦探故事的文风来描述，保持趣味性和逻辑性。"""


def generate_case(
    background: str,
    max_retries: int = 1,
    progress_callback: Optional[Callable[[str], None]] = None,
    safe_mode: bool = False,
) -> Dict:
    def _progress(msg: str):
        if progress_callback:
            progress_callback(msg)

    client = LLMClient()
    _progress("🎬 正在打造故事场景...")
    if not client.is_initialized:
        client.initialize()

    if not client.is_initialized:
        raise LLMResponseError("LLMClient 未初始化，无法生成案件。请设置 API Key。")

    last_error = None
    use_safe_prompt = safe_mode

    for attempt in range(max_retries + 1):
        try:
            temperature = 0.8 if attempt == 0 else 0.9

            if use_safe_prompt:
                _progress("🛡️ 正在使用安全创作模式...")
                system_prompt = _build_safe_system_prompt(background)
            else:
                system_prompt = _build_system_prompt(background)

            _progress("🧠 正在与 AI 构思案件...")

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "请生成案件。"},
            ]

            content = client.chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=2000,
            )

            _progress("🔍 正在编织线索与谜题...")

            text = content.strip()
            text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            case_dict = json.loads(text)
            case_dict["case_id"] = case_dict.get("case_id", str(uuid.uuid4()))

            _progress("⚖️ 正在校验逻辑自洽性...")
            jsonschema.validate(instance=case_dict, schema=CASE_SCHEMA)

            _progress("✅ 案件世界构建完成！")
            logger.info(f"案件生成成功: {case_dict.get('case_id', 'unknown')}")
            return case_dict

        except ContentFilterError as e:
            last_error = e
            if not use_safe_prompt:
                logger.warning(f"第 {attempt + 1} 次触发内容过滤，切换安全提示词重试")
                use_safe_prompt = True
                continue
            logger.warning(f"第 {attempt + 1} 次：安全提示词也触发内容过滤: {e}")
        except json.JSONDecodeError as e:
            last_error = e
            logger.warning(f"第 {attempt + 1} 次：JSON 解析失败: {e}")
        except jsonschema.ValidationError as e:
            last_error = e
            logger.warning(f"第 {attempt + 1} 次：Schema 校验失败: {e.message}")
        except Exception as e:
            last_error = e
            logger.warning(f"第 {attempt + 1} 次生成失败: {e}")

    raise ValidationError(f"案件生成失败，重试 {max_retries} 次后仍不通过: {last_error}")
