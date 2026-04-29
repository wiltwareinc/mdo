# wiltware 2026 (scaffolded by ChatGPT Codex 5.3 on 2025-02-23)
# connect watcher to everything

import json
from app.config import get_config
from pathlib import Path

from models.file_manager import FileManager


def write_metadata(root: Path, metadata: dict) -> None:
    """
    Dumps metadata into file.
    """
    with open(root / ".metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

def on_change(fm: FileManager, kind: str, path: Path) -> None:
    if not path.exists():
        # would this skip making the metadata?
        return
    if kind == "song":
        metadata = fm.create_metadata("song", path)
        if metadata is None:
            # error message?
            return
        write_metadata(path, metadata)
        fm.refresh_songs()
        return
    
    if kind == "album":
        metadata = fm.create_metadata("album", path)
        if metadata is None:
            # error message?
            return
        write_metadata(path, metadata)
        fm.refresh_albums()
        return
    
def main() -> None:
    root = get_config().root
    fm = FileManager(root)
    
    def _callback(kind: str, path: Path) -> None:
        """
        just passes fm to on_change
        """
        print(f"watcher: {kind} changed -> {path}")
        on_change(fm, kind, path)
        
    from models.watcher import run_watcher
    run_watcher(root, _callback)

if __name__ == "__main__":
    main()