"""Exercise legacy FileManager creation, editing, and relationship behavior.

These integration tests use a fresh temporary library for every test. They
protect current song/album behavior while the version-2 architecture is built.

Authored by OpenAI Codex on 2026-08-07.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from models.file_manager import FileManager


def test_file_manager_creates_required_layout(
    tmp_path: Path,
    configured_environment: None,
) -> None:
    root = tmp_path / "new-library"

    FileManager(root)

    assert (root / "songs").is_dir()
    assert (root / "albums").is_dir()


def test_create_song_builds_metadata_and_lyrics(file_manager: FileManager) -> None:
    created = file_manager.create_song("unit-test-song", ["lyrics"])

    assert created is not None
    assert created.is_dir()
    assert (created / ".metadata.json").is_file()
    assert list((created / "lyrics").glob("*.txt"))


def test_duplicate_song_is_rejected(file_manager: FileManager) -> None:
    assert file_manager.create_song("duplicate-song", []) is not None

    assert file_manager.create_song("duplicate-song", []) is None


def test_create_and_rename_album(file_manager: FileManager) -> None:
    song = file_manager.create_song("album-song", [])
    assert song is not None

    album = file_manager.create_album("unit-test-album", [song.name])
    assert album is not None
    assert (album / ".metadata.json").is_file()
    assert (album / "songs" / song.name).is_symlink()

    renamed = file_manager.edit_album(album, "unit-test-album-renamed", [song.name])
    assert renamed is not None
    assert renamed.is_dir()
    assert not album.exists()


def test_duplicate_album_is_rejected(file_manager: FileManager) -> None:
    assert file_manager.create_album("duplicate-album", []) is not None

    assert file_manager.create_album("duplicate-album", []) is None


def test_rename_song_updates_album_references(file_manager: FileManager) -> None:
    song = file_manager.create_song("linked-song", [])
    assert song is not None
    old_slug = song.name

    album = file_manager.create_album("linked-album", [old_slug])
    assert album is not None

    renamed = file_manager.edit_song(song, "renamed-linked-song", None)
    assert renamed is not None

    new_link = album / "songs" / renamed.name
    assert not (album / "songs" / old_slug).is_symlink()
    assert new_link.is_symlink()
    assert new_link.resolve() == renamed.resolve()

    file_manager.refresh_albums()
    album_data = next(item for item in file_manager.albums if item["slug"] == album.name)
    assert [track["slug"] for track in album_data["tracklist"]] == [renamed.name]


@pytest.mark.xfail(
    reason="Known legacy bug: rebuilding metadata resets the selected default project",
    strict=True,
)
def test_metadata_rebuild_preserves_default_project(file_manager: FileManager) -> None:
    song = file_manager.create_song("default-project-song", [])
    assert song is not None

    first_project = song / "projects" / "20260101-first-project"
    second_project = song / "projects" / "20260102-second-project"
    first_project.mkdir()
    second_project.mkdir()

    first_project_ref = str(first_project.relative_to(song))
    assert file_manager.edit_song(song, None, first_project_ref) is not None

    rebuilt = file_manager.create_metadata("song", song)
    assert rebuilt["default_project"] == first_project_ref

    assert file_manager.create_lyrics(song, "default-project-song") is not None
    assert file_manager.edit_song(song, None, None) is not None

    file_manager.refresh_songs()
    song_data = next(item for item in file_manager.songs if item["slug"] == song.name)
    assert song_data["default_project"] == first_project_ref
