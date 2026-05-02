from core.providers import (
    DEFAULT_PROVIDER,
    PROVIDERS,
    get_provider,
    get_provider_base_url,
    get_provider_default_model,
    get_provider_list,
    get_provider_models,
)


def test_default_provider_is_minimax():
    assert DEFAULT_PROVIDER == "minimax"


def test_get_provider_list():
    plist = get_provider_list()
    assert len(plist) == len(PROVIDERS)
    ids = [p["id"] for p in plist]
    assert "minimax" in ids
    assert "openai" in ids
    assert "custom" in ids


def test_get_provider():
    p = get_provider("minimax")
    assert p is not None
    assert p["name"] == "MiniMax"


def test_get_provider_not_found():
    assert get_provider("nonexistent") is None


def test_get_provider_base_url():
    assert get_provider_base_url("minimax") == "https://api.minimaxi.com/v1"
    assert get_provider_base_url("openai") == "https://api.openai.com/v1"
    assert get_provider_base_url("nonexistent") == ""


def test_get_provider_default_model():
    assert get_provider_default_model("minimax") == "MiniMax-M2.7"
    assert get_provider_default_model("openai") == "gpt-4o-mini"
    assert get_provider_default_model("nonexistent") == ""


def test_get_provider_models():
    models = get_provider_models("minimax")
    assert "MiniMax-M2.7" in models
    assert get_provider_models("nonexistent") == []
