import json
import os
from pathlib import Path
from typing import Optional

import keyring

from core.providers import DEFAULT_PROVIDER, get_provider_base_url, get_provider_default_model


SERVICE_NAME = "thebox"
CONFIG_FILE = Path.home() / ".thebox_config.json"


def _read_config() -> dict:
    """Read the config file, returning an empty dict on failure."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _write_config(config: dict) -> None:
    """Write the config dict to disk."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


# --- Per-provider API key helpers ---

def _keyring_service(provider_id: str) -> str:
    """Return the keyring service name for a given provider."""
    return f"thebox_{provider_id}"


def get_api_key(provider_id: Optional[str] = None, service: Optional[str] = None) -> str:
    """Get the API key for a provider from keyring.

    Supports legacy call: get_api_key() or get_api_key(service='thebox').
    New call: get_api_key(provider_id='minimax').
    """
    if provider_id is not None:
        service = _keyring_service(provider_id)
    elif service is None:
        # Legacy: try current provider first, fallback to SERVICE_NAME
        pid = get_provider()
        if pid and pid != DEFAULT_PROVIDER:
            service = _keyring_service(pid)
        else:
            service = SERVICE_NAME
    key = keyring.get_password(service, "api_key")
    return key or ""


def set_api_key(key: str, provider_id: Optional[str] = None, service: Optional[str] = None) -> None:
    """Set the API key for a provider in keyring."""
    if provider_id is not None:
        service = _keyring_service(provider_id)
    elif service is None:
        pid = get_provider()
        if pid and pid != DEFAULT_PROVIDER:
            service = _keyring_service(pid)
        else:
            service = SERVICE_NAME
    keyring.set_password(service, "api_key", key)


# --- Provider ---

def get_provider() -> str:
    """Get the current provider ID from config or env."""
    if os.environ.get("THEBOX_PROVIDER"):
        return os.environ["THEBOX_PROVIDER"]
    config = _read_config()
    return config.get("provider", DEFAULT_PROVIDER)


def set_provider(provider_id: str) -> None:
    """Set the current provider ID in config."""
    config = _read_config()
    config["provider"] = provider_id
    _write_config(config)


# --- Base URL ---

def get_base_url() -> str:
    """Get the API base URL.

    Priority: env var > config file > provider default.
    """
    if os.environ.get("THEBOX_BASE_URL"):
        return os.environ["THEBOX_BASE_URL"]
    config = _read_config()
    if "base_url" in config:
        return config["base_url"]
    provider_id = config.get("provider", DEFAULT_PROVIDER)
    return get_provider_base_url(provider_id)


def set_base_url(url: str) -> None:
    """Set the API base URL in config."""
    config = _read_config()
    config["base_url"] = url
    _write_config(config)


# --- Model ---

def get_model() -> str:
    """Get the current model name.

    Priority: env var > config file > provider default.
    """
    if os.environ.get("THEBOX_MODEL"):
        return os.environ["THEBOX_MODEL"]
    config = _read_config()
    if "model" in config:
        return config["model"]
    provider_id = config.get("provider", DEFAULT_PROVIDER)
    return get_provider_default_model(provider_id)


def set_model(model: str) -> None:
    """Set the current model name in config."""
    config = _read_config()
    config["model"] = model
    _write_config(config)


# --- Bulk get/set for settings dialog ---

def get_settings() -> dict:
    """Get all LLM settings as a dict."""
    config = _read_config()
    provider_id = config.get("provider", DEFAULT_PROVIDER)
    return {
        "provider": provider_id,
        "base_url": get_base_url(),
        "model": get_model(),
    }


def save_settings(provider: str, base_url: str, model: str, api_key: str = "") -> None:
    """Save all LLM settings at once."""
    config = _read_config()
    config["provider"] = provider
    config["base_url"] = base_url
    config["model"] = model
    _write_config(config)
    if api_key:
        set_api_key(api_key, provider_id=provider)
