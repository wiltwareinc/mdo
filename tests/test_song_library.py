"""Test the MVP version-2 song-library creation and listing workflow.

These tests verify that a new song returns its generated manifest, creates the
expected directory layout, can be listed again, rejects duplicate directories,
ignores unrelated entries, and does not leave a partial song after a failed
manifest write. Project-registration tests verify storage-relative locations,
default selection, optional defaults, missing targets, path safety, and
persistence failure behavior.

Authored by OpenAI Codex on 2026-08-25.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from domain.manifests import AssetKind, AssetPurpose, SongManifest
from persistence import song_library
from persistence.manifests import load_song_manifest
from persistence.song_library import create_song, list_songs, register_song_project
from persistence.storage import initialize_storage, load_storage_manifest


@pytest.fixture
def library_root(tmp_path: Path) -> Path:
    """Create an empty MDO root with its required songs directory."""
    root = tmp_path / "music"
    (root / "songs").mkdir(parents=True)
    initialize_storage(root, "Song Test Library")
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


def test_register_song_project_creates_default_asset_and_persists(
    library_root: Path,
) -> None:
    original = create_song(library_root, "Shared Project Song")
    song_root = next((library_root / "songs").iterdir())
    project_path = song_root / "projects" / "shared-session.rpp"
    project_path.write_text("REAPER_PROJECT", encoding="utf-8")

    updated = register_song_project(
        library_root,
        original.id,
        "Shared Session",
        "projects/shared-session.rpp",
    )

    assert len(updated.assets) == 1
    asset = updated.assets[0]
    storage = load_storage_manifest(library_root)
    assert asset.kind == AssetKind.PROJECT
    assert asset.purpose == AssetPurpose.SONG_SESSION
    assert asset.title == "Shared Session"
    assert asset.location.storage_id == storage.id
    assert asset.location.path == (
        song_root.relative_to(library_root) / "projects/shared-session.rpp"
    ).as_posix()
    assert updated.default_project_id == asset.id
    assert load_song_manifest(song_root) == updated


def test_register_song_project_can_leave_default_unchanged(
    library_root: Path,
) -> None:
    original = create_song(library_root, "Optional Project Song")
    song_root = next((library_root / "songs").iterdir())
    (song_root / "projects" / "alternate.rpp").write_text(
        "REAPER_PROJECT",
        encoding="utf-8",
    )

    updated = register_song_project(
        library_root,
        original.id,
        "Alternate Session",
        "projects/alternate.rpp",
        make_default=False,
    )

    assert len(updated.assets) == 1
    assert updated.default_project_id is None


def test_register_song_project_rejects_unknown_song(
    library_root: Path,
) -> None:
    with pytest.raises(FileNotFoundError, match="Song not found"):
        register_song_project(
            library_root,
            "song_00000000-0000-4000-8000-000000000000",
            "Missing Session",
            "projects/missing.rpp",
        )


def test_register_song_project_rejects_missing_project_without_writing(
    library_root: Path,
) -> None:
    original = create_song(library_root, "Missing Project Song")
    song_root = next((library_root / "songs").iterdir())

    with pytest.raises(FileNotFoundError, match="Project not found"):
        register_song_project(
            library_root,
            original.id,
            "Missing Session",
            "projects/missing.rpp",
        )

    assert load_song_manifest(song_root) == original


def test_register_song_project_rejects_path_outside_song(
    library_root: Path,
) -> None:
    original = create_song(library_root, "Safe Project Song")
    outside_project = library_root / "outside.rpp"
    outside_project.write_text("NOT_INSIDE_SONG", encoding="utf-8")

    with pytest.raises(ValidationError, match="must not escape storage"):
        register_song_project(
            library_root,
            original.id,
            "Outside Session",
            "../../outside.rpp",
        )


def test_register_song_project_write_failure_preserves_original_manifest(
    library_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = create_song(library_root, "Failed Registration Song")
    song_root = next((library_root / "songs").iterdir())
    (song_root / "projects" / "session.rpp").write_text(
        "REAPER_PROJECT",
        encoding="utf-8",
    )

    def fail_write(*args, **kwargs) -> Path:
        raise OSError("simulated project registration write failure")

    monkeypatch.setattr(song_library, "write_song_manifest", fail_write)

    with pytest.raises(OSError, match="simulated project registration write failure"):
        register_song_project(
            library_root,
            original.id,
            "Failed Session",
            "projects/session.rpp",
        )

    assert load_song_manifest(song_root) == original
