"""LLM Provider definitions with preset API endpoints."""

from typing import Dict, List, Optional


# Provider definitions: id -> {name, base_url, default_model, models}
PROVIDERS: Dict[str, Dict[str, object]] = {
    "minimax": {
        "name": "MiniMax",
        "base_url": "https://api.minimaxi.com/v1",
        "default_model": "MiniMax-M2.7",
        "models": ["MiniMax-M2.7", "MiniMax-M2.7-lightning"],
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
    },
    "zhipu": {
        "name": "智谱AI",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
        "models": ["glm-4", "glm-4-flash", "glm-4-plus", "glm-4-9b"],
    },
    "dashscope": {
        "name": "阿里通义",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "models": ["qwen-plus", "qwen-turbo", "qwen-max", "qwen-long"],
    },
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "models": ["deepseek-chat", "deepseek-reasoner"],
    },
    "gemini": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "default_model": "gemini-2.0-flash",
        "models": ["gemini-2.0-flash", "gemini-2.5-pro"],
    },
    "local": {
        "name": "本地模型",
        "base_url": "http://localhost:11434/v1",
        "default_model": "",
        "models": [],
    },
    "custom": {
        "name": "自定义",
        "base_url": "",
        "default_model": "",
        "models": [],
    },
}

DEFAULT_PROVIDER = "minimax"


def get_provider_list() -> List[Dict[str, str]]:
    """Return a list of providers for dropdown display."""
    return [{"id": pid, "name": p["name"]} for pid, p in PROVIDERS.items()]


def get_provider(provider_id: str) -> Optional[Dict]:
    """Get provider config by ID, or None if not found."""
    return PROVIDERS.get(provider_id)


def get_provider_base_url(provider_id: str) -> str:
    """Get base_url for a provider."""
    p = PROVIDERS.get(provider_id)
    return p["base_url"] if p else ""


def get_provider_default_model(provider_id: str) -> str:
    """Get default model for a provider."""
    p = PROVIDERS.get(provider_id)
    return p["default_model"] if p else ""


def get_provider_models(provider_id: str) -> List[str]:
    """Get model list for a provider."""
    p = PROVIDERS.get(provider_id)
    return p["models"] if p else []
