"""Test the MVP version-2 song-library creation and listing workflow.

These tests verify that a new song returns its generated manifest, creates the
expected directory layout, can be listed again, rejects duplicate directories,
ignores unrelated entries, and does not leave a partial song after a failed
manifest write.

Authored by OpenAI Codex on 2026-08-25.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from domain.manifests import SongManifest
from persistence import song_library
from persistence.manifests import load_song_manifest
from persistence.song_library import create_song, list_songs


@pytest.fixture
def library_root(tmp_path: Path) -> Path:
    """Create an empty MDO root with its required songs directory."""
    root = tmp_path / "music"
    (root / "songs").mkdir(parents=True)
    return root


def test_create_song_returns_manifest_and_creates_layout(
    library_root: Path,
) -> None:
    manifest = create_song(library_root, "New Song")

    assert isinstance(manifest, SongManifest)
    assert manifest.title == "New Song"

    song_directories = list((library_root / "songs").iterdir())
    assert len(song_directories) == 1
    song_root = song_directories[0]
    assert song_root.is_dir()
    assert (song_root / "lyrics").is_dir()
    assert (song_root / "projects").is_dir()
    assert (song_root / "renders").is_dir()
    assert (song_root / ".metadata.json").is_file()
    assert load_song_manifest(song_root) == manifest


def test_list_songs_returns_created_manifests(library_root: Path) -> None:
    first = create_song(library_root, "First Song")
    second = create_song(library_root, "Second Song")

    listed = list_songs(library_root)

    assert {song.id for song in listed} == {first.id, second.id}
    assert {song.title for song in listed} == {"First Song", "Second Song"}


def test_list_songs_ignores_files_and_directories_without_metadata(
    library_root: Path,
) -> None:
    expected = create_song(library_root, "Real Song")
    (library_root / "songs" / "README.txt").write_text("not a song", encoding="utf-8")
    (library_root / "songs" / "unmanaged-directory").mkdir()

    assert list_songs(library_root) == [expected]


def test_create_song_rejects_duplicate_directory(library_root: Path) -> None:
    create_song(library_root, "Duplicate Song")

    with pytest.raises(FileExistsError):
        create_song(library_root, "Duplicate Song")

    assert len(list((library_root / "songs").iterdir())) == 1


def test_failed_manifest_write_removes_partial_song_directory(
    library_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_write(*args, **kwargs) -> Path:
        raise OSError("simulated manifest write failure")

    monkeypatch.setattr(song_library, "write_song_manifest", fail_write)

    with pytest.raises(OSError, match="simulated manifest write failure"):
        create_song(library_root, "Failed Song")

    assert list((library_root / "songs").iterdir()) == []
