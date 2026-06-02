# wiltware 2026
# utils
import os
import shlex
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

def _edit_file_in_terminal(file: Path) -> None:
    editor = os.getenv("VISUAL") or os.getenv("EDITOR") or "nano"
    cmd = [*shlex.split(editor), str(file)]
    subprocess.run(cmd)