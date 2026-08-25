"""Test the MVP version-2 song API from HTTP request through JSON storage.

These tests verify an empty library, song creation, portable metadata written
to disk, stable IDs across later list requests, and HTTP conflict handling for
duplicate song directories.

Authored by OpenAI Codex on 2026-08-25.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from domain.manifests import SongManifest
from persistence.manifests import load_song_manifest


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
