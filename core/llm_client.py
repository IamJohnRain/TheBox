import time
import logging
from typing import Dict, List, Optional

import openai
from openai import OpenAI

from core.config import get_api_key, get_model
from core.exceptions import ConfigError, LLMResponseError, NetworkError

logger = logging.getLogger("thebox")


class LLMClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance.client = None
            cls._instance.model = None
            cls._instance.max_retries = 2
            cls._instance.retry_delay = 1.0
        return cls._instance

    def initialize(self):
        api_key = get_api_key()
        if not api_key:
            logger.warning("未设置 API Key，LLMClient 未初始化，将使用离线模式")
            self._initialized = False
            return
        self.client = OpenAI(api_key=api_key)
        self.model = get_model()
        self._initialized = True
        logger.info(f"LLMClient 已初始化，模型: {self.model}")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def chat_completion(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 500,
        response_format: Optional[Dict] = None,
    ) -> str:
        if not self._initialized:
            raise ConfigError("LLMClient 未初始化，请先设置 API Key 并调用 initialize()")
        for attempt in range(self.max_retries + 1):
            try:
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if response_format:
                    kwargs["response_format"] = response_format

                response = self.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
                if content is None:
                    raise LLMResponseError("LLM 返回 content 为 None")
                return content
            except (openai.APITimeoutError, openai.APIConnectionError) as e:
                logger.warning(f"网络错误，第 {attempt + 1} 次重试: {e}")
                if attempt == self.max_retries:
                    raise NetworkError("网络连接失败，请检查网络设置") from e
                time.sleep(self.retry_delay * (2**attempt))
            except openai.BadRequestError as e:
                logger.error(f"请求参数错误: {e}")
                raise LLMResponseError("请求格式有误") from e
            except Exception as e:
                logger.exception(f"未知错误: {e}")
                raise LLMResponseError(f"LLM 调用失败: {str(e)}") from e
        raise LLMResponseError("重试次数用尽，仍然失败")

    def set_model(self, model_name: str):
        self.model = model_name
        from core.config import set_model

        set_model(model_name)


llm_client = LLMClient()
