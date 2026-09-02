# Authored by ChatGPT on 2026-09-01.

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from domain.manifests import (
    AlbumManifest,
    Asset,
    AssetKind,
    AssetLocation,
    AssetPurpose,
    Entry,
    Sequence,
    SongManifest,
)
from persistence.manifests import (
    METADATA_FILENAME,
    write_album_manifest,
    write_song_manifest,
)
from persistence.storage import load_storage_manifest

LEGACY_BACKUP_FILENAME = ".metadata.v1.json"


class LegacyModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class LegacyPath(LegacyModel):
    path: str


class LegacySongManifest(LegacyModel):
    slug: str
    title: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    timezone: str | None = None
    lyrics: list[LegacyPath] = Field(default_factory=list)
    projects: list[LegacyPath] = Field(default_factory=list)
    default_project: str | None = None
    renders: list[LegacyPath] = Field(default_factory=list)
    created_at: datetime
    modified_at: datetime


class LegacyTrack(LegacyModel):
    slug: str
    number: int | None = None


class LegacyAlbumManifest(LegacyModel):
    slug: str
    title: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    timezone: str | None = None
    tracklist: list[LegacyTrack] = Field(default_factory=list)
    created_at: datetime
    modified_at: datetime


@dataclass
class MigrationReport:
    dry_run: bool
    songs: list[Path] = field(default_factory=list)
    albums: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)
    backups: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    applied: bool = False

    @property
    def can_apply(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class _PlannedSongWrite:
    directory: Path
    manifest: SongManifest


@dataclass(frozen=True)
class _PlannedAlbumWrite:
    directory: Path
    manifest: AlbumManifest


def _stable_id(prefix: str, storage_id: str, *parts: object) -> str:
    identity = json.dumps(
        ["mdo", "v1-migration", storage_id, prefix, *parts],
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    uuid_bytes = bytearray(hashlib.sha256(identity).digest()[:16])
    uuid_bytes[6] = (uuid_bytes[6] & 0x0F) | 0x40
    uuid_bytes[8] = (uuid_bytes[8] & 0x3F) | 0x80
    return f"{prefix}_{UUID(bytes=bytes(uuid_bytes))}"


def _read_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _schema_version(data: object) -> int | None:
    if not isinstance(data, dict):
        return None

    value = data.get("schema_version")
    return value if isinstance(value, int) else None


def _legacy_project_paths(manifest: LegacySongManifest) -> list[str]:
    paths = [project.path for project in manifest.projects]

    if manifest.default_project is not None:
        paths.append(manifest.default_project)

    return list(dict.fromkeys(paths))


def _migrate_song(
    root: Path,
    song_path: Path,
    legacy: LegacySongManifest,
    storage_id: str,
    report: MigrationReport,
) -> SongManifest:
    song_id = _stable_id("song", storage_id, song_path.name)
    assets: list[Asset] = []
    asset_ids_by_legacy_path: dict[str, str] = {}

    for legacy_path in _legacy_project_paths(legacy):
        relative_path = PurePosixPath(legacy_path)
        storage_path = (
            PurePosixPath(song_path.relative_to(root).as_posix()) / relative_path
        ).as_posix()
        asset_id = _stable_id("asset", storage_id, song_path.name, legacy_path)
        asset_ids_by_legacy_path[legacy_path] = asset_id
        assets.append(
            Asset(
                id=asset_id,
                kind=AssetKind.PROJECT,
                purpose=AssetPurpose.SONG_SESSION,
                title=relative_path.name or "Project",
                location=AssetLocation(
                    storage_id=storage_id,
                    path=storage_path,
                ),
            )
        )

        if not (root / storage_path).exists():
            report.warnings.append(
                f"{song_path}: project is referenced but unavailable: {legacy_path}"
            )

    if legacy.lyrics or legacy.renders:
        report.warnings.append(
            f"{song_path}: legacy lyrics/renders remain on disk and are not "
            "persisted as v2 assets"
        )

    if legacy.slug != song_path.name:
        report.warnings.append(
            f"{song_path}: legacy slug differs from directory name: {legacy.slug}"
        )

    if legacy.model_extra:
        report.warnings.append(
            f"{song_path}: unrecognized legacy fields remain in the backup only: "
            f"{sorted(legacy.model_extra)}"
        )

    default_project_id = (
        asset_ids_by_legacy_path.get(legacy.default_project)
        if legacy.default_project is not None
        else None
    )

    return SongManifest(
        schema_version=2,
        id=song_id,
        title=legacy.title,
        description=legacy.description,
        tags=legacy.tags,
        assets=assets,
        default_project_id=default_project_id,
        created_at=legacy.created_at,
        updated_at=legacy.modified_at,
    )


def _migrate_album(
    album_path: Path,
    legacy: LegacyAlbumManifest,
    storage_id: str,
    song_ids_by_slug: dict[str, str],
    report: MigrationReport,
) -> AlbumManifest:
    album_id = _stable_id("album", storage_id, album_path.name)
    sequence_id = _stable_id("sequence", storage_id, album_path.name, "primary")
    entries = [
        Entry(
            id=_stable_id(
                "entry",
                storage_id,
                album_path.name,
                index,
                track.slug,
            ),
            song_id=song_ids_by_slug[track.slug],
        )
        for index, track in enumerate(legacy.tracklist)
    ]

    if legacy.model_extra:
        report.warnings.append(
            f"{album_path}: unrecognized legacy fields remain in the backup only: "
            f"{sorted(legacy.model_extra)}"
        )

    return AlbumManifest(
        schema_version=2,
        id=album_id,
        title=legacy.title,
        description=legacy.description,
        tags=legacy.tags,
        primary_sequence_id=sequence_id,
        sequences=[
            Sequence(
                id=sequence_id,
                title="Main Album",
                entries=entries,
            )
        ],
        created_at=legacy.created_at,
        updated_at=legacy.modified_at,
    )


def _register_song_slug(
    mapping: dict[str, str],
    slug: str,
    song_id: str,
    path: Path,
    report: MigrationReport,
) -> None:
    existing = mapping.get(slug)

    if existing is not None and existing != song_id:
        report.errors.append(f"{path}: duplicate legacy song slug: {slug}")
        return

    mapping[slug] = song_id


def _backup_manifest(metadata_path: Path) -> Path:
    backup_path = metadata_path.with_name(LEGACY_BACKUP_FILENAME)

    with metadata_path.open("rb") as source, backup_path.open("xb") as backup:
        shutil.copyfileobj(source, backup)
        backup.flush()
        os.fsync(backup.fileno())

    return backup_path


def migrate_library_v1_to_v2(
    root: Path,
    *,
    dry_run: bool = True,
) -> MigrationReport:
    root = root.resolve()
    storage = load_storage_manifest(root)
    report = MigrationReport(dry_run=dry_run)
    song_ids_by_slug: dict[str, str] = {}
    song_plans: list[_PlannedSongWrite] = []
    album_plans: list[_PlannedAlbumWrite] = []

    for song_path in sorted((root / "songs").iterdir()):
        if not song_path.is_dir():
            continue

        metadata_path = song_path / METADATA_FILENAME
        if not metadata_path.is_file():
            report.errors.append(f"{song_path}: song metadata is missing")
            continue

        try:
            data = _read_json(metadata_path)
            version = _schema_version(data)

            if version == 2:
                manifest = SongManifest.model_validate(data)
                report.skipped.append(metadata_path)
                _register_song_slug(
                    song_ids_by_slug,
                    song_path.name,
                    manifest.id,
                    song_path,
                    report,
                )
                continue

            if version not in {None, 1}:
                report.errors.append(
                    f"{metadata_path}: unsupported song schema version: {version}"
                )
                continue

            legacy = LegacySongManifest.model_validate(data)
            manifest = _migrate_song(
                root,
                song_path,
                legacy,
                storage.id,
                report,
            )
        except (OSError, json.JSONDecodeError, ValidationError, ValueError) as error:
            report.errors.append(f"{metadata_path}: {error}")
            continue

        _register_song_slug(
            song_ids_by_slug,
            song_path.name,
            manifest.id,
            song_path,
            report,
        )
        _register_song_slug(
            song_ids_by_slug,
            legacy.slug,
            manifest.id,
            song_path,
            report,
        )
        song_plans.append(_PlannedSongWrite(song_path, manifest))
        report.songs.append(metadata_path)

    for album_path in sorted((root / "albums").iterdir()):
        if not album_path.is_dir():
            continue

        metadata_path = album_path / METADATA_FILENAME
        if not metadata_path.is_file():
            report.errors.append(f"{album_path}: album metadata is missing")
            continue

        try:
            data = _read_json(metadata_path)
            version = _schema_version(data)

            if version == 2:
                AlbumManifest.model_validate(data)
                report.skipped.append(metadata_path)
                continue

            if version not in {None, 1}:
                report.errors.append(
                    f"{metadata_path}: unsupported album schema version: {version}"
                )
                continue

            legacy = LegacyAlbumManifest.model_validate(data)
            missing_slugs = [
                track.slug
                for track in legacy.tracklist
                if track.slug not in song_ids_by_slug
            ]
            if missing_slugs:
                report.errors.append(
                    f"{metadata_path}: unresolved song slugs: "
                    f"{list(dict.fromkeys(missing_slugs))}"
                )
                continue

            manifest = _migrate_album(
                album_path,
                legacy,
                storage.id,
                song_ids_by_slug,
                report,
            )
        except (OSError, json.JSONDecodeError, ValidationError, ValueError) as error:
            report.errors.append(f"{metadata_path}: {error}")
            continue

        album_plans.append(_PlannedAlbumWrite(album_path, manifest))
        report.albums.append(metadata_path)

    plans = [*song_plans, *album_plans]

    for plan in plans:
        backup_path = plan.directory / LEGACY_BACKUP_FILENAME
        if backup_path.exists():
            report.errors.append(f"{backup_path}: legacy backup already exists")

    if report.errors or dry_run:
        return report

    for plan in plans:
        report.backups.append(
            _backup_manifest(plan.directory / METADATA_FILENAME)
        )

    for plan in song_plans:
        write_song_manifest(plan.directory, plan.manifest)

    for plan in album_plans:
        write_album_manifest(plan.directory, plan.manifest)

    report.applied = True
    return report


def _print_report(report: MigrationReport) -> None:
    mode = "dry run" if report.dry_run else "apply"
    print(f"migration mode: {mode}")
    print(f"songs planned: {len(report.songs)}")
    print(f"albums planned: {len(report.albums)}")
    print(f"schema-2 manifests skipped: {len(report.skipped)}")

    for warning in report.warnings:
        print(f"warning: {warning}")

    for error in report.errors:
        print(f"error: {error}")

    if report.applied:
        print(f"migration applied; backups created: {len(report.backups)}")
    elif report.can_apply and report.dry_run:
        print("dry run passed; rerun with --apply to write changes")
    else:
        print("migration was not applied")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Translate legacy MDO manifests to schema version 2."
    )
    parser.add_argument("root", type=Path, help="MDO storage root")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="back up and replace legacy manifests; otherwise perform a dry run",
    )
    arguments = parser.parse_args(argv)

    report = migrate_library_v1_to_v2(
        arguments.root,
        dry_run=not arguments.apply,
    )
    _print_report(report)
    return 0 if report.can_apply else 1


if __name__ == "__main__":
    sys.exit(main())
