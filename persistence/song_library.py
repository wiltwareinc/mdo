# wiltware 2026
# new song creation/edit file management

import shutil
from datetime import datetime
from pathlib import Path
from typing import TypedDict
from uuid import uuid4

from domain.manifests import Asset, AssetKind, AssetLocation, AssetPurpose, SongManifest
from persistence.manifests import (
    create_song_manifest,
    load_song_manifest,
    write_song_manifest,
)
from persistence.storage import load_storage_manifest

def _validate_return_manifest(manifest: SongManifest, song_path: Path) -> SongManifest:
    manifest.updated_at = datetime.now().astimezone()

    validated_manifest = SongManifest.model_validate(manifest.model_dump(mode="python"))

    _ = write_song_manifest(song_path, validated_manifest)

    return validated_manifest

def create_song(root: Path, title: str) -> SongManifest:
    date = datetime.now().astimezone().strftime("%Y%m%d")
    name = f"{date}_{title}"
    # ensure that it current is valid within the root
    path = root / "songs" / name
    if path.exists():
        # error
        raise FileExistsError(f"Song already exists: {path}")
    path.mkdir()
    # create lyrics/ projects/ and renders/
    try:
        (path / "lyrics").mkdir()
        (path / "projects").mkdir()
        (path / "renders").mkdir()

        manifest = create_song_manifest(title=title)
        _ = write_song_manifest(path, manifest)
    except Exception:
        shutil.rmtree(path)  # clean up!
        raise

    return manifest


def list_songs(root: Path) -> list[SongManifest]:
    path = root / "songs"
    songs: list[SongManifest] = []
    for song in path.iterdir():
        if not song.is_dir():
            continue

        md = song / ".metadata.json"
        if not md.exists():
            continue

        songs.append(load_song_manifest(song))

    return songs


def _find_song(root: Path, song_id: str) -> tuple[SongManifest, Path]:
    songs_root = root / "songs"

    for song_path in songs_root.iterdir():
        if not song_path.is_dir():
            continue

        md = song_path / ".metadata.json"
        if not md.exists():
            continue

        manifest = load_song_manifest(song_path)
        if manifest.id == song_id:
            return manifest, song_path

    raise FileNotFoundError(f"Song not found: {song_id}")


def get_song(root: Path, song_id: str) -> SongManifest:
    manifest, _ = _find_song(root, song_id)
    return manifest


def register_song_project(
    root: Path,
    song_id: str,
    title: str,
    relative_path: str,
    parent_song: str | None = None,
    make_default: bool = True,
) -> SongManifest:
    """Register a new or shared project with a song.

    Without ``parent_song``, the project is resolved relative to the target
    song and a new asset identity is created. With ``parent_song``, an existing
    project asset is found in that song and its complete identity and location
    are reused in the target song.

    Args:
        root:
            Root directory of the active MDO storage. This directory contains
            ``.storage.json`` and the ``songs`` directory.

        song_id:
            Stable ID of the song receiving the project asset.

        title:
            Human-readable name used when creating a new asset. When sharing
            an existing asset, its original title is preserved.

        relative_path:
            Path to the project relative to the target song, or relative to
            ``parent_song`` when sharing an existing project.

        parent_song:
            Optional stable ID of the song whose registered project should be
            shared with the target song.

        make_default:
            Whether the newly created asset should become the song's default
            project. Defaults to True.

    Returns:
        The validated and persisted SongManifest containing the new asset.

    Raises:
        FileNotFoundError:
            If the target song, parent song, storage identity, registered
            parent asset, or project path does not exist.

        ValueError:
            If the generated asset location or updated song manifest is
            invalid.
    """
    songs_root = root / "songs"
    song_path: Path | None = None
    manifest: SongManifest | None = None
    parent_path: Path | None = None
    parent_manifest: SongManifest | None = None

    # Locate the target song and, when requested, the song owning the asset.
    for song in songs_root.iterdir():
        if not song.is_dir():
            continue

        md = song / ".metadata.json"
        if not md.exists():
            continue

        candidate = load_song_manifest(song)
        if candidate.id == song_id:
            manifest = candidate
            song_path = song

        if parent_song is not None and candidate.id == parent_song:
            parent_manifest = candidate
            parent_path = song

        if song_path is not None and (
            parent_song is None or parent_manifest is not None
        ):
            break

    if parent_song is not None and parent_manifest is None:
        raise FileNotFoundError(f"Parent song not found: {parent_song}")

    if song_path is None or manifest is None:
        raise FileNotFoundError(f"Song not found: {song_id}")

    storage = load_storage_manifest(root)

    if parent_manifest is not None and parent_path is not None:
        parent_storage_path = (parent_path.relative_to(root) / relative_path).as_posix()
        parent_asset = next(
            (
                candidate
                for candidate in parent_manifest.assets
                if candidate.kind == AssetKind.PROJECT
                and candidate.location.storage_id == storage.id
                and candidate.location.path == parent_storage_path
            ),
            None,
        )
        if parent_asset is None:
            raise FileNotFoundError(
                f"Parent song does not contain project at {relative_path}"
            )

        asset = parent_asset.model_copy(deep=True)
    else:
        storage_relative_path = (song_path.relative_to(root) / relative_path).as_posix()
        asset = Asset(
            id=f"asset_{uuid4()}",
            kind=AssetKind.PROJECT,
            purpose=AssetPurpose.SONG_SESSION,
            title=title,
            location=AssetLocation(
                storage_id=storage.id,
                path=storage_relative_path,
            ),
        )

    project_path = root / asset.location.path
    if not project_path.exists():
        raise FileNotFoundError(f"Project not found: {project_path}")

    existing_asset = next(
        (candidate for candidate in manifest.assets if candidate.id == asset.id),
        None,
    )
    if existing_asset is None:
        manifest.assets.append(asset)
    elif existing_asset != asset:
        raise ValueError(f"Asset ID has conflicting metadata: {asset.id}")
    else:
        asset = existing_asset

    if make_default:
        manifest.default_project_id = asset.id

    manifest.updated_at = datetime.now().astimezone()

    validated_manifest = SongManifest.model_validate(manifest.model_dump(mode="python"))

    _ = write_song_manifest(song_path, validated_manifest)

    return validated_manifest

class SongMetaDataChanges(TypedDict, total=False):
    title: str
    description: str | None
    tags: list[str]
    default_project_id: str | None


def update_song_metadata(
    root: Path,
    song_id: str,
    changes: SongMetaDataChanges
) -> SongManifest:
    """Updates the metadata for a given song.

    Args:
        root: Given root of the storage media
        song_id: UUID of the given song
        changes: Dictionary of allowed changes:
            - title
            - description
            - tags
            - default_project_id

    Returns:
        Updated SongManifest
    """
    # find song
    manifest, song_path = _find_song(root, song_id)

    # supposedly, because this is coming from the API, we need a dynamic
    # checker to ensure that the unexpected fields are good
    allowed_fields = {
        "title",
        "description",
        "tags",
        "default_project_id"
    }

    unexpected_fields = changes.keys() - allowed_fields
    if unexpected_fields:
        raise ValueError(f"Unexpected fields: {unexpected_fields}")

    if not changes:
        return manifest

    if "title" in changes:
        manifest.title = changes["title"]
    if "description" in changes:
        manifest.description = changes["description"]
    if "tags" in changes:
        manifest.tags = changes["tags"]
    if "default_project_id" in changes:
        manifest.default_project_id = changes["default_project_id"]

    # validate manifest

    return _validate_return_manifest(manifest, song_path)
