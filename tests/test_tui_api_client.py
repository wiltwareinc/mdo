# This test was written by ChatGPT Codex 5 on 2026-03-10
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.deps import get_file_manager
from app.main import app
from tui import api_client


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def make_temp_music() -> Path:
    temp_root = ROOT / "extra" / "tmp-test"
    temp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="mdo-tui-client-", dir=temp_root))
    temp_music = temp_dir / "music"
    temp_music.mkdir()
    (temp_music / "songs").mkdir()
    (temp_music / "albums").mkdir()
    return temp_music


def make_temp_home(temp_music: Path) -> Path:
    temp_home = temp_music.parent / "home"
    template_dir = temp_home / ".config" / "REAPER" / "ProjectTemplates"
    template_dir.mkdir(parents=True, exist_ok=True)
    (template_dir / "default.RPP").write_text("dummy reaper template", encoding="utf-8")
    return temp_home


class RespProxy:
    """Small requests.Response-like shim for TestClient responses."""

    def __init__(self, response) -> None:
        self._response = response
        self.status_code = response.status_code
        self.text = response.text

    def json(self):
        return self._response.json()

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(self.text)


def _path_from_url(url: str) -> str:
    parts = urlsplit(url)
    return parts.path or "/"


def test_tui_api_client_crud(client: TestClient, temp_music: Path) -> None:
    def fake_get(url: str, timeout: int = 5):
        return RespProxy(client.get(_path_from_url(url)))

    def fake_post(url: str, json: dict | None = None, timeout: int = 5):
        return RespProxy(client.post(_path_from_url(url), json=json))

    def fake_patch(url: str, json: dict | None = None, timeout: int = 5):
        return RespProxy(client.patch(_path_from_url(url), json=json))

    with (
        patch.object(api_client.requests, "get", side_effect=fake_get),
        patch.object(api_client.requests, "post", side_effect=fake_post),
        patch.object(api_client.requests, "patch", side_effect=fake_patch),
    ):
        songs_before = api_client.get_songs()
        assert_true(songs_before == [], "expected empty song list in temp fs")

        created_song = api_client.create_song(
            "ignored-by-current-signature",
            {"title": "tui-api-song", "args": ["lyrics"]},
        )
        song_slug = created_song.get("slug")
        assert_true(bool(song_slug), "create_song should return a slug")
        assert_true(created_song.get("title") == "tui-api-song", "song title mismatch")

        got_song = api_client.get_song(song_slug)
        assert_true(got_song.get("slug") == song_slug, "get_song should return created slug")

        updated_song = api_client.edit_song(song_slug, {"title": "tui-api-song-renamed"})
        updated_slug = updated_song.get("slug")
        assert_true(bool(updated_slug), "edit_song should return updated slug")
        assert_true(updated_slug != song_slug, "song slug should change after rename")

        lyric_before = len(updated_song.get("lyrics", []))
        lyric_name = updated_song.get("title")
        lyric_song = api_client.create_lyric(updated_slug, {"title": lyric_name})
        lyric_after = len(lyric_song.get("lyrics", []))
        assert_true(lyric_after == lyric_before + 1, "create_lyric should add one lyric")
        lyric_rel = lyric_song["lyrics"][-1]["path"]
        assert_true(
            (temp_music / "songs" / updated_slug / lyric_rel).exists(),
            "create_lyric should create lyric file on disk",
        )

        project_before = len(lyric_song.get("projects", []))
        project_song = api_client.create_project(
            updated_slug, {"title": lyric_song.get("title"), "type": "Reaper"}
        )
        project_after = len(project_song.get("projects", []))
        assert_true(project_after == project_before + 1, "create_project should add one project")
        assert_true(
            project_song.get("default_project") is not None,
            "create_project should set a default project",
        )
        project_rel = project_song["projects"][-1]["path"]
        project_dir = temp_music / "songs" / updated_slug / project_rel
        assert_true(project_dir.exists(), "create_project should create project folder")
        assert_true(
            any(p.suffix == ".RPP" for p in project_dir.iterdir()),
            "create_project should create an .RPP file",
        )

        created_album = api_client.create_album(
            "ignored-by-current-signature",
            {"title": "tui-api-album", "tracklist": [updated_slug]},
        )
        album_slug = created_album.get("slug")
        assert_true(bool(album_slug), "create_album should return a slug")

        got_album = api_client.get_album(album_slug)
        assert_true(got_album.get("slug") == album_slug, "get_album should return created slug")

        updated_album = api_client.edit_album(album_slug, {"title": "tui-api-album-renamed"})
        assert_true(updated_album.get("slug") != album_slug, "album slug should change after rename")


def main() -> None:
    temp_music = make_temp_music()
    old_home = os.environ.get("HOME")
    try:
        temp_home = make_temp_home(temp_music)
        os.environ["MDO_ROOT"] = str(temp_music)
        os.environ["HOME"] = str(temp_home)
        get_file_manager.cache_clear()
        client = TestClient(app)
        test_tui_api_client_crud(client, temp_music)
        print("tui api client tests: OK")
    finally:
        if old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = old_home
        shutil.rmtree(temp_music.parent)


if __name__ == "__main__":
    main()
