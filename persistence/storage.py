# wiltware 2026
# storage id management

import json
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from domain.manifests import AssetLocation, StorageManifest

STORAGE_FILENAME = ".storage.json"


def create_storage_manifest(name: str) -> StorageManifest:
    now = datetime.now().astimezone()

    return StorageManifest(
        schema_version=1, id=f"storage_{uuid4()}", name=name, created_at=now
    )


def load_storage_manifest(root: Path) -> StorageManifest:
    path = root / STORAGE_FILENAME

    with path.open("r") as f:
        data = json.load(f)

    return StorageManifest.model_validate(data)


def write_storage_manifest(root: Path, manifest: StorageManifest) -> Path:
    metadata_path = root / STORAGE_FILENAME
    temporary_path = root / f"{STORAGE_FILENAME}.tmp"

    data = manifest.model_dump(mode="json")

    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
        _ = file.write("\n")
        file.flush()
        os.fsync(file.fileno())

    os.replace(temporary_path, metadata_path)

    return metadata_path


def resolve_asset_location(
    root: Path, storage: StorageManifest, location: AssetLocation
) -> Path:
    if not location.storage_id == storage.id:
        raise ValueError("asset location storage id does not match manifest")

    return root / location.path


def initialize_storage(root: Path, name: str) -> StorageManifest:
    """Initializes both the storage manifest and the folders"""
    root.mkdir(parents=True, exist_ok=True)
    
    storage_path = root / STORAGE_FILENAME
    if storage_path.exists():
        raise FileExistsError(f"storage already initialized: {storage_path}")


    # create the folders
    required_dir = [
        root / "songs",
        root / "albums"
    ]

    for dir in required_dir:
        if dir.exists() and not dir.is_dir():
            raise NotADirectoryError(f"expected directory: {dir}")

    for dir in required_dir:
        dir.mkdir(exist_ok=True)
    
    manifest = create_storage_manifest(name)
    _ = write_storage_manifest(root, manifest)

    return manifest
