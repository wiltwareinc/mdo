"""Test the TUI HTTP client against the in-process FastAPI application.

Requests calls are redirected to FastAPI's TestClient, preserving the complete
TUI-to-API workflow without starting a server or making network requests.

Authored by OpenAI Codex on 2026-08-07.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import requests
from fastapi.testclient import TestClient

from tui import api_client as tui_client


class ResponseProxy:
    """Adapt a TestClient response to the subset of requests.Response in use."""

    def __init__(self, response) -> None:
        self._response = response
        self.status_code = response.status_code
        self.text = response.text

    def json(self):
        return self._response.json()

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(self.text)


@pytest.fixture
def redirected_requests(
    monkeypatch: pytest.MonkeyPatch,
    api_client: TestClient,
) -> Iterator[None]:
    """Redirect requests.get/post/patch calls into the FastAPI TestClient."""

    def path_from_url(url: str) -> str:
        return urlsplit(url).path or "/"

    def fake_get(url: str, timeout: int = 5):
        return ResponseProxy(api_client.get(path_from_url(url)))

    def fake_post(url: str, json: dict | None = None, timeout: int = 5):
        return ResponseProxy(api_client.post(path_from_url(url), json=json))

    def fake_patch(url: str, json: dict | None = None, timeout: int = 5):
        return ResponseProxy(api_client.patch(path_from_url(url), json=json))

    monkeypatch.setattr(tui_client.requests, "get", fake_get)
    monkeypatch.setattr(tui_client.requests, "post", fake_post)
    monkeypatch.setattr(tui_client.requests, "patch", fake_patch)
    yield


def test_tui_client_lists_empty_library(redirected_requests: None) -> None:
    assert tui_client.get_songs() == []
    assert tui_client.get_albums() == []


def test_tui_client_song_and_album_workflow(
    redirected_requests: None,
    music_root: Path,
) -> None:
    created_song = tui_client.create_song(
        "ignored-by-current-signature",
        {"title": "tui-api-song", "args": ["lyrics"]},
    )
    original_slug = created_song["slug"]
    assert tui_client.get_song(original_slug)["slug"] == original_slug

    updated_song = tui_client.edit_song(
        original_slug,
        {"title": "tui-api-song-renamed"},
    )
    updated_slug = updated_song["slug"]
    assert updated_slug != original_slug

    lyric_count = len(updated_song["lyrics"])
    with_lyric = tui_client.create_lyric(
        updated_slug,
        {"title": updated_song["title"]},
    )
    assert len(with_lyric["lyrics"]) == lyric_count + 1

    with_project = tui_client.create_project(
        updated_slug,
        {"title": with_lyric["title"], "type": "Reaper"},
    )
    assert with_project["default_project"] is not None
    project_path = music_root / "songs" / updated_slug / with_project["projects"][-1]["path"]
    assert any(path.suffix == ".RPP" for path in project_path.iterdir())

    created_album = tui_client.create_album(
        "ignored-by-current-signature",
        {"title": "tui-api-album", "tracklist": [updated_slug]},
    )
    assert tui_client.get_album(created_album["slug"])["slug"] == created_album["slug"]

    updated_album = tui_client.edit_album(
        created_album["slug"],
        {"title": "tui-api-album-renamed"},
    )
    assert updated_album["slug"] != created_album["slug"]
