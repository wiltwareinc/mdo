"""Test the MVP version-2 song and album APIs through JSON storage.

These tests verify an empty library, song creation, portable metadata written
to disk, stable IDs across later list requests, and HTTP conflict handling for
duplicate directories. They also verify registering one shared album session,
persisting it, adding songs at requested track positions, and reporting
unknown album, song, sequence, and entry IDs. Track mutation tests also verify
reordering and removal through HTTP without losing persistence.

Authored by OpenAI Codex on 2026-08-25.
"""

from __future__ import annotations

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
    album_root = next((music_root / "albums").iterdir())
    assert session["location"]["storage_id"] == storage.id
    assert session["location"]["path"] == (
        album_root.relative_to(music_root) / "projects/continuous-album.rpp"
    ).as_posix()
    assert {
        entry["album_asset_id"]
        for entry in updated["sequences"][0]["entries"]
    } == {session["id"]}


def test_v2_registered_album_session_is_persisted(
    api_client: TestClient,
    music_root: Path,
) -> None:
    album = api_client.post(
        "/v2/albums",
        json={"title": "Persistent Session Album", "song_ids": []},
    ).json()

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

    album_root = next((music_root / "albums").iterdir())
    assert load_album_manifest(album_root) == returned


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
