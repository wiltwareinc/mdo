"""Test safe translation of legacy MDO manifests into schema version 2.

These tests cover dry runs, exact backups, song assets and defaults, ordered
album references, unresolved slugs, unsafe legacy paths, existing backups,
and repeatable migration. Every test operates on a temporary library.

Authored by ChatGPT on 2026-09-01.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from persistence.manifests import load_album_manifest, load_song_manifest
from persistence.migration_v1 import (
    LEGACY_BACKUP_FILENAME,
    main,
    migrate_library_v1_to_v2,
)
from persistence.storage import initialize_storage

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "manifests_v1"


@pytest.fixture
def legacy_library(tmp_path: Path) -> Path:
    root = tmp_path / "legacy-music"
    initialize_storage(root, "Legacy Test Library")

    first_song = root / "songs" / "20240102-first-song"
    second_song = root / "songs" / "20240103-second-song"
    album = root / "albums" / "20240201-connected-album"

    for directory in (first_song, second_song, album):
        directory.mkdir()

    shutil.copy2(FIXTURE_ROOT / "song.json", first_song / ".metadata.json")
    shutil.copy2(
        FIXTURE_ROOT / "song_no_projects.json",
        second_song / ".metadata.json",
    )
    shutil.copy2(FIXTURE_ROOT / "album.json", album / ".metadata.json")

    (first_song / "lyrics").mkdir()
    (first_song / "lyrics" / "first-song.txt").touch()
    (first_song / "projects" / "main-session").mkdir(parents=True)
    (first_song / "projects" / "alternate-session").mkdir()
    (first_song / "renders").mkdir()
    (first_song / "renders" / "first-mix.wav").touch()

    return root


def test_migration_dry_run_reports_work_without_writing(
    legacy_library: Path,
) -> None:
    metadata_paths = sorted(legacy_library.glob("*/**/.metadata.json"))
    original_contents = {path: path.read_bytes() for path in metadata_paths}

    report = migrate_library_v1_to_v2(legacy_library)

    assert report.dry_run is True
    assert report.applied is False
    assert report.can_apply is True
    assert len(report.songs) == 2
    assert len(report.albums) == 1
    assert report.backups == []
    assert any("lyrics/renders remain on disk" in item for item in report.warnings)
    assert {path: path.read_bytes() for path in metadata_paths} == original_contents
    assert not list(legacy_library.glob(f"*/**/{LEGACY_BACKUP_FILENAME}"))


def test_migration_applies_song_assets_album_order_and_exact_backups(
    legacy_library: Path,
) -> None:
    first_root = legacy_library / "songs" / "20240102-first-song"
    second_root = legacy_library / "songs" / "20240103-second-song"
    album_root = legacy_library / "albums" / "20240201-connected-album"
    roots = [first_root, second_root, album_root]
    original_contents = {
        root: (root / ".metadata.json").read_bytes() for root in roots
    }

    report = migrate_library_v1_to_v2(legacy_library, dry_run=False)

    assert report.applied is True
    assert report.errors == []
    assert len(report.backups) == 3
    for entity_root in roots:
        assert (
            entity_root / LEGACY_BACKUP_FILENAME
        ).read_bytes() == original_contents[entity_root]

    first = load_song_manifest(first_root)
    second = load_song_manifest(second_root)
    album = load_album_manifest(album_root)

    assert first.schema_version == 2
    assert first.title == "First Song"
    assert first.description == "A legacy description."
    assert first.tags == ["legacy", "connected"]
    assert first.created_at.isoformat() == "2024-01-02T00:00:00-05:00"
    assert first.updated_at.isoformat() == "2024-02-03T14:30:00-05:00"
    assert len(first.assets) == 2
    assert first.default_project_id is not None
    default = next(
        asset for asset in first.assets if asset.id == first.default_project_id
    )
    assert default.location.path == (
        "songs/20240102-first-song/projects/main-session"
    )
    assert {asset.location.path for asset in first.assets} == {
        "songs/20240102-first-song/projects/main-session",
        "songs/20240102-first-song/projects/alternate-session",
    }
    assert second.assets == []
    assert [entry.song_id for entry in album.sequences[0].entries] == [
        second.id,
        first.id,
    ]
    assert album.description == "A connected legacy record."
    assert album.tags == ["album"]
    assert first_root.name == "20240102-first-song"
    assert album_root.name == "20240201-connected-album"


def test_migration_aborts_every_write_for_unresolved_album_song(
    legacy_library: Path,
) -> None:
    album_metadata = (
        legacy_library / "albums" / "20240201-connected-album" / ".metadata.json"
    )
    album_data = json.loads(album_metadata.read_text(encoding="utf-8"))
    album_data["tracklist"].append({"slug": "missing-song", "number": 3})
    album_metadata.write_text(json.dumps(album_data), encoding="utf-8")

    report = migrate_library_v1_to_v2(legacy_library, dry_run=False)

    assert report.applied is False
    assert any("unresolved song slugs" in error for error in report.errors)
    assert not list(legacy_library.glob(f"*/**/{LEGACY_BACKUP_FILENAME}"))
    first_metadata = (
        legacy_library / "songs" / "20240102-first-song" / ".metadata.json"
    )
    assert "schema_version" not in json.loads(first_metadata.read_text())


def test_migration_rejects_escaping_legacy_project_path_without_writing(
    legacy_library: Path,
) -> None:
    song_metadata = (
        legacy_library / "songs" / "20240102-first-song" / ".metadata.json"
    )
    song_data = json.loads(song_metadata.read_text(encoding="utf-8"))
    song_data["projects"].append({"path": "../../outside-project"})
    song_metadata.write_text(json.dumps(song_data), encoding="utf-8")

    report = migrate_library_v1_to_v2(legacy_library, dry_run=False)

    assert report.applied is False
    assert any("must not escape storage" in error for error in report.errors)
    assert not list(legacy_library.glob(f"*/**/{LEGACY_BACKUP_FILENAME}"))


def test_migration_refuses_to_overwrite_existing_backup(
    legacy_library: Path,
) -> None:
    first_root = legacy_library / "songs" / "20240102-first-song"
    backup = first_root / LEGACY_BACKUP_FILENAME
    backup.write_text("existing backup", encoding="utf-8")

    report = migrate_library_v1_to_v2(legacy_library, dry_run=False)

    assert report.applied is False
    assert any("legacy backup already exists" in error for error in report.errors)
    assert backup.read_text(encoding="utf-8") == "existing backup"
    assert not (
        legacy_library
        / "songs"
        / "20240103-second-song"
        / LEGACY_BACKUP_FILENAME
    ).exists()


def test_completed_migration_can_be_run_again_safely(
    legacy_library: Path,
) -> None:
    first = migrate_library_v1_to_v2(legacy_library, dry_run=False)

    second = migrate_library_v1_to_v2(legacy_library, dry_run=False)

    assert first.applied is True
    assert second.applied is True
    assert second.errors == []
    assert len(second.skipped) == 3
    assert second.songs == []
    assert second.albums == []
    assert second.backups == []


def test_migration_reports_unrecognized_legacy_fields(
    legacy_library: Path,
) -> None:
    song_metadata = (
        legacy_library / "songs" / "20240102-first-song" / ".metadata.json"
    )
    song_data = json.loads(song_metadata.read_text(encoding="utf-8"))
    song_data["custom_note"] = "preserve me in the backup"
    song_metadata.write_text(json.dumps(song_data), encoding="utf-8")

    report = migrate_library_v1_to_v2(legacy_library)

    assert any("custom_note" in warning for warning in report.warnings)


def test_migration_command_defaults_to_dry_run(
    legacy_library: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = main([str(legacy_library)])

    output = capsys.readouterr().out
    assert result == 0
    assert "migration mode: dry run" in output
    assert "rerun with --apply" in output
    assert not list(legacy_library.glob(f"*/**/{LEGACY_BACKUP_FILENAME}"))
