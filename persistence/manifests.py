# wiltware 2026
# ability for persistience with the manifests

import json
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from domain.manifests import AlbumManifest, Entry, Sequence, SongManifest

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
        _ = file.write("\n")
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
        updated_at=now,
    )

def create_album_manifest(title: str, song_ids: list[str]) -> AlbumManifest:
    now = datetime.now().astimezone()
    sequence_id = f"sequence_{uuid4()}"

    entries = [
        Entry(
            id=f"entry_{uuid4()}",
            song_id=song_id,
        )
        for song_id in song_ids
    ]

    primary_sequence = Sequence(
        id=sequence_id,
        title="Main Album",
        entries=entries,
    )

    return AlbumManifest(
        schema_version=2,
        id=f"album_{uuid4()}",
        title=title,
        primary_sequence_id=sequence_id,
        sequences=[primary_sequence],
        collections=[],
        assets=[],
        created_at=now,
        updated_at=now,
    )

def load_album_manifest(album_root: Path) -> AlbumManifest:
    metadata_path = album_root / METADATA_FILENAME

    with metadata_path.open("r") as f:
        data = json.load(f)

    return AlbumManifest.model_validate(data)

def write_album_manifest(album_root: Path, manifest: AlbumManifest) -> Path:
    metadata_path = album_root / METADATA_FILENAME
    temporary_path = album_root / f"{METADATA_FILENAME}.tmp"

    data = manifest.model_dump(mode="json")

    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
        _ = file.write("\n")
        file.flush()
        os.fsync(file.fileno())

    os.replace(temporary_path, metadata_path)

    return metadata_path
