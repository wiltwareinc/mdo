import os
from functools import lru_cache
from pathlib import Path
from app.config import get_config
from models.file_manager import FileManager

@lru_cache(maxsize=1)
def get_file_manager() -> FileManager:
    # root = Path(os.getenv("MDO_ROOT", "./music")).resolve() #! needs to be changed to something customizable
    config = get_config()
    return FileManager(config.root)