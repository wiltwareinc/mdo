"""Test the MVP version-2 album-library creation and listing workflow.

These tests verify album directory layout, ordered primary-sequence entries,
empty albums, duplicate rejection, stable listing results, ignored unmanaged
items, cleanup after a failed manifest write, and registration of one shared
album-session asset across multiple track entries. Entry tests cover default
and explicit sequences, exact insertion positions, invalid targets, and disk
persistence, plus reordering and removal without regenerating stable IDs.
Album creation tests also verify that every initial track references a song
that is actually present in the library. Metadata-update tests cover partial
edits, explicit null clearing, stable directories, and persistence.

Authored by OpenAI Codex on 2026-08-26.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from domain.manifests import AlbumManifest, AssetKind, AssetPurpose, Entry, Sequence
from persistence import album_library
from persistence.album_library import (
    add_album_entry,
    create_album,
    list_albums,
    register_album_session,
    remove_album_entry,
    reorder_album_entry,
    update_album_metadata,
)
from persistence.manifests import (
    load_album_manifest,
    load_song_manifest,
    write_album_manifest,
    write_song_manifest,
)
from persistence.song_library import create_song
from persistence.storage import initialize_storage, load_storage_manifest

SONG_IDS = [
    "song_2f8c2a4e-8bd2-4d57-a1c7-7e4cbfd52a91",
    "song_225aa914-22bd-4e35-b12d-66b145a090b2",
]
UNKNOWN_SONG_ID = "song_941a5060-7e46-421c-953b-b85cf7ed65e8"
ALTERNATE_SEQUENCE_ID = "sequence_11111111-1111-4111-8111-111111111111"


@pytest.fixture
def library_root(tmp_path: Path) -> Path:
    """Create an MDO root containing the two stable fixture songs."""
    root = tmp_path / "music"
    (root / "albums").mkdir(parents=True)
    (root / "songs").mkdir()
    initialize_storage(root, "Album Test Library")

    for number, song_id in enumerate(SONG_IDS, start=1):
        created = create_song(root, f"Fixture Song {number}")
        song_root = next(
            path
            for path in (root / "songs").iterdir()
            if load_song_manifest(path).id == created.id
        )
        stable_fixture = created.model_copy(update={"id": song_id})
        write_song_manifest(song_root, stable_fixture)

    return root


@pytest.fixture
def added_song_id(library_root: Path) -> str:
    """Create the real song that entry-registration tests will reference."""
    return create_song(library_root, "New Album Song").id


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


def test_create_album_rejects_unknown_song_without_creating_directory(
    library_root: Path,
) -> None:
    with pytest.raises(FileNotFoundError, match="Songs not found"):
        create_album(
            library_root,
            "Invalid Album",
            [SONG_IDS[0], UNKNOWN_SONG_ID],
        )

    assert list((library_root / "albums").iterdir()) == []


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


def test_register_album_session_shares_one_asset_across_entries(
    library_root: Path,
) -> None:
    original = create_album(library_root, "Connected Album", SONG_IDS)
    entry_ids = [entry.id for entry in original.sequences[0].entries]

    updated = register_album_session(
        library_root,
        original.id,
        "Continuous Reaper Session",
        "projects/continuous-album.rpp",
        entry_ids,
    )

    assert len(updated.assets) == 1
    session = updated.assets[0]
    assert session.kind == AssetKind.PROJECT
    assert session.purpose == AssetPurpose.ALBUM_SESSION
    assert session.title == "Continuous Reaper Session"
    storage = load_storage_manifest(library_root)
    assert session.location.storage_id == storage.id
    assert {entry.album_asset_id for entry in updated.sequences[0].entries} == {
        session.id
    }

    album_root = next((library_root / "albums").iterdir())
    assert (
        session.location.path
        == (
            album_root.relative_to(library_root) / "projects/continuous-album.rpp"
        ).as_posix()
    )
    assert load_album_manifest(album_root) == updated


def test_register_album_session_finds_album_after_other_albums(
    library_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_album(library_root, "A Unrelated Album", [])
    target = create_album(library_root, "Z Target Album", SONG_IDS)
    albums_root = library_root / "albums"
    original_iterdir = Path.iterdir

    def ordered_iterdir(path: Path):
        items = original_iterdir(path)
        if path == albums_root:
            return iter(sorted(items))
        return items

    monkeypatch.setattr(Path, "iterdir", ordered_iterdir)

    updated = register_album_session(
        library_root,
        target.id,
        "Target Session",
        "projects/target.rpp",
        [target.sequences[0].entries[0].id],
    )

    assert updated.id == target.id


def test_register_album_session_reports_unknown_album(
    library_root: Path,
) -> None:
    with pytest.raises(FileNotFoundError, match="Album not found"):
        register_album_session(
            library_root,
            "album_00000000-0000-4000-8000-000000000000",
            "Missing Session",
            "projects/missing.rpp",
            [],
        )


def test_register_album_session_rejects_unknown_entry_without_writing(
    library_root: Path,
) -> None:
    original = create_album(library_root, "Connected Album", SONG_IDS)
    album_root = next((library_root / "albums").iterdir())

    with pytest.raises(ValueError, match="Missing entry ids"):
        register_album_session(
            library_root,
            original.id,
            "Continuous Reaper Session",
            "projects/continuous-album.rpp",
            ["entry_00000000-0000-4000-8000-000000000000"],
        )

    assert load_album_manifest(album_root) == original


def test_add_album_entry_appends_to_primary_sequence_and_persists(
    library_root: Path,
    added_song_id: str,
) -> None:
    original = create_album(library_root, "Growing Album", SONG_IDS)
    album_root = next((library_root / "albums").iterdir())

    updated = add_album_entry(library_root, original.id, added_song_id)

    primary = next(
        sequence
        for sequence in updated.sequences
        if sequence.id == updated.primary_sequence_id
    )
    assert [entry.song_id for entry in primary.entries] == [
        *SONG_IDS,
        added_song_id,
    ]
    assert primary.entries[-1].id.startswith("entry_")
    assert load_album_manifest(album_root) == updated


def test_add_album_entry_uses_explicit_sequence(
    library_root: Path,
    added_song_id: str,
) -> None:
    original = create_album(library_root, "Alternate Order Album", SONG_IDS)
    album_root = next((library_root / "albums").iterdir())
    original.sequences.append(
        Sequence(id=ALTERNATE_SEQUENCE_ID, title="Alternate Sequence")
    )
    write_album_manifest(album_root, original)

    updated = add_album_entry(
        library_root,
        original.id,
        added_song_id,
        sequence_id=ALTERNATE_SEQUENCE_ID,
    )

    primary = next(
        sequence
        for sequence in updated.sequences
        if sequence.id == updated.primary_sequence_id
    )
    alternate = next(
        sequence
        for sequence in updated.sequences
        if sequence.id == ALTERNATE_SEQUENCE_ID
    )
    assert [entry.song_id for entry in primary.entries] == SONG_IDS
    assert [entry.song_id for entry in alternate.entries] == [added_song_id]


def test_add_album_entry_inserts_at_requested_position(
    library_root: Path,
    added_song_id: str,
) -> None:
    original = create_album(library_root, "Positioned Album", SONG_IDS)

    updated = add_album_entry(
        library_root,
        original.id,
        added_song_id,
        position=1,
    )

    assert [entry.song_id for entry in updated.sequences[0].entries] == [
        SONG_IDS[0],
        added_song_id,
        SONG_IDS[1],
    ]


@pytest.mark.parametrize("position", [-1, 3])
def test_add_album_entry_rejects_out_of_range_position_without_writing(
    library_root: Path,
    added_song_id: str,
    position: int,
) -> None:
    original = create_album(library_root, "Bounds Album", SONG_IDS)
    album_root = next((library_root / "albums").iterdir())

    with pytest.raises(ValueError, match="Position out of range"):
        add_album_entry(
            library_root,
            original.id,
            added_song_id,
            position=position,
        )

    assert load_album_manifest(album_root) == original


def test_add_album_entry_rejects_unknown_sequence_without_writing(
    library_root: Path,
    added_song_id: str,
) -> None:
    original = create_album(library_root, "Missing Sequence Album", SONG_IDS)
    album_root = next((library_root / "albums").iterdir())

    with pytest.raises(FileNotFoundError, match="Sequence not found"):
        add_album_entry(
            library_root,
            original.id,
            added_song_id,
            sequence_id=ALTERNATE_SEQUENCE_ID,
        )

    assert load_album_manifest(album_root) == original


def test_add_album_entry_rejects_unknown_album(
    library_root: Path,
    added_song_id: str,
) -> None:
    with pytest.raises(FileNotFoundError, match="Album not found"):
        add_album_entry(
            library_root,
            "album_00000000-0000-4000-8000-000000000000",
            added_song_id,
        )


def test_add_album_entry_rejects_unknown_song_without_writing(
    library_root: Path,
) -> None:
    original = create_album(library_root, "Missing Song Album", SONG_IDS)
    album_root = next((library_root / "albums").iterdir())

    with pytest.raises(FileNotFoundError, match="Song not found"):
        add_album_entry(library_root, original.id, UNKNOWN_SONG_ID)

    assert load_album_manifest(album_root) == original


def test_reorder_album_entry_moves_existing_entry_and_persists(
    library_root: Path,
) -> None:
    original = create_album(library_root, "Reordered Album", SONG_IDS)
    album_root = next((library_root / "albums").iterdir())
    original_entries = original.sequences[0].entries
    moved_entry_id = original_entries[0].id

    updated = reorder_album_entry(
        library_root,
        original.id,
        moved_entry_id,
        position=1,
    )

    assert [entry.id for entry in updated.sequences[0].entries] == [
        original_entries[1].id,
        moved_entry_id,
    ]
    assert load_album_manifest(album_root) == updated


def test_reorder_album_entry_targets_explicit_sequence(
    library_root: Path,
) -> None:
    original = create_album(library_root, "Alternate Reorder Album", SONG_IDS)
    album_root = next((library_root / "albums").iterdir())
    alternate_entries = [
        Entry(
            id="entry_11111111-1111-4111-8111-111111111111",
            song_id=SONG_IDS[0],
        ),
        Entry(
            id="entry_22222222-2222-4222-8222-222222222222",
            song_id=SONG_IDS[1],
        ),
    ]
    original.sequences.append(
        Sequence(
            id=ALTERNATE_SEQUENCE_ID,
            title="Alternate Sequence",
            entries=alternate_entries,
        )
    )
    write_album_manifest(album_root, original)

    updated = reorder_album_entry(
        library_root,
        original.id,
        alternate_entries[1].id,
        position=0,
        sequence_id=ALTERNATE_SEQUENCE_ID,
    )

    alternate = next(
        sequence
        for sequence in updated.sequences
        if sequence.id == ALTERNATE_SEQUENCE_ID
    )
    assert [entry.id for entry in alternate.entries] == [
        alternate_entries[1].id,
        alternate_entries[0].id,
    ]
    assert [entry.id for entry in updated.sequences[0].entries] == [
        entry.id for entry in original.sequences[0].entries
    ]


@pytest.mark.parametrize("position", [-1, 2])
def test_reorder_album_entry_rejects_invalid_position_without_writing(
    library_root: Path,
    position: int,
) -> None:
    original = create_album(library_root, "Invalid Reorder Album", SONG_IDS)
    album_root = next((library_root / "albums").iterdir())

    with pytest.raises(ValueError, match="Invalid position"):
        reorder_album_entry(
            library_root,
            original.id,
            original.sequences[0].entries[0].id,
            position=position,
        )

    assert load_album_manifest(album_root) == original


def test_remove_album_entry_removes_only_target_and_persists(
    library_root: Path,
) -> None:
    original = create_album(library_root, "Reduced Album", SONG_IDS)
    album_root = next((library_root / "albums").iterdir())
    removed_entry_id = original.sequences[0].entries[0].id
    remaining_entry = original.sequences[0].entries[1]

    updated = remove_album_entry(
        library_root,
        original.id,
        removed_entry_id,
    )

    assert updated.sequences[0].entries == [remaining_entry]
    assert load_album_manifest(album_root) == updated


@pytest.mark.parametrize("operation", [reorder_album_entry, remove_album_entry])
def test_album_entry_mutation_rejects_unknown_entry_without_writing(
    library_root: Path,
    operation,
) -> None:
    original = create_album(library_root, "Unknown Entry Album", SONG_IDS)
    album_root = next((library_root / "albums").iterdir())
    unknown_entry_id = "entry_00000000-0000-4000-8000-000000000000"

    with pytest.raises(FileNotFoundError, match="Entry not found"):
        if operation is reorder_album_entry:
            operation(
                library_root,
                original.id,
                unknown_entry_id,
                position=0,
            )
        else:
            operation(library_root, original.id, unknown_entry_id)

    assert load_album_manifest(album_root) == original


def test_update_album_metadata_applies_partial_changes_and_persists(
    library_root: Path,
) -> None:
    original = create_album(library_root, "Original Album Title", SONG_IDS)
    album_root = next((library_root / "albums").iterdir())

    updated = update_album_metadata(
        library_root,
        original.id,
        {
            "title": "Updated Album Title",
            "description": "Updated description",
            "tags": ["album", "continuous"],
        },
    )

    assert updated.title == "Updated Album Title"
    assert updated.description == "Updated description"
    assert updated.tags == ["album", "continuous"]
    assert album_root.name.endswith("Original Album Title")
    assert updated.created_at == original.created_at
    assert updated.updated_at >= original.updated_at
    assert updated.sequences == original.sequences
    assert load_album_manifest(album_root) == updated


def test_update_album_metadata_can_clear_description(
    library_root: Path,
) -> None:
    original = create_album(library_root, "Clearable Album", SONG_IDS)
    described = update_album_metadata(
        library_root,
        original.id,
        {"description": "Temporary description"},
    )

    cleared = update_album_metadata(
        library_root,
        original.id,
        {"description": None},
    )

    assert described.description == "Temporary description"
    assert cleared.description is None
    album_root = next((library_root / "albums").iterdir())
    assert load_album_manifest(album_root) == cleared


def test_update_album_metadata_empty_changes_leave_manifest_unchanged(
    library_root: Path,
) -> None:
    original = create_album(library_root, "Unchanged Album", SONG_IDS)

    assert update_album_metadata(library_root, original.id, {}) == original


def test_update_album_metadata_rejects_unknown_album(library_root: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Album not found"):
        update_album_metadata(
            library_root,
            "album_00000000-0000-4000-8000-000000000000",
            {"title": "Missing"},
        )
