"""Test the MVP version-2 song-library creation and listing workflow.

These tests verify that a new song returns its generated manifest, creates the
expected directory layout, can be listed again, rejects duplicate directories,
ignores unrelated entries, and does not leave a partial song after a failed
manifest write. Directory tests verify unsafe title characters cannot alter
the library layout. Project-registration tests verify storage-relative locations,
default selection, optional defaults, missing targets, path safety, and
persistence failure behavior. Shared-project tests verify that multiple songs
reuse one asset identity and location without creating duplicate references.
Metadata-update tests cover partial edits, explicit null clearing, validation,
stable directories, and persistence.

Authored by OpenAI Codex on 2026-08-25.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from domain.manifests import Asset, AssetKind, AssetPurpose, SongManifest
from persistence import song_library
from persistence.album_library import create_album, register_album_session
from persistence.manifests import load_song_manifest, write_song_manifest
from persistence.song_library import (
    assign_album_session_to_song,
    create_song,
    create_song_project_from_template,
    list_songs,
    register_song_project,
    update_song_metadata,
)
from persistence.storage import initialize_storage, load_storage_manifest


@pytest.fixture
def library_root(tmp_path: Path) -> Path:
    """Create an empty MDO root with its required songs directory."""
    root = tmp_path / "music"
    (root / "songs").mkdir(parents=True)
    initialize_storage(root, "Song Test Library")
    return root


@pytest.fixture
def registered_album_session(
    library_root: Path,
) -> tuple[SongManifest, Asset, Path, Path]:
    song = create_song(library_root, "Connected Song")
    song_root = next((library_root / "songs").iterdir())
    album = create_album(library_root, "Connected Album", [song.id])
    album_root = next((library_root / "albums").iterdir())
    project_path = album_root / "projects" / "connected.rpp"
    project_path.touch()
    registered = register_album_session(
        library_root,
        album.id,
        "Connected Session",
        "projects/connected.rpp",
        [],
    )
    return song, registered.assets[0], song_root, project_path


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


def test_create_song_sanitizes_directory_name_and_preserves_title(
    library_root: Path,
) -> None:
    title = "../Side A/B: Finale?"

    manifest = create_song(library_root, title)

    song_directories = list((library_root / "songs").iterdir())
    assert len(song_directories) == 1
    assert song_directories[0].name.endswith("-Side A-B- Finale-")
    assert manifest.title == title
    assert not (library_root / "Side A").exists()


def test_create_song_rejects_title_without_usable_filename_characters(
    library_root: Path,
) -> None:
    with pytest.raises(ValueError, match="usable filename characters"):
        create_song(library_root, "/\\:*?")

    assert list((library_root / "songs").iterdir()) == []


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


def test_register_song_project_reuses_parent_asset_and_location(
    library_root: Path,
) -> None:
    parent = create_song(library_root, "Connected Parent")
    target = create_song(library_root, "Connected Target")
    parent_root = next(
        path
        for path in (library_root / "songs").iterdir()
        if load_song_manifest(path).id == parent.id
    )
    target_root = next(
        path
        for path in (library_root / "songs").iterdir()
        if load_song_manifest(path).id == target.id
    )
    (parent_root / "projects" / "connected.rpp").write_text(
        "REAPER_PROJECT",
        encoding="utf-8",
    )
    registered_parent = register_song_project(
        library_root,
        parent.id,
        "Connected Session",
        "projects/connected.rpp",
    )

    shared = register_song_project(
        library_root,
        target.id,
        "Ignored Replacement Title",
        "projects/connected.rpp",
        parent_song=parent.id,
    )

    assert len(shared.assets) == 1
    assert shared.assets[0] == registered_parent.assets[0]
    assert shared.default_project_id == registered_parent.assets[0].id
    assert shared.assets[0].location.path == (
        parent_root.relative_to(library_root) / "projects/connected.rpp"
    ).as_posix()
    assert load_song_manifest(target_root) == shared

    repeated = register_song_project(
        library_root,
        target.id,
        "Still Ignored",
        "projects/connected.rpp",
        parent_song=parent.id,
    )
    assert len(repeated.assets) == 1
    assert repeated.assets[0] == registered_parent.assets[0]


def test_register_song_project_rejects_unknown_parent_song(
    library_root: Path,
) -> None:
    target = create_song(library_root, "Orphan Target")

    with pytest.raises(FileNotFoundError, match="Parent song not found"):
        register_song_project(
            library_root,
            target.id,
            "Missing Shared Session",
            "projects/missing.rpp",
            parent_song="song_00000000-0000-4000-8000-000000000000",
        )


def test_register_song_project_rejects_unregistered_parent_project(
    library_root: Path,
) -> None:
    parent = create_song(library_root, "Unregistered Parent")
    target = create_song(library_root, "Unregistered Target")

    with pytest.raises(FileNotFoundError, match="does not contain project"):
        register_song_project(
            library_root,
            target.id,
            "Unregistered Session",
            "projects/unregistered.rpp",
            parent_song=parent.id,
        )


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


def test_assign_album_session_to_song_sets_default_and_persists(
    library_root: Path,
    registered_album_session: tuple[SongManifest, Asset, Path, Path],
) -> None:
    song, session, song_root, _ = registered_album_session

    updated = assign_album_session_to_song(library_root, song.id, session.id)

    assert updated.assets == [session]
    assert updated.default_project_id == session.id
    assert load_song_manifest(song_root) == updated


def test_assign_album_session_to_song_can_leave_default_unchanged(
    library_root: Path,
    registered_album_session: tuple[SongManifest, Asset, Path, Path],
) -> None:
    song, session, _, _ = registered_album_session

    updated = assign_album_session_to_song(
        library_root,
        song.id,
        session.id,
        make_default=False,
    )

    assert updated.assets == [session]
    assert updated.default_project_id is None


def test_assign_album_session_to_song_is_idempotent(
    library_root: Path,
    registered_album_session: tuple[SongManifest, Asset, Path, Path],
) -> None:
    song, session, _, _ = registered_album_session

    assign_album_session_to_song(library_root, song.id, session.id)
    repeated = assign_album_session_to_song(library_root, song.id, session.id)

    assert repeated.assets == [session]
    assert repeated.default_project_id == session.id


def test_assign_album_session_to_song_rejects_unknown_asset_without_writing(
    library_root: Path,
    registered_album_session: tuple[SongManifest, Asset, Path, Path],
) -> None:
    song, _, song_root, _ = registered_album_session

    with pytest.raises(FileNotFoundError, match="Album session not found"):
        assign_album_session_to_song(
            library_root,
            song.id,
            "asset_00000000-0000-4000-8000-000000000000",
        )

    assert load_song_manifest(song_root) == song


def test_assign_album_session_to_song_rejects_missing_project_without_writing(
    library_root: Path,
    registered_album_session: tuple[SongManifest, Asset, Path, Path],
) -> None:
    song, session, song_root, project_path = registered_album_session
    project_path.unlink()

    with pytest.raises(FileNotFoundError, match="Project not found"):
        assign_album_session_to_song(library_root, song.id, session.id)

    assert load_song_manifest(song_root) == song


def test_assign_album_session_to_song_rejects_conflicting_existing_asset(
    library_root: Path,
    registered_album_session: tuple[SongManifest, Asset, Path, Path],
) -> None:
    song, session, song_root, _ = registered_album_session
    conflicting_asset = session.model_copy(update={"title": "Conflicting Session"})
    song.assets.append(conflicting_asset)
    write_song_manifest(song_root, song)

    with pytest.raises(ValueError, match="conflicting metadata"):
        assign_album_session_to_song(library_root, song.id, session.id)

    assert load_song_manifest(song_root).assets == [conflicting_asset]


def test_update_song_metadata_applies_partial_changes_and_persists(
    library_root: Path,
) -> None:
    original = create_song(library_root, "Original Song Title")
    song_root = next((library_root / "songs").iterdir())

    updated = update_song_metadata(
        library_root,
        original.id,
        {
            "title": "Updated Song Title",
            "description": "New description",
            "tags": ["connected", "electronic"],
        },
    )

    assert updated.title == "Updated Song Title"
    assert updated.description == "New description"
    assert updated.tags == ["connected", "electronic"]
    assert song_root.name.endswith("Original Song Title")
    assert updated.created_at == original.created_at
    assert updated.updated_at >= original.updated_at
    assert load_song_manifest(song_root) == updated


def test_update_song_metadata_can_clear_nullable_fields(
    library_root: Path,
) -> None:
    original = create_song(library_root, "Clearable Song")
    song_root = next((library_root / "songs").iterdir())
    (song_root / "projects" / "default.rpp").write_text(
        "REAPER_PROJECT",
        encoding="utf-8",
    )
    registered = register_song_project(
        library_root,
        original.id,
        "Default Session",
        "projects/default.rpp",
    )
    described = update_song_metadata(
        library_root,
        original.id,
        {"description": "Temporary description"},
    )
    assert described.default_project_id == registered.default_project_id

    cleared = update_song_metadata(
        library_root,
        original.id,
        {"description": None, "default_project_id": None},
    )

    assert cleared.description is None
    assert cleared.default_project_id is None
    assert cleared.assets == registered.assets
    assert load_song_manifest(song_root) == cleared


def test_update_song_metadata_rejects_unknown_default_without_writing(
    library_root: Path,
) -> None:
    original = create_song(library_root, "Invalid Default Song")
    song_root = next((library_root / "songs").iterdir())

    with pytest.raises(ValidationError, match="must reference an asset"):
        update_song_metadata(
            library_root,
            original.id,
            {"default_project_id": "asset_00000000-0000-4000-8000-000000000000"},
        )

    assert load_song_manifest(song_root) == original


def test_update_song_metadata_empty_changes_leave_manifest_unchanged(
    library_root: Path,
) -> None:
    original = create_song(library_root, "Unchanged Song")

    assert update_song_metadata(library_root, original.id, {}) == original


def test_update_song_metadata_rejects_unknown_song(library_root: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Song not found"):
        update_song_metadata(
            library_root,
            "song_00000000-0000-4000-8000-000000000000",
            {"title": "Missing"},
        )


def test_create_song_project_from_file_template_uses_song_title_and_persists(
    library_root: Path,
    tmp_path: Path,
) -> None:
    song = create_song(library_root, "Template Song")
    song_root = next((library_root / "songs").iterdir())
    template = tmp_path / "default.RPP"
    template.write_text("REAPER_TEMPLATE", encoding="utf-8")

    updated = create_song_project_from_template(
        library_root,
        song.id,
        template,
        nested_folder=False,
    )

    project_roots = list((song_root / "projects").iterdir())
    assert len(project_roots) == 1
    assert project_roots[0].name.endswith("_Template Song")
    project_file = project_roots[0] / "Template Song.RPP"
    assert project_file.read_text(encoding="utf-8") == "REAPER_TEMPLATE"
    assert updated.assets[0].title == "Template Song"
    assert updated.assets[0].location.path.endswith(
        "/projects/" + project_roots[0].name + "/Template Song.RPP"
    )
    assert updated.default_project_id == updated.assets[0].id
    assert load_song_manifest(song_root) == updated


def test_create_song_project_from_nested_template_preserves_folder_layout(
    library_root: Path,
    tmp_path: Path,
) -> None:
    song = create_song(library_root, "Ableton Song")
    song_root = next((library_root / "songs").iterdir())
    template_root = tmp_path / "ableton-template"
    template_root.mkdir()
    (template_root / "Samples").mkdir()
    (template_root / "Ableton Project Info").mkdir()
    template = template_root / "default.als"
    template.write_text("ABLETON_TEMPLATE", encoding="utf-8")

    updated = create_song_project_from_template(
        library_root,
        song.id,
        template,
        nested_folder=True,
        title="Live Set",
        make_default=False,
    )

    project_root = next((song_root / "projects").iterdir())
    nested_root = project_root / "Live Set"
    assert (nested_root / "Live Set.als").read_text(encoding="utf-8") == (
        "ABLETON_TEMPLATE"
    )
    assert (nested_root / "Samples").is_dir()
    assert (nested_root / "Ableton Project Info").is_dir()
    assert updated.assets[0].title == "Live Set"
    assert updated.assets[0].location.path.endswith(
        "/projects/" + project_root.name + "/Live Set/Live Set.als"
    )
    assert updated.default_project_id is None
    assert load_song_manifest(song_root) == updated


def test_create_song_project_from_template_increments_duplicate_names(
    library_root: Path,
    tmp_path: Path,
) -> None:
    song = create_song(library_root, "Duplicate Project Song")
    song_root = next((library_root / "songs").iterdir())
    template = tmp_path / "default.RPP"
    template.touch()

    create_song_project_from_template(
        library_root,
        song.id,
        template,
        nested_folder=False,
        title="Same Session",
    )
    updated = create_song_project_from_template(
        library_root,
        song.id,
        template,
        nested_folder=False,
        title="Same Session",
    )

    project_names = sorted(path.name for path in (song_root / "projects").iterdir())
    assert project_names[1] == f"{project_names[0]}_1"
    assert len(updated.assets) == 2
    assert updated.default_project_id == updated.assets[-1].id


def test_create_song_project_from_template_rejects_missing_template_without_writing(
    library_root: Path,
    tmp_path: Path,
) -> None:
    song = create_song(library_root, "Missing Template Song")
    song_root = next((library_root / "songs").iterdir())

    with pytest.raises(FileNotFoundError, match="Template not found"):
        create_song_project_from_template(
            library_root,
            song.id,
            tmp_path / "missing.RPP",
            nested_folder=False,
        )

    assert list((song_root / "projects").iterdir()) == []
    assert load_song_manifest(song_root) == song


def test_create_song_project_from_template_cleans_up_failed_copy(
    library_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    song = create_song(library_root, "Copy Failure Song")
    song_root = next((library_root / "songs").iterdir())
    template = tmp_path / "default.RPP"
    template.touch()

    def fail_copy(*args, **kwargs):
        raise OSError("simulated template copy failure")

    monkeypatch.setattr(song_library.shutil, "copy2", fail_copy)

    with pytest.raises(OSError, match="simulated template copy failure"):
        create_song_project_from_template(
            library_root,
            song.id,
            template,
            nested_folder=False,
        )

    assert list((song_root / "projects").iterdir()) == []
    assert load_song_manifest(song_root) == song


def test_create_song_project_from_template_cleans_up_failed_manifest_write(
    library_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    song = create_song(library_root, "Write Failure Song")
    song_root = next((library_root / "songs").iterdir())
    template = tmp_path / "default.RPP"
    template.touch()

    def fail_write(*args, **kwargs) -> Path:
        raise OSError("simulated template manifest write failure")

    monkeypatch.setattr(song_library, "write_song_manifest", fail_write)

    with pytest.raises(OSError, match="simulated template manifest write failure"):
        create_song_project_from_template(
            library_root,
            song.id,
            template,
            nested_folder=False,
        )

    assert list((song_root / "projects").iterdir()) == []
    assert load_song_manifest(song_root) == song
