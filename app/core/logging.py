import sys
from pathlib import Path
from datetime import timezone, timedelta
from loguru import logger

LOGS_DIR = Path("logs")

def setup_logger():

    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def patch_logger(record):
        record.update(time=record['time'].astimezone(timezone(timedelta(hours=3))))
        return record

    logger_config = {
        "handlers": [
            {
                "sink": sys.stdout,
                "format": (
                    "<white>{time:YYYY-MM-DD HH:mm:ss.SSS:Z}</white> | "
                    "<level>{level: <8}</level> | "
                    "{name}:{function}:{line} - <magenta>{message}</magenta>"
                ),
                "level": "DEBUG",
                "backtrace": True,
                "diagnose": True,
                "enqueue": True,
                "filter": lambda record: record["level"].no >= logger.level("DEBUG").no,
            },
            {
                "sink": str(LOGS_DIR / "bot.log"),  # ✅ Путь в папку
                "format": (
                    "{time:YYYY-MM-DD HH:mm:ss.SSS:Z} | "
                    "{level: <8} | "
                    "{name}:{function}:{line} | "
                    "{message}"
                ),
                "level": "DEBUG",
                "rotation": "50 MB",
                "retention": "14 days",
                "compression": "zip",
                "enqueue": True,
                "backtrace": True,
                "diagnose": True,
            },
            {
                "sink": str(LOGS_DIR / "errors.log"),
                "format": (
                    "{time:YYYY-MM-DD HH:mm:ss.SSS:Z} | "
                    "{level: <8} | "
                    "{name}:{function}:{line} | "
                    "{message}"
                ),
                "level": "ERROR",
                "rotation": "20 MB",
                "retention": "30 days",
                "compression": "zip",
                "enqueue": True,
                "backtrace": True,
                "diagnose": True,
                "serialize": False,
            },
        ],
        "patcher": patch_logger,
    }

    logger.remove()
    logger.configure(**logger_config)
    logger.info(f"📁 Логи: {LOGS_DIR.resolve()}")