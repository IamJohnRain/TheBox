"""Fake LLM client for testing - returns configurable responses without API calls."""

import json
from typing import Dict, List, Optional


class FakeLLMClient:
    """Deterministic LLM client for testing. Returns pre-configured responses."""

    def __init__(self):
        self.is_initialized = True
        self._responses: List[str] = []
        self._response_index = 0
        self._default_response = {
            "reply": "我是无辜的",
            "secret_triggered": None,
        }

    def configure_responses(self, responses: List[str]):
        """Set a sequence of responses to return."""
        self._responses = responses
        self._response_index = 0

    def configure_default_response(self, reply: str, secret_triggered: Optional[str] = None):
        """Set the default response when no specific response is configured."""
        self._default_response = {
            "reply": reply,
            "secret_triggered": secret_triggered,
        }

    def chat_completion(self, messages: List[Dict], **kwargs) -> str:
        """Return the next configured response or default."""
        if self._responses and self._response_index < len(self._responses):
            response = self._responses[self._response_index]
            self._response_index += 1
            return response
        return json.dumps(self._default_response)

    def reset(self):
        """Reset the response index."""
        self._response_index = 0


# Global instance for patching
fake_llm = FakeLLMClient()
