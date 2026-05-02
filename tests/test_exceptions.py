import pytest

from core.exceptions import (
    ConfigError,
    DatabaseError,
    LLMResponseError,
    NetworkError,
    TheBoxError,
    ValidationError,
)


def test_exception_hierarchy():
    assert issubclass(NetworkError, TheBoxError)
    assert issubclass(LLMResponseError, TheBoxError)
    assert issubclass(DatabaseError, TheBoxError)
    assert issubclass(ValidationError, TheBoxError)
    assert issubclass(ConfigError, TheBoxError)


def test_thebox_error_is_exception():
    assert issubclass(TheBoxError, Exception)


def test_exceptions_can_be_raised():
    with pytest.raises(TheBoxError):
        raise NetworkError("test")
    with pytest.raises(TheBoxError):
        raise ConfigError("test")
