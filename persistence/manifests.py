# wiltware 2026
# ability for persistience with the manifests

from datetime import datetime
import json
import os
from pathlib import Path
from uuid import uuid4

from domain.manifests import SongManifest

METADATA_FILENAME = ".metadata.json"

def load_song_manifest(path: Path) -> SongManifest:
    metadata_path = path / METADATA_FILENAME

    with metadata_path.open("r") as f:
        data = json.load(f)

    return SongManifest.model_validate(data)


def write_song_manifest(path: Path, manifest: SongManifest) -> Path:
    metadata_path = path / METADATA_FILENAME
    temporary_path = path / f"{METADATA_FILENAME}.tmp"

    data = manifest.model_dump(mode="json")

    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
        file.write("\n")
        file.flush()
        os.fsync(file.fileno())
    
    os.replace(temporary_path, metadata_path)

    return metadata_path

def create_song_manifest(title: str) -> SongManifest:
    now = datetime.now().astimezone()

    return SongManifest(
        schema_version=2,
        id=f"song_{uuid4()}",
        title=title,
        created_at=now,
        updated_at=now
    )