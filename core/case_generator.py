import json
import logging
import re
import uuid
from typing import Dict

import jsonschema

from core.exceptions import LLMResponseError, ValidationError
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
    return f"""你是一个推理案件生成器。请根据以下背景故事生成一个完整的谋杀案案件，严格以 JSON 格式输出。

背景故事：{background}

输出 JSON 必须严格遵循以下 Schema：
{{
  "case_id": "字符串，唯一标识",
  "title": "字符串，案件标题",
  "victim": "字符串，受害者姓名",
  "cause_of_death": "字符串，死因",
  "crime_scene": "字符串，犯罪现场描述",
  "truth": "字符串，案件真相（必须包含动机、手段、时机三个要素）",
  "suspects": [
    {{
      "name": "字符串，嫌疑人姓名",
      "role": "字符串，与受害者的关系/角色",
      "personality": "字符串，性格描述",
      "knowledge": "字符串，该嫌疑人所知道的信息",
      "forbidden_to_reveal": ["字符串列表，真凶绝不能直接承认的关键词"]
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
2. 只有一个真凶。真凶的 knowledge 中可以暗示自己是凶手，但绝不能直接写"我是凶手"或直接坦白。
3. 真凶的 forbidden_to_reveal 必须包含真凶绝不能直接承认的关键词（如凶器名称、犯罪行为等）。
4. 至少 2 个嫌疑人。
5. truth 必须明确包含动机、手段、时机三个要素。
6. 只输出 JSON，不要输出任何其他内容。"""


def generate_case(background: str, max_retries: int = 1) -> Dict:
    client = LLMClient()
    if not client.is_initialized:
        client.initialize()

    if not client.is_initialized:
        raise LLMResponseError("LLMClient 未初始化，无法生成案件。请设置 API Key。")

    system_prompt = _build_system_prompt(background)
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            temperature = 0.8 if attempt == 0 else 0.9

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "请生成案件。"},
            ]

            content = client.chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=2000,
            )

            # Strip markdown code fences if present (some models wrap JSON in ```json ... ```)
            text = content.strip()
            # Strip <think>...</think> blocks (reasoning model output like MiniMax-M2.7)
            text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
            if text.startswith("```"):
                # Remove opening fence (with optional language tag)
                text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            case_dict = json.loads(text)
            case_dict["case_id"] = case_dict.get("case_id", str(uuid.uuid4()))

            jsonschema.validate(instance=case_dict, schema=CASE_SCHEMA)

            logger.info(f"案件生成成功: {case_dict.get('case_id', 'unknown')}")
            return case_dict

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
