import json
import os
from pathlib import Path

import keyring


SERVICE_NAME = "thebox"
CONFIG_FILE = Path.home() / ".thebox_config.json"


def get_api_key(service: str = SERVICE_NAME) -> str:
    key = keyring.get_password(service, "api_key")
    return key or ""


def set_api_key(key: str, service: str = SERVICE_NAME) -> None:
    keyring.set_password(service, "api_key", key)


def get_model() -> str:
    if os.environ.get("THEBOX_MODEL"):
        return os.environ["THEBOX_MODEL"]
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config.get("model", "gpt-4o-mini")
        except (json.JSONDecodeError, OSError):
            pass
    return "gpt-4o-mini"


def set_model(model: str) -> None:
    config = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    config["model"] = model
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
