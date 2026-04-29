# wiltware 2026
# utils
import os
import subprocess
import sys
from pathlib import Path


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


def _find_reaper(project: Path) -> Path:
    """Quick helper to find a .RPP file."""
    for item in project.iterdir():
        if item.suffix == ".RPP":
            return item
    return project
