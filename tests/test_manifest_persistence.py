"""Test creation, loading, and atomic writing of version-2 song manifests.

These tests verify automatically generated defaults, unique stable IDs, JSON
round trips, validation failures, missing/corrupt files, and preservation of an
existing manifest when atomic replacement fails.

Authored by OpenAI Codex on 2026-08-25.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from persistence import manifests as manifest_io
from persistence.manifests import (
    METADATA_FILENAME,
    create_song_manifest,
    load_song_manifest,
    write_song_manifest,
)


@pytest.fixture
def song_root(tmp_path: Path) -> Path:
    """Create an otherwise empty song directory for persistence tests."""
    path = tmp_path / "songs" / "new-song"
    path.mkdir(parents=True)
    return path


def test_create_song_manifest_generates_expected_defaults() -> None:
    before = datetime.now().astimezone()
    manifest = create_song_manifest("New Song")
    after = datetime.now().astimezone()

    assert manifest.schema_version == 2
    assert manifest.title == "New Song"
    assert manifest.description is None
    assert manifest.tags == []
    assert manifest.assets == []
    assert manifest.default_project_id is None
    assert before <= manifest.created_at <= after
    assert manifest.updated_at == manifest.created_at
    assert manifest.created_at.utcoffset() is not None

    prefix, uuid_text = manifest.id.split("_", maxsplit=1)
    assert prefix == "song"
    assert UUID(uuid_text).version == 4


def test_create_song_manifest_generates_unique_ids() -> None:
    first = create_song_manifest("First Song")
    second = create_song_manifest("Second Song")

    assert first.id != second.id


def test_song_manifest_round_trip(song_root: Path) -> None:
    created = create_song_manifest("Round Trip Song")

    metadata_path = write_song_manifest(song_root, created)
    loaded = load_song_manifest(song_root)

    assert metadata_path == song_root / METADATA_FILENAME
    assert metadata_path.is_file()
    assert loaded == created


def test_write_song_manifest_produces_readable_json(song_root: Path) -> None:
    manifest = create_song_manifest("JSON Song")

    metadata_path = write_song_manifest(song_root, manifest)
    raw = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert raw["schema_version"] == 2
    assert raw["id"] == manifest.id
    assert raw["title"] == "JSON Song"
    assert raw["created_at"] == manifest.created_at.isoformat()
    assert raw["updated_at"] == manifest.updated_at.isoformat()
    assert not (song_root / f"{METADATA_FILENAME}.tmp").exists()


def test_song_manifest_round_trip_preserves_unicode(song_root: Path) -> None:
    manifest = create_song_manifest("Canción 🎵")

    write_song_manifest(song_root, manifest)

    assert load_song_manifest(song_root).title == "Canción 🎵"


def test_write_song_manifest_replaces_existing_manifest(song_root: Path) -> None:
    first = create_song_manifest("First Title")
    second = create_song_manifest("Updated Title")
    write_song_manifest(song_root, first)

    write_song_manifest(song_root, second)

    assert load_song_manifest(song_root) == second
    assert not (song_root / f"{METADATA_FILENAME}.tmp").exists()


def test_failed_atomic_replace_preserves_existing_manifest(
    song_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = create_song_manifest("Original Title")
    replacement = create_song_manifest("Replacement Title")
    metadata_path = write_song_manifest(song_root, original)
    original_bytes = metadata_path.read_bytes()

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(manifest_io.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        write_song_manifest(song_root, replacement)

    assert metadata_path.read_bytes() == original_bytes
    assert load_song_manifest(song_root) == original


def test_load_song_manifest_rejects_missing_file(song_root: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_song_manifest(song_root)


def test_load_song_manifest_rejects_invalid_json(song_root: Path) -> None:
    metadata_path = song_root / METADATA_FILENAME
    metadata_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        load_song_manifest(song_root)


def test_load_song_manifest_rejects_invalid_manifest(song_root: Path) -> None:
    metadata_path = song_root / METADATA_FILENAME
    metadata_path.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "id": "not-a-song-id",
                "title": "Invalid Song",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_song_manifest(song_root)
