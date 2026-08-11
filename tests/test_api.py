"""Test the legacy FastAPI song and album CRUD endpoints.

Each test uses FastAPI's in-process TestClient and a temporary library, so no
server, network connection, or real music collection is required.

Authored by OpenAI Codex on 2026-08-07.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_song_list_starts_empty(api_client: TestClient) -> None:
    response = api_client.get("/songs")

    assert response.status_code == 200
    assert response.json() == []


def test_create_get_and_update_song(api_client: TestClient) -> None:
    created_response = api_client.post(
        "/songs",
        json={"title": "api-test-song", "args": []},
    )
    assert created_response.status_code == 201
    created = created_response.json()
    original_slug = created["slug"]

    get_response = api_client.get(f"/songs/{original_slug}")
    assert get_response.status_code == 200
    assert get_response.json()["slug"] == original_slug

    update_response = api_client.patch(
        f"/songs/{original_slug}",
        json={"title": "api-test-song-renamed"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["slug"] != original_slug
    assert update_response.json()["title"] == "api-test-song-renamed"


def test_create_and_get_album(api_client: TestClient) -> None:
    song_response = api_client.post(
        "/songs",
        json={"title": "album-track", "args": []},
    )
    song_slug = song_response.json()["slug"]

    created_response = api_client.post(
        "/albums",
        json={"title": "api-test-album", "tracklist": [song_slug]},
    )
    assert created_response.status_code == 201
    created = created_response.json()
    assert [track["slug"] for track in created["tracklist"]] == [song_slug]

    get_response = api_client.get(f"/albums/{created['slug']}")
    assert get_response.status_code == 200
    assert get_response.json()["slug"] == created["slug"]


def test_missing_song_and_album_return_not_found(api_client: TestClient) -> None:
    assert api_client.get("/songs/not-a-song").status_code == 404
    assert api_client.get("/albums/not-an-album").status_code == 404
