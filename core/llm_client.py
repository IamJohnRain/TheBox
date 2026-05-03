import time
import logging
from typing import Dict, List, Optional

import openai
from openai import OpenAI

from core.config import get_api_key, get_base_url, get_model, get_provider
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
            cls._instance.base_url = None
            cls._instance.provider = None
            cls._instance.max_retries = 2
            cls._instance.retry_delay = 1.0
        return cls._instance

    def initialize(self):
        provider = get_provider()
        api_key = get_api_key(provider_id=provider)
        if not api_key:
            logger.warning("未设置 API Key，LLMClient 未初始化，将使用离线模式")
            self._initialized = False
            return
        base_url = get_base_url()
        try:
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        except Exception as e:
            logger.error(f"OpenAI 客户端初始化失败: {e}")
            self._initialized = False
            return
        self.model = get_model()
        self.base_url = base_url
        self.provider = provider
        self._initialized = True
        logger.info(f"LLMClient 已初始化，Provider: {provider}, 模型: {self.model}")

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

        logger.debug(f"API请求: model={self.model}, messages_count={len(messages)}")

        start_time = time.time()
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

                elapsed_ms = int((time.time() - start_time) * 1000)
                usage = response.usage
                tokens_info = (
                    f"prompt={usage.prompt_tokens}, completion={usage.completion_tokens}"
                    if usage
                    else "N/A"
                )
                logger.debug(f"API响应: model={self.model}, latency={elapsed_ms}ms, tokens={tokens_info}")

                if not content:
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

    def reinitialize(self, provider: str, api_key: str, base_url: str, model: str):
        """Re-initialize the client with explicit settings (used by settings dialog)."""
        from core.config import save_settings

        save_settings(provider, base_url, model, api_key)
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.base_url = base_url
        self.provider = provider
        self._initialized = True
        logger.info(f"LLMClient 已重新初始化，Provider: {provider}, 模型: {model}")


llm_client = LLMClient()
