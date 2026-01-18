import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional


def read_metadata(file: Path) -> Optional[Dict[str, Any]]:
    if not file.exists():
        logging.error(f"File {file} does not exist. Not reading metadata.")
        return None
    # maybe temp
    json_name = re.compile(rf".*\.json")
    if not json_name.match(file.name):
        logging.error(f"File {file} is not a JSON. Not reading metadata.")
        return None
    with open(file, "r") as item:
        data = json.load(item)
    return data


test: Path = Path("music/songs/20251128-alpine/.metadata.json")
result = read_metadata(test)
print(result.get("created_at") if result is not None else "")
