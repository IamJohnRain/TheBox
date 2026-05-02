class TheBoxError(Exception):
    pass


class NetworkError(TheBoxError):
    pass


class LLMResponseError(TheBoxError):
    pass


class DatabaseError(TheBoxError):
    pass


class ValidationError(TheBoxError):
    pass


class ConfigError(TheBoxError):
    pass
