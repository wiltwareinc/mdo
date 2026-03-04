# This test was written by ChatGPT Codex 5 on 2026-02-19
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

from fastapi import HTTPException
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.api import resolve_path
from app.deps import get_file_manager
from app.main import app


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def make_temp_music() -> Path:
    temp_root = ROOT / "extra" / "tmp-test"
    temp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="mdo-files-", dir=temp_root))
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

        sample_path = temp_music / "songs" / "sample.txt"
        sample_path.write_text("hello-world", encoding="utf-8")

        resp = client.get("/files", params={"path": "songs/sample.txt", "mode": "text"})
        print("GET /files text ->", resp.status_code, resp.json())
        assert_true(resp.status_code == 200, f"GET /files text failed: {resp.text}")
        assert_true(resp.json()["content"] == "hello-world", "text content mismatch")

        resp = client.get("/files", params={"path": "songs/sample.txt", "mode": "raw"})
        print("GET /files raw ->", resp.status_code, resp.headers.get("content-type"))
        assert_true(resp.status_code == 200, f"GET /files raw failed: {resp.text}")
        assert_true(resp.content == b"hello-world", "raw content mismatch")

        resp = client.get("/files", params={"path": "../outside.txt", "mode": "text"})
        print("GET /files traversal ->", resp.status_code, resp.text)
        assert_true(resp.status_code == 404, "path traversal should be blocked")

        resp = client.get("/files", params={"path": "songs", "mode": "text"})
        print("GET /files dir ->", resp.status_code, resp.text)
        assert_true(resp.status_code == 400, "directory path should be rejected")

        resolved = resolve_path("songs/sample.txt")
        assert_true(resolved == sample_path, "resolve_path should return the file path")

        try:
            resolve_path("../outside.txt")
            raise AssertionError("resolve_path should block traversal")
        except HTTPException as exc:
            assert_true(exc.status_code == 404, "resolve_path should raise 404 on traversal")

        print("file api tests: OK")
    finally:
        shutil.rmtree(temp_music.parent)


if __name__ == "__main__":
    main()
