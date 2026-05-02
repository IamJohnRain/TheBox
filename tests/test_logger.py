from core.logger import setup_logger


def test_setup_logger_returns_thebox_logger():
    logger = setup_logger()
    assert logger.name == "thebox"


def test_setup_logger_does_not_duplicate_handlers():
    logger = setup_logger()
    initial_count = len(logger.handlers)
    logger2 = setup_logger()
    assert len(logger2.handlers) == initial_count
