"""Validate the portable version-2 song and album manifest contracts.

These tests cover successful fixture parsing, strict schema handling, asset
purpose validation, and internal default-project/primary-sequence references.

Authored by OpenAI Codex on 2026-08-07.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import ValidationError

from domain.manifests import AlbumManifest, SongManifest


def test_song_fixture_is_valid(load_manifest: Callable[[str], dict]) -> None:
    song = SongManifest.model_validate(load_manifest("song.json"))

    assert song.title == "Beautiful Tune"
    assert song.default_project_id == song.assets[0].id


def test_album_fixture_is_valid(load_manifest: Callable[[str], dict]) -> None:
    album = AlbumManifest.model_validate(load_manifest("album.json"))

    assert album.title == "Awesome Album"
    assert album.primary_sequence_id == album.sequences[0].id


@pytest.mark.parametrize("model, filename", [
    (SongManifest, "song.json"),
    (AlbumManifest, "album.json"),
])
def test_manifest_rejects_unknown_fields(
    model: type[SongManifest] | type[AlbumManifest],
    filename: str,
    load_manifest: Callable[[str], dict],
) -> None:
    data = load_manifest(filename)
    data["unexpected"] = "must not be silently discarded"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        model.model_validate(data)


@pytest.mark.parametrize("model, filename", [
    (SongManifest, "song.json"),
    (AlbumManifest, "album.json"),
])
def test_manifest_requires_schema_version_two(
    model: type[SongManifest] | type[AlbumManifest],
    filename: str,
    load_manifest: Callable[[str], dict],
) -> None:
    data = load_manifest(filename)
    data["schema_version"] = 3

    with pytest.raises(ValidationError):
        model.model_validate(data)


def test_song_rejects_missing_default_project_reference(
    load_manifest: Callable[[str], dict],
) -> None:
    data = load_manifest("song.json")
    data["default_project_id"] = "asset_missing"

    with pytest.raises(
        ValidationError,
        match="default_project_id must reference an asset in this song",
    ):
        SongManifest.model_validate(data)


def test_song_rejects_non_project_default(
    load_manifest: Callable[[str], dict],
) -> None:
    data = load_manifest("song.json")
    data["assets"][0]["kind"] = "audio"

    with pytest.raises(
        ValidationError,
        match="default_project_id must reference a project asset",
    ):
        SongManifest.model_validate(data)


def test_asset_rejects_unknown_purpose(
    load_manifest: Callable[[str], dict],
) -> None:
    data = load_manifest("song.json")
    data["assets"][0]["purpose"] = "song_sesion"

    with pytest.raises(ValidationError):
        SongManifest.model_validate(data)


def test_album_rejects_missing_primary_sequence_reference(
    load_manifest: Callable[[str], dict],
) -> None:
    data = load_manifest("album.json")
    data["primary_sequence_id"] = "sequence_missing"

    with pytest.raises(
        ValidationError,
        match="primary_sequence_id must reference a sequence in this manifest",
    ):
        AlbumManifest.model_validate(data)
