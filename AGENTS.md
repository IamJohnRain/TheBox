# The Box: Local Verdict

AI detective interrogation game using PySide6 (Qt) with WebEngine UI and LLM backends.

## Commands

```bash
# Run the app
python main.py

# Run tests (fast, no API calls)
pytest tests/ -m "not slow and not real_api" -v

# Run all tests including slow/e2e (requires API key)
pytest tests/ -v

# Lint and format
flake8 core ui --max-line-length=120
black --check core ui
isort --check core ui

# Pre-commit (runs all checks)
pre-commit run --all-files
```

## Architecture

- `main.py` - Entry point, initializes DB and Qt app with `WebMainWindow`
- `core/` - Business logic (LLM client, interrogation engine, case generator, DB)
- `ui/` - Qt widgets and web UI bridge
- `ui/web/` - HTML/CSS/JS frontend loaded via PySide6 WebEngine
- `schemas/` - TypedDict definitions and validation schemas
- `tests/fixtures/` - Test fixtures including mock case JSON files

## Key Patterns

- **LLMClient singleton** (`core/llm_client.py`): Single instance, initialized on first use. Supports multiple providers (MiniMax, OpenAI, Zhipu, etc.) via `core/providers.py`.
- **InterrogationEngine** (`core/interrogation.py`): Manages game state, suspect agents, and action processing.
- **WebBridge** (`ui/web_bridge.py`): Qt-to-JavaScript bridge exposing Python APIs to the web frontend.
- **Config**: API keys stored in system keyring; settings in `~/.thebox_config.json`. Env vars: `THEBOX_PROVIDER`, `THEBOX_MODEL`, `THEBOX_BASE_URL`.

## Environment

- Python 3.10+
- PySide6 >= 6.5.0 required
- Default provider: MiniMax (`DEFAULT_PROVIDER = "minimax"` in `core/providers.py`)

## Testing

- Tests use `pytest` with `pytest-qt` for GUI testing
- Markers: `@pytest.mark.slow`, `@pytest.mark.real_api` (excluded from CI)
- Fixtures in `tests/fixtures/conftest.py` provide `mock_case_simple`, `mock_engine`, `mock_suspect_agent`
- CI runs on Python 3.10 and 3.11