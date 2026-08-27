# wiltware 2026
# new song creation/edit file management

import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from domain.manifests import Asset, AssetKind, AssetLocation, AssetPurpose, SongManifest
from persistence.manifests import (
    create_song_manifest,
    load_song_manifest,
    write_song_manifest,
)
from persistence.storage import load_storage_manifest


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


def get_song(root: Path, song_id: str) -> SongManifest:
    songs_root = root / "songs"

    for song_path in songs_root.iterdir():
        if not song_path.is_dir():
            continue

        md = song_path / ".metadata.json"
        if not md.exists():
            continue

        manifest = load_song_manifest(song_path)
        if manifest.id == song_id:
            return manifest

    raise FileNotFoundError(f"Song not found: {song_id}")


def register_song_project(
    root: Path, song_id: str, title: str, relative_path: str, make_default: bool = True
) -> SongManifest:
    songs_root = root / "songs"
    song_path: Path | None = None
    manifest: SongManifest | None = None

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
            break

    if song_path is None or manifest is None:
        raise FileNotFoundError(f"Song not found: {song_id}")

    storage = load_storage_manifest(root)

    storage_relative_path = (song_path.relative_to(root) / relative_path).as_posix()

    location = AssetLocation(storage_id=storage.id, path=storage_relative_path)

    project_path = root / location.path
    if not project_path.exists():
        raise FileNotFoundError(f"Project not found: {project_path}")

    asset = Asset(
        id=f"asset_{uuid4()}",
        kind=AssetKind.PROJECT,
        purpose=AssetPurpose.SONG_SESSION,
        title=title,
        location=location,
    )

    manifest.assets.append(asset)  # add to the bunch

    if make_default:
        manifest.default_project_id = asset.id

    manifest.updated_at = datetime.now().astimezone()

    validated_manifest = SongManifest.model_validate(manifest.model_dump(mode="python"))

    _ = write_song_manifest(song_path, validated_manifest)

    return validated_manifest
