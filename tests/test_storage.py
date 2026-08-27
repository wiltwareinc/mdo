"""Test portable storage identity persistence and asset path resolution.

These tests verify the version-1 storage fixture, UUID generation, atomic JSON
round trips, explicit one-time initialization, duplicate protection, matching
storage references, and rejection of unavailable storage IDs.

Authored by OpenAI Codex on 2026-08-27.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from domain.manifests import AssetLocation, StorageManifest
from persistence import storage


@pytest.fixture
def storage_data() -> dict:
    path = Path(__file__).parent / "fixtures" / "storage" / "storage.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_storage_fixture_is_valid(storage_data: dict) -> None:
    manifest = StorageManifest.model_validate(storage_data)

    assert manifest.schema_version == 1
    assert manifest.id == "storage_1c2ee06f-dbc8-49c8-87ab-c279b5444a91"
    assert manifest.name == "Studio SSD"


def test_create_storage_manifest_generates_unique_storage_ids() -> None:
    first = storage.create_storage_manifest("First Storage")
    second = storage.create_storage_manifest("Second Storage")

    assert first.schema_version == 1
    assert first.id.startswith("storage_")
    assert second.id.startswith("storage_")
    assert first.id != second.id


def test_storage_manifest_write_and_load_round_trip(
    tmp_path: Path,
    storage_data: dict,
) -> None:
    manifest = StorageManifest.model_validate(storage_data)

    written_path = storage.write_storage_manifest(tmp_path, manifest)

    assert written_path == tmp_path / storage.STORAGE_FILENAME
    assert written_path.is_file()
    assert written_path.read_text(encoding="utf-8").endswith("\n")
    assert not (tmp_path / f"{storage.STORAGE_FILENAME}.tmp").exists()
    assert storage.load_storage_manifest(tmp_path) == manifest


def test_initialize_storage_creates_identity_file(tmp_path: Path) -> None:
    manifest = storage.initialize_storage(tmp_path, "Main Library")

    assert manifest.name == "Main Library"
    assert storage.load_storage_manifest(tmp_path) == manifest


def test_initialize_storage_rejects_existing_identity(tmp_path: Path) -> None:
    original = storage.initialize_storage(tmp_path, "Original Library")

    with pytest.raises(FileExistsError, match="already initialized"):
        storage.initialize_storage(tmp_path, "Replacement Library")

    assert storage.load_storage_manifest(tmp_path) == original


def test_resolve_asset_location_uses_matching_storage_root(
    tmp_path: Path,
    storage_data: dict,
) -> None:
    manifest = StorageManifest.model_validate(storage_data)
    location = AssetLocation(
        storage_id=manifest.id,
        path="songs/example/projects/shared-session",
    )

    resolved = storage.resolve_asset_location(tmp_path, manifest, location)

    assert resolved == tmp_path / "songs/example/projects/shared-session"


def test_resolve_asset_location_rejects_different_storage(
    tmp_path: Path,
    storage_data: dict,
) -> None:
    manifest = StorageManifest.model_validate(storage_data)
    location = AssetLocation(
        storage_id="storage_2f8c2a4e-8bd2-4d57-a1c7-7e4cbfd52a91",
        path="songs/example/projects/shared-session",
    )

    with pytest.raises(ValueError, match="does not match"):
        storage.resolve_asset_location(tmp_path, manifest, location)

