# This test was written by ChatGPT Codex 5 on 2026-02-19
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.deps import get_file_manager
from app.main import app


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def make_temp_music() -> Path:
    temp_root = ROOT / "extra" / "tmp-test"
    temp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="mdo-api-", dir=temp_root))
    temp_music = temp_dir / "music"
    temp_music.mkdir()
    (temp_music / "songs").mkdir()
    (temp_music / "albums").mkdir()
    return temp_music


def main() -> None:
    temp_music = make_temp_music()
    try:
        os.environ["MDO_ROOT"] = str(temp_music)
        get_file_manager.cache_clear()
        client = TestClient(app)

        resp = client.get("/songs")
        print("GET /songs ->", resp.status_code, resp.json())
        assert_true(resp.status_code == 200, f"GET /songs failed: {resp.text}")
        assert_true(isinstance(resp.json(), list), "GET /songs should return a list")

        create_payload = {"title": "api-test-song", "args": []}
        print("POST /songs payload ->", create_payload)
        resp = client.post("/songs", json=create_payload)
        print("POST /songs ->", resp.status_code, resp.json())
        assert_true(resp.status_code == 201, f"POST /songs failed: {resp.text}")
        song = resp.json()
        slug = song.get("slug")
        assert_true(slug, "POST /songs should return a slug")

        resp = client.get(f"/songs/{slug}")
        print(f"GET /songs/{slug} ->", resp.status_code, resp.json())
        assert_true(resp.status_code == 200, f"GET /songs/{{slug}} failed: {resp.text}")

        patch_payload = {"name": "api-test-song-renamed"}
        print(f"PATCH /songs/{slug} payload ->", patch_payload)
        resp = client.patch(f"/songs/{slug}", json=patch_payload)
        print(f"PATCH /songs/{slug} ->", resp.status_code, resp.json())
        assert_true(resp.status_code == 200, f"PATCH /songs/{{slug}} failed: {resp.text}")
        updated_song = resp.json()
        updated_slug = updated_song.get("slug")
        assert_true(updated_slug and updated_slug != slug, "PATCH /songs should rename slug")

        album_payload = {"title": "api-test-album", "tracklist": [updated_slug]}
        print("POST /albums payload ->", album_payload)
        resp = client.post("/albums", json=album_payload)
        print("POST /albums ->", resp.status_code, resp.json())
        assert_true(resp.status_code == 201, f"POST /albums failed: {resp.text}")
        album = resp.json()
        album_slug = album.get("slug")
        assert_true(album_slug, "POST /albums should return a slug")

        resp = client.get(f"/albums/{album_slug}")
        print(f"GET /albums/{album_slug} ->", resp.status_code, resp.json())
        assert_true(resp.status_code == 200, f"GET /albums/{{slug}} failed: {resp.text}")

        print("api tests: OK")
    finally:
        shutil.rmtree(temp_music.parent)


if __name__ == "__main__":
    main()
