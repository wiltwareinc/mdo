"""Verify safe text/raw file access through the API and path resolver.

The tests cover successful reads, invalid modes, directories, missing paths,
and attempts to escape the configured temporary library root.

Authored by OpenAI Codex on 2026-08-07.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api import resolve_path


@pytest.fixture
def sample_file(music_root: Path) -> Path:
    path = music_root / "songs" / "sample.txt"
    path.write_text("hello-world", encoding="utf-8")
    return path


def test_get_file_as_text(api_client: TestClient, sample_file: Path) -> None:
    response = api_client.get("/files/songs/sample.txt", params={"mode": "text"})

    assert response.status_code == 200
    assert response.json() == {
        "path": "songs/sample.txt",
        "content": "hello-world",
    }


def test_get_file_as_raw_bytes(api_client: TestClient, sample_file: Path) -> None:
    response = api_client.get("/files/songs/sample.txt", params={"mode": "raw"})

    assert response.status_code == 200
    assert response.content == b"hello-world"


def test_get_file_rejects_invalid_mode(
    api_client: TestClient,
    sample_file: Path,
) -> None:
    response = api_client.get("/files/songs/sample.txt", params={"mode": "unknown"})

    assert response.status_code == 400


def test_resolve_path_returns_file(
    configured_environment: None,
    sample_file: Path,
) -> None:
    assert resolve_path("songs/sample.txt") == sample_file


@pytest.mark.parametrize(
    "path, expected_status",
    [
        ("../outside.txt", 404),
        ("songs/missing.txt", 404),
        ("songs", 400),
    ],
)
def test_resolve_path_rejects_unsafe_or_non_file_targets(
    configured_environment: None,
    path: str,
    expected_status: int,
) -> None:
    with pytest.raises(HTTPException) as error:
        resolve_path(path)

    assert error.value.status_code == expected_status
