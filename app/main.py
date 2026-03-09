# wiltware 2026
# entry point for FastAPI
# logging stuff from ChatGPT
from pathlib import Path
import logging
import logging.config

LOG_PATH = Path(__file__).resolve().parents[1] / "file_manager.log"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "file_manager": {
            "class": "logging.FileHandler",
            "filename": str(LOG_PATH),
            "formatter": "standard",
            "level": "DEBUG",
        },
    },
    "root": {"handlers": ["file_manager"], "level": "DEBUG"},
}

logging.config.dictConfig(LOGGING)

from fastapi import FastAPI
from app.api import router as api_router

app = FastAPI(title="MDO API", version="0.1.0")

app.include_router(api_router)
