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


def _find_project_file(project: Path) -> Path:
    """Find a project file inside of a project folder"""
    # verify
    if not project.is_dir():
        return project # womp womp

    # get recognized suffixes
    suffixes = []
    config = get_config()
    for t in config.templates.values():
        path = t.root
        if path.suffix:
            suffixes.append(path.suffix)
    
    files = sorted(p for p in project.rglob("*") if p.is_file()) # recursive finding for folders

    for f in files:
        if f.stem == f.parent.name: # nested folder check
            return f

    # non-nested, break away the YYYMMDD- from the beginning of the folder
    project_title = project.name.split("-", 1)[1] if "-" in project.name else project.name

    for f in files:
        if f.stem == project_title:
            return f
    
    return project
