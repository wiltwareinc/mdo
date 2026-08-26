"""Test the MVP version-2 album-library creation and listing workflow.

These tests verify album directory layout, ordered primary-sequence entries,
empty albums, duplicate rejection, stable listing results, ignored unmanaged
items, and cleanup after a failed manifest write.

Authored by OpenAI Codex on 2026-08-26.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from domain.manifests import AlbumManifest
from persistence import album_library
from persistence.album_library import create_album, list_albums
from persistence.manifests import load_album_manifest


SONG_IDS = [
    "song_2f8c2a4e-8bd2-4d57-a1c7-7e4cbfd52a91",
    "song_225aa914-22bd-4e35-b12d-66b145a090b2",
]


@pytest.fixture
def library_root(tmp_path: Path) -> Path:
    """Create an empty MDO root with its required albums directory."""
    root = tmp_path / "music"
    (root / "albums").mkdir(parents=True)
    return root


def test_create_album_returns_manifest_and_creates_layout(
    library_root: Path,
) -> None:
    manifest = create_album(library_root, "Connected Album", SONG_IDS)

    assert isinstance(manifest, AlbumManifest)
    assert manifest.title == "Connected Album"
    assert [entry.song_id for entry in manifest.sequences[0].entries] == SONG_IDS

    album_directories = list((library_root / "albums").iterdir())
    assert len(album_directories) == 1
    album_root = album_directories[0]
    assert album_root.is_dir()
    assert (album_root / "projects").is_dir()
    assert (album_root / "artwork").is_dir()
    assert (album_root / "exports").is_dir()
    assert (album_root / ".metadata.json").is_file()
    assert load_album_manifest(album_root) == manifest


def test_create_album_allows_empty_primary_sequence(library_root: Path) -> None:
    manifest = create_album(library_root, "Empty Album", [])

    assert len(manifest.sequences) == 1
    assert manifest.sequences[0].entries == []
    assert manifest.primary_sequence_id == manifest.sequences[0].id


def test_list_albums_returns_created_manifests(library_root: Path) -> None:
    first = create_album(library_root, "First Album", SONG_IDS)
    second = create_album(library_root, "Second Album", [])

    listed = list_albums(library_root)

    assert {album.id for album in listed} == {first.id, second.id}
    assert {album.title for album in listed} == {"First Album", "Second Album"}


def test_list_albums_ignores_files_and_directories_without_metadata(
    library_root: Path,
) -> None:
    expected = create_album(library_root, "Real Album", SONG_IDS)
    (library_root / "albums" / "README.txt").write_text(
        "not an album",
        encoding="utf-8",
    )
    (library_root / "albums" / "unmanaged-directory").mkdir()

    assert list_albums(library_root) == [expected]


def test_create_album_rejects_duplicate_directory(library_root: Path) -> None:
    create_album(library_root, "Duplicate Album", SONG_IDS)

    with pytest.raises(FileExistsError):
        create_album(library_root, "Duplicate Album", SONG_IDS)

    assert len(list((library_root / "albums").iterdir())) == 1


def test_failed_manifest_write_removes_partial_album_directory(
    library_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_write(*args, **kwargs) -> Path:
        raise OSError("simulated album manifest write failure")

    monkeypatch.setattr(album_library, "write_album_manifest", fail_write)

    with pytest.raises(OSError, match="simulated album manifest write failure"):
        create_album(library_root, "Failed Album", SONG_IDS)

    assert list((library_root / "albums").iterdir()) == []
