# wiltware 2026
# utils
import subprocess

from pathlib import Path
def _open_file(file: Path) -> None:
    # only linux rn
    with open("tui.log", "a") as log:
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