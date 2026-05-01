# wiltware 2026
# utils
import os
import subprocess
import sys
from pathlib import Path

from app.config import get_config


def _open_file(file: Path) -> None:
    with open("tui.log", "a") as log:
        if sys.platform == "darwin":  # macos
            subprocess.call(
                ("open", file),
                stdout=log,
                stderr=log,
                text=True,
            )
        elif sys.platform.startswith("win"):  # windows
            os.startfile(file)
        else:
            subprocess.call(
                ("xdg-open", file),
                stdout=log,
                stderr=log,
                text=True,
            )