"""Validate the portable version-2 song and album manifest contracts.

These tests cover successful fixture parsing, strict schema handling, every
prefixed UUID field, storage-relative asset locations, shared project assets,
asset purposes, and internal manifest references.

Authored by OpenAI Codex on 2026-08-07; ID coverage expanded on 2026-08-11;
shared asset-location coverage added on 2026-08-27.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import ValidationError

from domain.manifests import (
    AlbumManifest,
    Asset,
    Collection,
    Entry,
    Sequence,
    SongManifest,
    validate_prefixed_uuid,
)


UUID4 = "2f8c2a4e-8bd2-4d57-a1c7-7e4cbfd52a91"
UUID1 = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"


def _error_locations(error: ValidationError) -> set[tuple[str | int, ...]]:
    """Return Pydantic error locations for precise field-level assertions."""
    return {tuple(item["loc"]) for item in error.errors()}


def test_song_fixture_is_valid(load_manifest: Callable[[str], dict]) -> None:
    song = SongManifest.model_validate(load_manifest("song.json"))

    assert song.title == "Beautiful Tune"
    assert song.default_project_id == song.assets[0].id
    assert song.assets[0].location.storage_id == (
        "storage_1c2ee06f-dbc8-49c8-87ab-c279b5444a91"
    )
    assert song.assets[0].location.path == (
        "songs/20260415_shared-session-host/projects/main-session"
    )


def test_two_songs_can_share_the_same_default_project_asset(
    load_manifest: Callable[[str], dict],
) -> None:
    first_data = load_manifest("song.json")
    second_data = load_manifest("song.json")
    second_data["id"] = "song_225aa914-22bd-4e35-b12d-66b145a090b2"
    second_data["title"] = "Connected Tune"

    first = SongManifest.model_validate(first_data)
    second = SongManifest.model_validate(second_data)

    assert first.default_project_id == second.default_project_id
    assert first.assets[0].id == second.assets[0].id
    assert first.assets[0].location == second.assets[0].location


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


@pytest.mark.parametrize(
    "prefix",
    ["song", "album", "asset", "entry", "sequence", "collection"],
)
def test_prefixed_uuid_helper_accepts_canonical_uuid4(prefix: str) -> None:
    value = f"{prefix}_{UUID4}"

    assert validate_prefixed_uuid(value, prefix) == value


@pytest.mark.parametrize(
    ("value", "prefix", "message"),
    [
        (f"album_{UUID4}", "song", "expected song UUID"),
        ("song_not-a-uuid", "song", "valid UUID"),
        (f"song_{UUID1}", "song", "UUIDv4"),
        (f"song_{UUID4.upper()}", "song", "canonical lowercase"),
    ],
)
def test_prefixed_uuid_helper_rejects_invalid_values(
    value: str,
    prefix: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_prefixed_uuid(value, prefix)


@pytest.mark.parametrize(
    ("model", "data"),
    [
        (
            Asset,
            {
                "id": f"asset_{UUID4}",
                "kind": "project",
                "purpose": "song_session",
                "title": "Session",
                "location": {
                    "storage_id": f"storage_{UUID4}",
                    "path": "songs/example/projects/session",
                },
            },
        ),
        (
            Entry,
            {
                "id": f"entry_{UUID4}",
                "song_id": f"song_{UUID4}",
            },
        ),
        (
            Sequence,
            {
                "id": f"sequence_{UUID4}",
                "title": "Main sequence",
                "entries": [],
            },
        ),
        (
            Collection,
            {
                "id": f"collection_{UUID4}",
                "title": "Bonus material",
                "entries": [],
            },
        ),
    ],
)
def test_nested_models_accept_correct_id_prefixes(
    model: type[Asset] | type[Entry] | type[Sequence] | type[Collection],
    data: dict,
) -> None:
    assert model.model_validate(data).id == data["id"]


@pytest.mark.parametrize(
    ("model", "data"),
    [
        (
            Asset,
            {
                "id": f"song_{UUID4}",
                "kind": "project",
                "purpose": "song_session",
                "title": "Session",
                "location": {
                    "storage_id": f"storage_{UUID4}",
                    "path": "songs/example/projects/session",
                },
            },
        ),
        (
            Entry,
            {
                "id": f"song_{UUID4}",
                "song_id": f"song_{UUID4}",
            },
        ),
        (
            Sequence,
            {
                "id": f"collection_{UUID4}",
                "title": "Main sequence",
                "entries": [],
            },
        ),
        (
            Collection,
            {
                "id": f"sequence_{UUID4}",
                "title": "Bonus material",
                "entries": [],
            },
        ),
    ],
)
def test_nested_models_reject_wrong_id_prefixes_on_id_field(
    model: type[Asset] | type[Entry] | type[Sequence] | type[Collection],
    data: dict,
) -> None:
    with pytest.raises(ValidationError) as error:
        model.model_validate(data)

    assert ("id",) in _error_locations(error.value)


def test_entry_accepts_song_prefixed_song_reference() -> None:
    entry = Entry.model_validate(
        {
            "id": f"entry_{UUID4}",
            "song_id": f"song_{UUID4}",
        }
    )

    assert entry.song_id == f"song_{UUID4}"


def test_entry_rejects_non_song_prefix_on_song_reference() -> None:
    with pytest.raises(ValidationError) as error:
        Entry.model_validate(
            {
                "id": f"entry_{UUID4}",
                "song_id": f"entry_{UUID4}",
            }
        )

    assert ("song_id",) in _error_locations(error.value)


@pytest.mark.parametrize(
    "invalid_id",
    [
        "album_2f8c2a4e-8bd2-4d57-a1c7-7e4cbfd52a91",
        "song_not-a-uuid",
    ],
)
def test_song_rejects_invalid_id(
    invalid_id: str,
    load_manifest: Callable[[str], dict],
) -> None:
    data = load_manifest("song.json")
    data["id"] = invalid_id

    with pytest.raises(ValidationError):
        SongManifest.model_validate(data)


def test_album_rejects_wrong_id_prefix(
    load_manifest: Callable[[str], dict],
) -> None:
    data = load_manifest("album.json")
    data["id"] = f"song_{UUID4}"

    with pytest.raises(ValidationError) as error:
        AlbumManifest.model_validate(data)

    assert ("id",) in _error_locations(error.value)


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


def test_asset_rejects_non_storage_id_in_location(
    load_manifest: Callable[[str], dict],
) -> None:
    data = load_manifest("song.json")
    data["assets"][0]["location"]["storage_id"] = f"song_{UUID4}"

    with pytest.raises(ValidationError) as error:
        SongManifest.model_validate(data)

    assert ("assets", 0, "location", "storage_id") in _error_locations(error.value)


@pytest.mark.parametrize(
    "path",
    [
        "/Volumes/Studio SSD/songs/example/projects/session",
        "../outside/projects/session",
        "songs/example/../../outside",
    ],
)
def test_asset_location_rejects_absolute_or_escaping_path(
    path: str,
    load_manifest: Callable[[str], dict],
) -> None:
    data = load_manifest("song.json")
    data["assets"][0]["location"]["path"] = path

    with pytest.raises(ValidationError) as error:
        SongManifest.model_validate(data)

    assert ("assets", 0, "location", "path") in _error_locations(error.value)


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


def test_album_allows_entries_to_share_album_session(
    load_manifest: Callable[[str], dict],
) -> None:
    album = AlbumManifest.model_validate(load_manifest("album.json"))

    entries = album.sequences[0].entries
    assert entries[0].album_asset_id is not None
    assert entries[0].album_asset_id == entries[1].album_asset_id
    assert entries[0].album_asset_id == album.assets[0].id


def test_album_rejects_missing_album_asset_reference(
    load_manifest: Callable[[str], dict],
) -> None:
    data = load_manifest("album.json")
    data["sequences"][0]["entries"][0]["album_asset_id"] = (
        "asset_2f8c2a4e-8bd2-4d57-a1c7-7e4cbfd52a91"
    )

    with pytest.raises(
        ValidationError,
        match="album_asset_id must reference an asset in this album",
    ):
        AlbumManifest.model_validate(data)


def test_album_asset_reference_must_be_project(
    load_manifest: Callable[[str], dict],
) -> None:
    data = load_manifest("album.json")
    data["assets"][0]["kind"] = "audio"

    with pytest.raises(
        ValidationError,
        match="album_asset_id must reference a project asset",
    ):
        AlbumManifest.model_validate(data)


def test_album_asset_reference_must_be_album_session(
    load_manifest: Callable[[str], dict],
) -> None:
    data = load_manifest("album.json")
    data["assets"][0]["purpose"] = "song_session"

    with pytest.raises(
        ValidationError,
        match="album_asset_id must reference an album session",
    ):
        AlbumManifest.model_validate(data)


def test_collection_album_asset_reference_is_also_validated(
    load_manifest: Callable[[str], dict],
) -> None:
    data = load_manifest("album.json")
    data["collections"][0]["entries"][0]["album_asset_id"] = (
        "asset_2f8c2a4e-8bd2-4d57-a1c7-7e4cbfd52a91"
    )

    with pytest.raises(
        ValidationError,
        match="album_asset_id must reference an asset in this album",
    ):
        AlbumManifest.model_validate(data)
