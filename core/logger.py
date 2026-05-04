import logging
import logging.handlers
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "thebox.log"


def setup_logger(level=logging.INFO):
    logger = logging.getLogger("thebox")
    logger.setLevel(level)

    if not logger.handlers:
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s"
            )
        )
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(module)s:%(lineno)d - %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        logger.addHandler(console_handler)

    return logger


logger = setup_logger()
