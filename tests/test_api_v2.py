"""Test the MVP version-2 song and album APIs through JSON storage.

These tests verify an empty library, song creation, portable metadata written
to disk, stable IDs across later list requests, and HTTP conflict handling for
duplicate directories. They also verify registering one shared album session,
persisting it, adding songs at requested track positions, and reporting
unknown album, song, sequence, and entry IDs. Track mutation tests also verify
reordering and removal through HTTP without losing persistence. Song-project
tests cover registration, default selection, persistence, and HTTP errors.
Song retrieval tests cover successful lookup, unknown IDs, and persisted
project information returned by a later request.
Metadata PATCH tests cover partial edits, explicit null clearing, persistence,
invalid project references, and unknown entity IDs.

Authored by OpenAI Codex on 2026-08-25.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from domain.manifests import AlbumManifest, SongManifest, StorageManifest
from persistence.manifests import load_album_manifest, load_song_manifest
from persistence.storage import STORAGE_FILENAME, load_storage_manifest


def test_v2_song_list_starts_empty(api_client: TestClient) -> None:
    response = api_client.get("/v2/songs")

    assert response.status_code == 200
    assert response.json() == []


def test_v2_create_song_returns_manifest_and_writes_metadata(
    api_client: TestClient,
    music_root: Path,
) -> None:
    response = api_client.post("/v2/songs", json={"title": "API Song"})

    assert response.status_code == 201
    body = response.json()
    manifest = SongManifest.model_validate(body)
    assert manifest.title == "API Song"
    assert manifest.id.startswith("song_")

    song_directories = list((music_root / "songs").iterdir())
    assert len(song_directories) == 1
    assert load_song_manifest(song_directories[0]) == manifest


def test_v2_song_id_is_stable_across_requests(api_client: TestClient) -> None:
    create_response = api_client.post(
        "/v2/songs",
        json={"title": "Persistent Song"},
    )
    assert create_response.status_code == 201
    created = create_response.json()

    list_response = api_client.get("/v2/songs")

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["id"] == created["id"]
    assert list_response.json()[0]["title"] == "Persistent Song"


def test_v2_get_song_returns_created_manifest(api_client: TestClient) -> None:
    created = api_client.post("/v2/songs", json={"title": "Fetched Song"}).json()

    response = api_client.get(f"/v2/songs/{created['id']}")

    assert response.status_code == 200
    assert SongManifest.model_validate(response.json()) == SongManifest.model_validate(
        created
    )


def test_v2_get_song_returns_404_for_unknown_song(api_client: TestClient) -> None:
    response = api_client.get(
        "/v2/songs/song_00000000-0000-4000-8000-000000000000"
    )

    assert response.status_code == 404
    assert "Song not found" in response.json()["detail"]


def test_v2_get_song_includes_persisted_project(
    api_client: TestClient,
    music_root: Path,
) -> None:
    song = api_client.post("/v2/songs", json={"title": "Persistent Project"}).json()
    song_root = next((music_root / "songs").iterdir())
    (song_root / "projects" / "shared-session.rpp").write_text(
        "REAPER_PROJECT",
        encoding="utf-8",
    )
    registered = api_client.post(
        f"/v2/songs/{song['id']}/projects",
        json={
            "title": "Shared Session",
            "relative_path": "projects/shared-session.rpp",
        },
    )
    assert registered.status_code == 201

    response = api_client.get(f"/v2/songs/{song['id']}")

    assert response.status_code == 200
    fetched = SongManifest.model_validate(response.json())
    assert fetched.assets == SongManifest.model_validate(registered.json()).assets
    assert fetched.default_project_id == fetched.assets[0].id


def test_v2_patch_song_updates_metadata_and_persists(
    api_client: TestClient,
    music_root: Path,
) -> None:
    song = api_client.post("/v2/songs", json={"title": "Original API Song"}).json()
    song_root = next((music_root / "songs").iterdir())

    response = api_client.patch(
        f"/v2/songs/{song['id']}",
        json={
            "title": "Updated API Song",
            "description": "Updated through HTTP",
            "tags": ["api", "edited"],
        },
    )

    assert response.status_code == 200
    updated = SongManifest.model_validate(response.json())
    assert updated.title == "Updated API Song"
    assert updated.description == "Updated through HTTP"
    assert updated.tags == ["api", "edited"]
    assert song_root.name.endswith("Original API Song")
    assert load_song_manifest(song_root) == updated


def test_v2_patch_song_can_clear_description_and_default_project(
    api_client: TestClient,
    music_root: Path,
) -> None:
    song = api_client.post("/v2/songs", json={"title": "Clearable API Song"}).json()
    song_root = next((music_root / "songs").iterdir())
    (song_root / "projects" / "default.rpp").write_text(
        "REAPER_PROJECT",
        encoding="utf-8",
    )
    registered = api_client.post(
        f"/v2/songs/{song['id']}/projects",
        json={"title": "Default", "relative_path": "projects/default.rpp"},
    )
    assert registered.status_code == 201
    described = api_client.patch(
        f"/v2/songs/{song['id']}",
        json={"description": "Temporary"},
    )
    assert described.status_code == 200

    response = api_client.patch(
        f"/v2/songs/{song['id']}",
        json={"description": None, "default_project_id": None},
    )

    assert response.status_code == 200
    updated = SongManifest.model_validate(response.json())
    assert updated.description is None
    assert updated.default_project_id is None
    assert len(updated.assets) == 1
    assert load_song_manifest(song_root) == updated


def test_v2_patch_song_returns_400_for_unknown_default_project(
    api_client: TestClient,
) -> None:
    song = api_client.post("/v2/songs", json={"title": "Invalid Default API"}).json()

    response = api_client.patch(
        f"/v2/songs/{song['id']}",
        json={"default_project_id": "asset_00000000-0000-4000-8000-000000000000"},
    )

    assert response.status_code == 400
    assert "must reference an asset" in response.json()["detail"]


def test_v2_patch_song_returns_404_for_unknown_song(api_client: TestClient) -> None:
    response = api_client.patch(
        "/v2/songs/song_00000000-0000-4000-8000-000000000000",
        json={"title": "Missing"},
    )

    assert response.status_code == 404
    assert "Song not found" in response.json()["detail"]


def test_v2_duplicate_song_returns_conflict(api_client: TestClient) -> None:
    first_response = api_client.post(
        "/v2/songs",
        json={"title": "Duplicate Song"},
    )
    assert first_response.status_code == 201

    duplicate_response = api_client.post(
        "/v2/songs",
        json={"title": "Duplicate Song"},
    )

    assert duplicate_response.status_code == 409
    assert "Song already exists" in duplicate_response.json()["detail"]


def test_v2_create_song_rejects_unusable_directory_title(
    api_client: TestClient,
) -> None:
    response = api_client.post("/v2/songs", json={"title": "/\\:*?"})

    assert response.status_code == 400
    assert "usable filename characters" in response.json()["detail"]


def test_v2_album_list_starts_empty(api_client: TestClient) -> None:
    response = api_client.get("/v2/albums")

    assert response.status_code == 200
    assert response.json() == []


def test_v2_create_album_preserves_song_order_and_writes_metadata(
    api_client: TestClient,
    music_root: Path,
) -> None:
    first_song = api_client.post("/v2/songs", json={"title": "First Song"}).json()
    second_song = api_client.post("/v2/songs", json={"title": "Second Song"}).json()
    song_ids = [first_song["id"], second_song["id"]]

    response = api_client.post(
        "/v2/albums",
        json={"title": "Connected Album", "song_ids": song_ids},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Connected Album"
    assert body["primary_sequence_id"] == body["sequences"][0]["id"]
    assert [entry["song_id"] for entry in body["sequences"][0]["entries"]] == song_ids

    album_directories = list((music_root / "albums").iterdir())
    assert len(album_directories) == 1
    assert load_album_manifest(album_directories[0]).id == body["id"]


def test_v2_create_album_returns_404_for_unknown_song(
    api_client: TestClient,
    music_root: Path,
) -> None:
    response = api_client.post(
        "/v2/albums",
        json={
            "title": "Invalid API Album",
            "song_ids": ["song_00000000-0000-4000-8000-000000000000"],
        },
    )

    assert response.status_code == 404
    assert "Songs not found" in response.json()["detail"]
    assert list((music_root / "albums").iterdir()) == []


def test_v2_album_id_is_stable_across_requests(api_client: TestClient) -> None:
    create_response = api_client.post(
        "/v2/albums",
        json={"title": "Persistent Album", "song_ids": []},
    )
    assert create_response.status_code == 201
    created = create_response.json()

    list_response = api_client.get("/v2/albums")

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["id"] == created["id"]
    assert list_response.json()[0]["title"] == "Persistent Album"


def test_v2_get_album_returns_created_manifest(api_client: TestClient) -> None:
    created = api_client.post(
        "/v2/albums",
        json={"title": "Fetched Album", "song_ids": []},
    ).json()

    response = api_client.get(f"/v2/albums/{created['id']}")

    assert response.status_code == 200
    assert AlbumManifest.model_validate(response.json()) == AlbumManifest.model_validate(
        created
    )


def test_v2_get_album_returns_404_for_unknown_album(api_client: TestClient) -> None:
    response = api_client.get(
        "/v2/albums/album_00000000-0000-4000-8000-000000000000"
    )

    assert response.status_code == 404
    assert "Album not found" in response.json()["detail"]


def test_v2_patch_album_updates_metadata_and_persists(
    api_client: TestClient,
    music_root: Path,
) -> None:
    album = api_client.post(
        "/v2/albums",
        json={"title": "Original API Album", "song_ids": []},
    ).json()
    album_root = next((music_root / "albums").iterdir())

    response = api_client.patch(
        f"/v2/albums/{album['id']}",
        json={
            "title": "Updated API Album",
            "description": "Updated album description",
            "tags": ["api", "album"],
        },
    )

    assert response.status_code == 200
    updated = AlbumManifest.model_validate(response.json())
    assert updated.title == "Updated API Album"
    assert updated.description == "Updated album description"
    assert updated.tags == ["api", "album"]
    assert album_root.name.endswith("Original API Album")
    assert load_album_manifest(album_root) == updated


def test_v2_patch_album_can_clear_description(api_client: TestClient) -> None:
    album = api_client.post(
        "/v2/albums",
        json={"title": "Clearable API Album", "song_ids": []},
    ).json()
    described = api_client.patch(
        f"/v2/albums/{album['id']}",
        json={"description": "Temporary"},
    )
    assert described.status_code == 200

    response = api_client.patch(
        f"/v2/albums/{album['id']}",
        json={"description": None},
    )

    assert response.status_code == 200
    assert response.json()["description"] is None


def test_v2_patch_album_returns_404_for_unknown_album(api_client: TestClient) -> None:
    response = api_client.patch(
        "/v2/albums/album_00000000-0000-4000-8000-000000000000",
        json={"title": "Missing"},
    )

    assert response.status_code == 404
    assert "Album not found" in response.json()["detail"]


def test_v2_duplicate_album_returns_conflict(api_client: TestClient) -> None:
    first_response = api_client.post(
        "/v2/albums",
        json={"title": "Duplicate Album", "song_ids": []},
    )
    assert first_response.status_code == 201

    duplicate_response = api_client.post(
        "/v2/albums",
        json={"title": "Duplicate Album", "song_ids": []},
    )

    assert duplicate_response.status_code == 409
    assert "Album already exists" in duplicate_response.json()["detail"]


def test_v2_create_album_rejects_unusable_directory_title(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        "/v2/albums",
        json={"title": "/\\:*?", "song_ids": []},
    )

    assert response.status_code == 400
    assert "usable filename characters" in response.json()["detail"]


def test_v2_register_album_session_shares_asset_across_entries(
    api_client: TestClient,
    music_root: Path,
) -> None:
    first_song = api_client.post("/v2/songs", json={"title": "Part One"}).json()
    second_song = api_client.post("/v2/songs", json={"title": "Part Two"}).json()
    album = api_client.post(
        "/v2/albums",
        json={
            "title": "Continuous Album",
            "song_ids": [first_song["id"], second_song["id"]],
        },
    ).json()
    entry_ids = [entry["id"] for entry in album["sequences"][0]["entries"]]
    album_root = next((music_root / "albums").iterdir())
    (album_root / "projects" / "continuous-album.rpp").touch()

    response = api_client.post(
        f"/v2/albums/{album['id']}/sessions",
        json={
            "title": "Continuous Reaper Session",
            "relative_path": "projects/continuous-album.rpp",
            "entry_ids": entry_ids,
        },
    )

    assert response.status_code == 201
    updated = response.json()
    assert len(updated["assets"]) == 1
    session = updated["assets"][0]
    assert session["kind"] == "project"
    assert session["purpose"] == "album_session"
    storage = load_storage_manifest(music_root)
    assert session["location"]["storage_id"] == storage.id
    assert session["location"]["path"] == (
        album_root.relative_to(music_root) / "projects/continuous-album.rpp"
    ).as_posix()
    assert {
        entry["album_asset_id"]
        for entry in updated["sequences"][0]["entries"]
    } == {session["id"]}


def test_v2_register_album_session_defaults_to_primary_sequence(
    api_client: TestClient,
    music_root: Path,
) -> None:
    first_song = api_client.post("/v2/songs", json={"title": "First Part"}).json()
    second_song = api_client.post("/v2/songs", json={"title": "Second Part"}).json()
    album = api_client.post(
        "/v2/albums",
        json={
            "title": "Default Session Album",
            "song_ids": [first_song["id"], second_song["id"]],
        },
    ).json()
    album_root = next((music_root / "albums").iterdir())
    (album_root / "projects" / "connected.rpp").touch()

    response = api_client.post(
        f"/v2/albums/{album['id']}/sessions",
        json={
            "title": "Connected Session",
            "relative_path": "projects/connected.rpp",
        },
    )

    assert response.status_code == 201
    updated = response.json()
    session_id = updated["assets"][0]["id"]
    assert {
        entry["album_asset_id"]
        for entry in updated["sequences"][0]["entries"]
    } == {session_id}


def test_v2_registered_album_session_is_persisted(
    api_client: TestClient,
    music_root: Path,
) -> None:
    album = api_client.post(
        "/v2/albums",
        json={"title": "Persistent Session Album", "song_ids": []},
    ).json()
    album_root = next((music_root / "albums").iterdir())
    (album_root / "projects" / "album-wide.rpp").touch()

    response = api_client.post(
        f"/v2/albums/{album['id']}/sessions",
        json={
            "title": "Album-Wide Session",
            "relative_path": "projects/album-wide.rpp",
            "entry_ids": [],
        },
    )
    assert response.status_code == 201
    returned = AlbumManifest.model_validate(response.json())

    assert load_album_manifest(album_root) == returned

    get_response = api_client.get(f"/v2/albums/{album['id']}")
    assert get_response.status_code == 200
    assert AlbumManifest.model_validate(get_response.json()) == returned


def test_v2_register_album_session_returns_404_for_unknown_album(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        "/v2/albums/album_00000000-0000-4000-8000-000000000000/sessions",
        json={
            "title": "Missing Session",
            "relative_path": "projects/missing.rpp",
            "entry_ids": [],
        },
    )

    assert response.status_code == 404
    assert "Album not found" in response.json()["detail"]


def test_v2_register_album_session_returns_400_for_unknown_entry(
    api_client: TestClient,
) -> None:
    album = api_client.post(
        "/v2/albums",
        json={"title": "Entry Error Album", "song_ids": []},
    ).json()

    response = api_client.post(
        f"/v2/albums/{album['id']}/sessions",
        json={
            "title": "Invalid Session",
            "relative_path": "projects/invalid.rpp",
            "entry_ids": ["entry_00000000-0000-4000-8000-000000000000"],
        },
    )

    assert response.status_code == 400
    assert "Missing entry ids" in response.json()["detail"]

    persisted_album = api_client.get("/v2/albums").json()[0]
    assert persisted_album["assets"] == []


def test_v2_add_album_entry_inserts_song_and_persists(
    api_client: TestClient,
    music_root: Path,
) -> None:
    first_song = api_client.post("/v2/songs", json={"title": "First Track"}).json()
    added_song = api_client.post("/v2/songs", json={"title": "New Opener"}).json()
    album = api_client.post(
        "/v2/albums",
        json={"title": "Editable Album", "song_ids": [first_song["id"]]},
    ).json()

    response = api_client.post(
        f"/v2/albums/{album['id']}/entries",
        json={"song_id": added_song["id"], "position": 0},
    )

    assert response.status_code == 201
    updated = AlbumManifest.model_validate(response.json())
    assert [entry.song_id for entry in updated.sequences[0].entries] == [
        added_song["id"],
        first_song["id"],
    ]
    album_root = next((music_root / "albums").iterdir())
    assert load_album_manifest(album_root) == updated


def test_v2_add_album_entry_accepts_explicit_primary_sequence(
    api_client: TestClient,
) -> None:
    song = api_client.post("/v2/songs", json={"title": "Explicit Track"}).json()
    album = api_client.post(
        "/v2/albums",
        json={"title": "Explicit Sequence Album", "song_ids": []},
    ).json()

    response = api_client.post(
        f"/v2/albums/{album['id']}/entries",
        json={
            "song_id": song["id"],
            "sequence_id": album["primary_sequence_id"],
        },
    )

    assert response.status_code == 201
    assert response.json()["sequences"][0]["entries"][0]["song_id"] == song["id"]


def test_v2_add_album_entry_returns_404_for_unknown_song(
    api_client: TestClient,
) -> None:
    album = api_client.post(
        "/v2/albums",
        json={"title": "Missing Song Album", "song_ids": []},
    ).json()

    response = api_client.post(
        f"/v2/albums/{album['id']}/entries",
        json={"song_id": "song_00000000-0000-4000-8000-000000000000"},
    )

    assert response.status_code == 404
    assert "Song not found" in response.json()["detail"]


def test_v2_add_album_entry_returns_404_for_unknown_sequence(
    api_client: TestClient,
) -> None:
    song = api_client.post("/v2/songs", json={"title": "Known Track"}).json()
    album = api_client.post(
        "/v2/albums",
        json={"title": "Missing Sequence Album", "song_ids": []},
    ).json()

    response = api_client.post(
        f"/v2/albums/{album['id']}/entries",
        json={
            "song_id": song["id"],
            "sequence_id": "sequence_00000000-0000-4000-8000-000000000000",
        },
    )

    assert response.status_code == 404
    assert "Sequence not found" in response.json()["detail"]


def test_v2_add_album_entry_returns_400_for_invalid_position(
    api_client: TestClient,
) -> None:
    song = api_client.post("/v2/songs", json={"title": "Position Track"}).json()
    album = api_client.post(
        "/v2/albums",
        json={"title": "Position Error Album", "song_ids": []},
    ).json()

    response = api_client.post(
        f"/v2/albums/{album['id']}/entries",
        json={"song_id": song["id"], "position": 1},
    )

    assert response.status_code == 400
    assert "Position out of range" in response.json()["detail"]
    assert api_client.get("/v2/albums").json()[0]["sequences"][0]["entries"] == []


def test_v2_reorder_album_entry_moves_track_and_persists(
    api_client: TestClient,
    music_root: Path,
) -> None:
    first = api_client.post("/v2/songs", json={"title": "Original Opener"}).json()
    second = api_client.post("/v2/songs", json={"title": "Original Closer"}).json()
    album = api_client.post(
        "/v2/albums",
        json={"title": "Reorder API Album", "song_ids": [first["id"], second["id"]]},
    ).json()
    first_entry_id = album["sequences"][0]["entries"][0]["id"]

    response = api_client.patch(
        f"/v2/albums/{album['id']}/entries/{first_entry_id}",
        json={"position": 1},
    )

    assert response.status_code == 200
    updated = AlbumManifest.model_validate(response.json())
    assert [entry.song_id for entry in updated.sequences[0].entries] == [
        second["id"],
        first["id"],
    ]
    album_root = next((music_root / "albums").iterdir())
    assert load_album_manifest(album_root) == updated


def test_v2_remove_album_entry_removes_track_and_persists(
    api_client: TestClient,
    music_root: Path,
) -> None:
    first = api_client.post("/v2/songs", json={"title": "Kept Track"}).json()
    second = api_client.post("/v2/songs", json={"title": "Removed Track"}).json()
    album = api_client.post(
        "/v2/albums",
        json={"title": "Remove API Album", "song_ids": [first["id"], second["id"]]},
    ).json()
    removed_entry_id = album["sequences"][0]["entries"][1]["id"]

    response = api_client.delete(
        f"/v2/albums/{album['id']}/entries/{removed_entry_id}"
    )

    assert response.status_code == 200
    updated = AlbumManifest.model_validate(response.json())
    assert [entry.song_id for entry in updated.sequences[0].entries] == [first["id"]]
    album_root = next((music_root / "albums").iterdir())
    assert load_album_manifest(album_root) == updated


def test_v2_reorder_album_entry_returns_400_for_invalid_position(
    api_client: TestClient,
) -> None:
    song = api_client.post("/v2/songs", json={"title": "Only Track"}).json()
    album = api_client.post(
        "/v2/albums",
        json={"title": "Bad Reorder Album", "song_ids": [song["id"]]},
    ).json()
    entry_id = album["sequences"][0]["entries"][0]["id"]

    response = api_client.patch(
        f"/v2/albums/{album['id']}/entries/{entry_id}",
        json={"position": 1},
    )

    assert response.status_code == 400
    assert "Invalid position" in response.json()["detail"]


def test_v2_reorder_album_entry_returns_404_for_unknown_entry(
    api_client: TestClient,
) -> None:
    album = api_client.post(
        "/v2/albums",
        json={"title": "Unknown Reorder Entry Album", "song_ids": []},
    ).json()

    response = api_client.patch(
        f"/v2/albums/{album['id']}/entries/entry_00000000-0000-4000-8000-000000000000",
        json={"position": 0},
    )

    assert response.status_code == 404
    assert "Entry not found" in response.json()["detail"]


def test_v2_remove_album_entry_returns_404_for_unknown_entry(
    api_client: TestClient,
) -> None:
    album = api_client.post(
        "/v2/albums",
        json={"title": "Unknown Removal Entry Album", "song_ids": []},
    ).json()

    response = api_client.delete(
        f"/v2/albums/{album['id']}/entries/entry_00000000-0000-4000-8000-000000000000"
    )

    assert response.status_code == 404
    assert "Entry not found" in response.json()["detail"]


def test_v2_initialize_storage_returns_manifest_and_persists(
    api_client: TestClient,
    music_root: Path,
) -> None:
    (music_root / STORAGE_FILENAME).unlink()

    response = api_client.post(
        "/v2/storage",
        json={"name": "API Music Library"},
    )

    assert response.status_code == 201
    returned = StorageManifest.model_validate(response.json())
    assert returned.name == "API Music Library"
    assert load_storage_manifest(music_root) == returned


def test_v2_initialize_storage_returns_conflict_when_already_initialized(
    api_client: TestClient,
    music_root: Path,
) -> None:
    original = load_storage_manifest(music_root)

    response = api_client.post(
        "/v2/storage",
        json={"name": "Replacement Library"},
    )

    assert response.status_code == 409
    assert "already initialized" in response.json()["detail"]
    assert load_storage_manifest(music_root) == original


def test_v2_get_storage_returns_current_identity(
    api_client: TestClient,
    music_root: Path,
) -> None:
    expected = load_storage_manifest(music_root)

    response = api_client.get("/v2/storage")

    assert response.status_code == 200
    assert StorageManifest.model_validate(response.json()) == expected


def test_v2_get_storage_returns_404_when_not_initialized(
    api_client: TestClient,
    music_root: Path,
) -> None:
    (music_root / STORAGE_FILENAME).unlink()

    response = api_client.get("/v2/storage")

    assert response.status_code == 404
    assert "Storage not initialized" in response.json()["detail"]


def test_v2_register_song_project_creates_default_asset_and_persists(
    api_client: TestClient,
    music_root: Path,
) -> None:
    song = api_client.post("/v2/songs", json={"title": "Project API Song"}).json()
    song_root = next((music_root / "songs").iterdir())
    (song_root / "projects" / "main-session.rpp").write_text(
        "REAPER_PROJECT",
        encoding="utf-8",
    )

    response = api_client.post(
        f"/v2/songs/{song['id']}/projects",
        json={
            "title": "Main Session",
            "relative_path": "projects/main-session.rpp",
        },
    )

    assert response.status_code == 201
    updated = SongManifest.model_validate(response.json())
    assert len(updated.assets) == 1
    assert updated.default_project_id == updated.assets[0].id
    assert load_song_manifest(song_root) == updated


def test_v2_register_song_project_can_skip_default_selection(
    api_client: TestClient,
    music_root: Path,
) -> None:
    song = api_client.post("/v2/songs", json={"title": "Alternate API Song"}).json()
    song_root = next((music_root / "songs").iterdir())
    (song_root / "projects" / "alternate.rpp").write_text(
        "REAPER_PROJECT",
        encoding="utf-8",
    )

    response = api_client.post(
        f"/v2/songs/{song['id']}/projects",
        json={
            "title": "Alternate Session",
            "relative_path": "projects/alternate.rpp",
            "make_default": False,
        },
    )

    assert response.status_code == 201
    assert response.json()["default_project_id"] is None


def test_v2_register_song_project_shares_parent_asset(
    api_client: TestClient,
    music_root: Path,
) -> None:
    parent = api_client.post("/v2/songs", json={"title": "API Parent"}).json()
    target = api_client.post("/v2/songs", json={"title": "API Target"}).json()
    parent_root = next(
        path
        for path in (music_root / "songs").iterdir()
        if load_song_manifest(path).id == parent["id"]
    )
    (parent_root / "projects" / "shared.rpp").write_text(
        "REAPER_PROJECT",
        encoding="utf-8",
    )
    parent_response = api_client.post(
        f"/v2/songs/{parent['id']}/projects",
        json={
            "title": "Shared API Session",
            "relative_path": "projects/shared.rpp",
        },
    )
    assert parent_response.status_code == 201
    parent_asset = parent_response.json()["assets"][0]

    response = api_client.post(
        f"/v2/songs/{target['id']}/projects",
        json={
            "title": "Shared API Session",
            "relative_path": "projects/shared.rpp",
            "parent_song": parent["id"],
        },
    )

    assert response.status_code == 201
    assert response.json()["assets"] == [parent_asset]
    assert response.json()["default_project_id"] == parent_asset["id"]


def test_v2_register_song_project_returns_404_for_unknown_song(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        "/v2/songs/song_00000000-0000-4000-8000-000000000000/projects",
        json={
            "title": "Missing Song Session",
            "relative_path": "projects/missing.rpp",
        },
    )

    assert response.status_code == 404
    assert "Song not found" in response.json()["detail"]


def test_v2_register_song_project_returns_404_for_missing_project(
    api_client: TestClient,
) -> None:
    song = api_client.post("/v2/songs", json={"title": "Missing Project API Song"}).json()

    response = api_client.post(
        f"/v2/songs/{song['id']}/projects",
        json={
            "title": "Missing Session",
            "relative_path": "projects/missing.rpp",
        },
    )

    assert response.status_code == 404
    assert "Project not found" in response.json()["detail"]


def test_v2_register_song_project_returns_400_for_escaping_path(
    api_client: TestClient,
    music_root: Path,
) -> None:
    song = api_client.post("/v2/songs", json={"title": "Safe API Song"}).json()
    (music_root / "outside.rpp").write_text("OUTSIDE", encoding="utf-8")

    response = api_client.post(
        f"/v2/songs/{song['id']}/projects",
        json={
            "title": "Outside Session",
            "relative_path": "../../outside.rpp",
        },
    )

    assert response.status_code == 400
    assert "must not escape storage" in response.json()["detail"]


def test_v2_assign_album_session_to_song_sets_default_and_persists(
    api_client: TestClient,
    music_root: Path,
) -> None:
    song = api_client.post("/v2/songs", json={"title": "Connected Track"}).json()
    album = api_client.post(
        "/v2/albums",
        json={"title": "Connected Record", "song_ids": [song["id"]]},
    ).json()
    album_root = next((music_root / "albums").iterdir())
    (album_root / "projects" / "connected.rpp").touch()
    album_session = api_client.post(
        f"/v2/albums/{album['id']}/sessions",
        json={
            "title": "Connected Session",
            "relative_path": "projects/connected.rpp",
        },
    ).json()["assets"][0]

    response = api_client.post(
        f"/v2/songs/{song['id']}/album-sessions",
        json={"asset_id": album_session["id"]},
    )

    assert response.status_code == 201
    updated = SongManifest.model_validate(response.json())
    assert updated.assets[0].model_dump(mode="json") == album_session
    assert updated.default_project_id == album_session["id"]
    song_root = next((music_root / "songs").iterdir())
    assert load_song_manifest(song_root) == updated


def test_v2_assign_album_session_to_song_can_skip_default_selection(
    api_client: TestClient,
    music_root: Path,
) -> None:
    song = api_client.post("/v2/songs", json={"title": "Optional Track"}).json()
    album = api_client.post(
        "/v2/albums",
        json={"title": "Optional Record", "song_ids": [song["id"]]},
    ).json()
    album_root = next((music_root / "albums").iterdir())
    (album_root / "projects" / "optional.rpp").touch()
    album_session = api_client.post(
        f"/v2/albums/{album['id']}/sessions",
        json={
            "title": "Optional Session",
            "relative_path": "projects/optional.rpp",
        },
    ).json()["assets"][0]

    response = api_client.post(
        f"/v2/songs/{song['id']}/album-sessions",
        json={"asset_id": album_session["id"], "make_default": False},
    )

    assert response.status_code == 201
    assert response.json()["assets"] == [album_session]
    assert response.json()["default_project_id"] is None


def test_v2_assign_album_session_to_song_returns_404_for_unknown_asset(
    api_client: TestClient,
) -> None:
    song = api_client.post("/v2/songs", json={"title": "Missing Session"}).json()

    response = api_client.post(
        f"/v2/songs/{song['id']}/album-sessions",
        json={"asset_id": "asset_00000000-0000-4000-8000-000000000000"},
    )

    assert response.status_code == 404
    assert "Album session not found" in response.json()["detail"]


def test_v2_assign_album_session_to_song_returns_404_for_unknown_song(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        "/v2/songs/song_00000000-0000-4000-8000-000000000000/album-sessions",
        json={"asset_id": "asset_00000000-0000-4000-8000-000000000000"},
    )

    assert response.status_code == 404
    assert "Song not found" in response.json()["detail"]


def test_v2_project_templates_lists_usable_templates_without_paths(
    api_client: TestClient,
) -> None:
    response = api_client.get("/v2/project-templates")

    assert response.status_code == 200
    assert response.json() == [
        {
            "name": "Reaper",
            "extension": ".RPP",
            "layout": "single_file",
        },
        {
            "name": "Ableton",
            "extension": ".als",
            "layout": "nested_folder",
        },
    ]
    assert all(
        set(template) == {"name", "extension", "layout"}
        for template in response.json()
    )


def test_v2_project_templates_omits_missing_and_extensionless_templates(
    api_client: TestClient,
    config_path: Path,
    tmp_path: Path,
) -> None:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    extensionless_template = tmp_path / "templates" / "extensionless"
    extensionless_template.touch()
    config["templates"] = {
        "Missing": {
            "path": str(tmp_path / "templates" / "missing.RPP"),
            "folder": False,
        },
        "Extensionless": {
            "path": str(extensionless_template),
            "folder": False,
        },
        "Reaper": config["templates"]["Reaper"],
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    response = api_client.get("/v2/project-templates")

    assert response.status_code == 200
    assert response.json() == [
        {
            "name": "Reaper",
            "extension": ".RPP",
            "layout": "single_file",
        }
    ]


def test_v2_project_templates_returns_empty_list_without_templates(
    api_client: TestClient,
    config_path: Path,
) -> None:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["templates"] = {}
    config_path.write_text(json.dumps(config), encoding="utf-8")

    response = api_client.get("/v2/project-templates")

    assert response.status_code == 200
    assert response.json() == []


def test_v2_create_song_project_from_file_template_uses_song_title(
    api_client: TestClient,
    music_root: Path,
) -> None:
    song = api_client.post("/v2/songs", json={"title": "API Template Song"}).json()
    song_root = next((music_root / "songs").iterdir())

    response = api_client.post(
        f"/v2/songs/{song['id']}/projects/from-template",
        json={"template_name": "Reaper"},
    )

    assert response.status_code == 201
    updated = SongManifest.model_validate(response.json())
    project_root = next((song_root / "projects").iterdir())
    project_file = project_root / "API Template Song.RPP"
    assert project_file.read_text(encoding="utf-8") == "dummy reaper template"
    assert updated.assets[0].title == "API Template Song"
    assert updated.default_project_id == updated.assets[0].id
    assert load_song_manifest(song_root) == updated


def test_v2_create_song_project_from_nested_template_uses_custom_title(
    api_client: TestClient,
    music_root: Path,
) -> None:
    song = api_client.post("/v2/songs", json={"title": "API Ableton Song"}).json()
    song_root = next((music_root / "songs").iterdir())

    response = api_client.post(
        f"/v2/songs/{song['id']}/projects/from-template",
        json={
            "template_name": "Ableton",
            "title": "Custom Live Set",
            "make_default": False,
        },
    )

    assert response.status_code == 201
    updated = SongManifest.model_validate(response.json())
    project_root = next((song_root / "projects").iterdir())
    nested_root = project_root / "Custom Live Set"
    assert (nested_root / "Custom Live Set.als").read_text(
        encoding="utf-8"
    ) == "dummy ableton template"
    assert (nested_root / "Samples").is_dir()
    assert (nested_root / "Ableton Project Info").is_dir()
    assert updated.assets[0].title == "Custom Live Set"
    assert updated.default_project_id is None


def test_v2_create_song_project_from_template_returns_404_for_unknown_template(
    api_client: TestClient,
) -> None:
    song = api_client.post("/v2/songs", json={"title": "Unknown Template"}).json()

    response = api_client.post(
        f"/v2/songs/{song['id']}/projects/from-template",
        json={"template_name": "Unknown"},
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_v2_create_song_project_from_template_returns_404_for_missing_file(
    api_client: TestClient,
    config_path: Path,
    tmp_path: Path,
) -> None:
    song = api_client.post("/v2/songs", json={"title": "Missing Template"}).json()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["templates"]["Reaper"]["path"] = str(tmp_path / "missing.RPP")
    config_path.write_text(json.dumps(config), encoding="utf-8")

    response = api_client.post(
        f"/v2/songs/{song['id']}/projects/from-template",
        json={"template_name": "Reaper"},
    )

    assert response.status_code == 404
    assert "Template not found" in response.json()["detail"]


def test_v2_create_song_project_from_template_returns_404_for_unknown_song(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        "/v2/songs/song_00000000-0000-4000-8000-000000000000/projects/from-template",
        json={"template_name": "Reaper"},
    )

    assert response.status_code == 404
    assert "Song not found" in response.json()["detail"]


def test_v2_create_song_project_from_template_rejects_unusable_title(
    api_client: TestClient,
    music_root: Path,
) -> None:
    song = api_client.post("/v2/songs", json={"title": "Safe Song"}).json()
    song_root = next((music_root / "songs").iterdir())

    response = api_client.post(
        f"/v2/songs/{song['id']}/projects/from-template",
        json={"template_name": "Reaper", "title": "/\\:*?"},
    )

    assert response.status_code == 400
    assert "usable filename characters" in response.json()["detail"]
    assert list((song_root / "projects").iterdir()) == []


def test_v2_create_album_sequence_persists_secondary_tracklist(
    api_client: TestClient,
    music_root: Path,
) -> None:
    album = api_client.post(
        "/v2/albums",
        json={"title": "Multiple Tracklists", "song_ids": []},
    ).json()

    response = api_client.post(
        f"/v2/albums/{album['id']}/sequences",
        json={"title": "B-Sides", "description": "Alternate order."},
    )

    assert response.status_code == 201
    updated = AlbumManifest.model_validate(response.json())
    assert len(updated.sequences) == 2
    assert updated.sequences[1].title == "B-Sides"
    assert updated.sequences[1].description == "Alternate order."
    assert updated.sequences[1].entries == []
    assert updated.primary_sequence_id == album["primary_sequence_id"]
    album_root = next((music_root / "albums").iterdir())
    assert load_album_manifest(album_root) == updated


def test_v2_created_album_sequence_accepts_entries(
    api_client: TestClient,
) -> None:
    song = api_client.post("/v2/songs", json={"title": "B-Side Song"}).json()
    album = api_client.post(
        "/v2/albums",
        json={"title": "B-Sides Album", "song_ids": []},
    ).json()
    sequence_response = api_client.post(
        f"/v2/albums/{album['id']}/sequences",
        json={"title": "B-Sides"},
    ).json()
    sequence_id = sequence_response["sequences"][1]["id"]

    response = api_client.post(
        f"/v2/albums/{album['id']}/entries",
        json={"song_id": song["id"], "sequence_id": sequence_id},
    )

    assert response.status_code == 201
    assert response.json()["sequences"][1]["entries"][0]["song_id"] == song["id"]


def test_v2_create_album_sequence_returns_expected_errors(
    api_client: TestClient,
) -> None:
    album = api_client.post(
        "/v2/albums",
        json={"title": "Sequence Errors", "song_ids": []},
    ).json()

    blank = api_client.post(
        f"/v2/albums/{album['id']}/sequences",
        json={"title": " "},
    )
    missing = api_client.post(
        "/v2/albums/album_00000000-0000-4000-8000-000000000000/sequences",
        json={"title": "Missing Album"},
    )

    assert blank.status_code == 400
    assert "Title cannot be empty" in blank.json()["detail"]
    assert missing.status_code == 404
    assert "Album not found" in missing.json()["detail"]


def test_v2_patch_album_sequence_supports_partial_updates_and_clearing(
    api_client: TestClient,
) -> None:
    album = api_client.post(
        "/v2/albums",
        json={"title": "Editable Tracklists", "song_ids": []},
    ).json()
    created = api_client.post(
        f"/v2/albums/{album['id']}/sequences",
        json={"title": "B-Sides", "description": "Temporary"},
    ).json()
    sequence_id = created["sequences"][1]["id"]

    renamed = api_client.patch(
        f"/v2/albums/{album['id']}/sequences/{sequence_id}",
        json={"title": "Deluxe B-Sides"},
    )
    cleared = api_client.patch(
        f"/v2/albums/{album['id']}/sequences/{sequence_id}",
        json={"description": ""},
    )

    assert renamed.status_code == 200
    assert renamed.json()["sequences"][1]["title"] == "Deluxe B-Sides"
    assert renamed.json()["sequences"][1]["description"] == "Temporary"
    assert cleared.status_code == 200
    assert cleared.json()["sequences"][1]["title"] == "Deluxe B-Sides"
    assert cleared.json()["sequences"][1]["description"] == ""


def test_v2_patch_album_sequence_returns_expected_errors(
    api_client: TestClient,
) -> None:
    album = api_client.post(
        "/v2/albums",
        json={"title": "Patch Errors", "song_ids": []},
    ).json()
    sequence_id = album["primary_sequence_id"]

    blank = api_client.patch(
        f"/v2/albums/{album['id']}/sequences/{sequence_id}",
        json={"title": ""},
    )
    missing_sequence = api_client.patch(
        f"/v2/albums/{album['id']}/sequences/sequence_00000000-0000-4000-8000-000000000000",
        json={"title": "Missing"},
    )
    missing_album = api_client.patch(
        "/v2/albums/album_00000000-0000-4000-8000-000000000000/sequences/sequence_00000000-0000-4000-8000-000000000000",
        json={"title": "Missing"},
    )

    assert blank.status_code == 400
    assert "Title cannot be empty" in blank.json()["detail"]
    assert missing_sequence.status_code == 404
    assert "Sequence" in missing_sequence.json()["detail"]
    assert missing_album.status_code == 404
    assert "Album not found" in missing_album.json()["detail"]


def test_v2_delete_album_sequence_removes_secondary_and_persists(
    api_client: TestClient,
    music_root: Path,
) -> None:
    album = api_client.post(
        "/v2/albums",
        json={"title": "Delete B-Sides", "song_ids": []},
    ).json()
    created = api_client.post(
        f"/v2/albums/{album['id']}/sequences",
        json={"title": "B-Sides"},
    ).json()
    secondary_id = created["sequences"][1]["id"]

    response = api_client.delete(
        f"/v2/albums/{album['id']}/sequences/{secondary_id}"
    )

    assert response.status_code == 200
    updated = AlbumManifest.model_validate(response.json())
    assert [sequence.id for sequence in updated.sequences] == [
        album["primary_sequence_id"]
    ]
    album_root = next((music_root / "albums").iterdir())
    assert load_album_manifest(album_root) == updated


def test_v2_delete_album_sequence_returns_expected_errors(
    api_client: TestClient,
) -> None:
    album = api_client.post(
        "/v2/albums",
        json={"title": "Protected Sequence", "song_ids": []},
    ).json()

    primary = api_client.delete(
        f"/v2/albums/{album['id']}/sequences/{album['primary_sequence_id']}"
    )
    missing_sequence = api_client.delete(
        f"/v2/albums/{album['id']}/sequences/sequence_00000000-0000-4000-8000-000000000000"
    )
    missing_album = api_client.delete(
        "/v2/albums/album_00000000-0000-4000-8000-000000000000/sequences/sequence_00000000-0000-4000-8000-000000000000"
    )

    assert primary.status_code == 400
    assert "Cannot delete the primary sequence" in primary.json()["detail"]
    assert missing_sequence.status_code == 404
    assert "Sequence" in missing_sequence.json()["detail"]
    assert missing_album.status_code == 404
    assert "Album not found" in missing_album.json()["detail"]
