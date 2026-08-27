# wiltware 2026
# filesystem layer for album library

from datetime import date, datetime
from pathlib import Path
import shutil
from uuid import uuid4


from domain.manifests import AlbumManifest, Asset, AssetKind, AssetLocation, AssetPurpose, Entry
from persistence.manifests import create_album_manifest, load_album_manifest, load_song_manifest, write_album_manifest
from persistence.storage import load_storage_manifest


def create_album(
    root: Path,
    title: str,
    song_ids: list[str]
) -> AlbumManifest:
    date = datetime.now().strftime("%Y%m%d")
    name = f"{date}_{title}"

    path = root / "albums" / name
    if path.exists():
        raise FileExistsError(f"Album already exists: {path}")
    path.mkdir()

    try:
        (path / "projects").mkdir()
        (path / "artwork").mkdir()
        (path / "exports").mkdir() #? do we want this?

        manifest = create_album_manifest(title=title, song_ids=song_ids)
        _ = write_album_manifest(path, manifest)
    except Exception:
        shutil.rmtree(path)
        raise

    return manifest

def list_albums(root: Path) -> list[AlbumManifest]:
    path = root / "albums"
    albums = []

    for album in path.iterdir():
        if not album.is_dir():
            continue #really this is an issue

        md = album / ".metadata.json"
        if not md.exists():
            continue

        albums.append(load_album_manifest(album))

    return albums

def register_album_session(
    root: Path,
    album_id: str,
    title: str,
    relative_path: str,
    entry_ids: list[str]
) -> AlbumManifest:
    albums_root = root / "albums"
    album_root = None
    manifest: AlbumManifest | None = None # TODO fix errors

    # find the right album
    for candidate in albums_root.iterdir():
        if not candidate.is_dir():
            continue

        metadata_path = candidate / ".metadata.json"
        if not metadata_path.is_file():
            continue

        candidate_manifest = load_album_manifest(candidate)

        if candidate_manifest.id == album_id:
            album_root = candidate
            manifest = candidate_manifest
            break

    if album_root is None or manifest is None:
        raise FileNotFoundError(f"Album not found: {album_id}")

    groups = [*manifest.sequences, *manifest.collections]
    entries_by_id = {
        entry.id: entry
        for group in groups
        for entry in group.entries
    }

    missing_entry_ids = [
        entry_id
        for entry_id in entry_ids
        if entry_id not in entries_by_id
    ]

    if missing_entry_ids:
        raise ValueError(f"Missing entry ids: {missing_entry_ids}")

    storage_relative_path = (
        album_root.relative_to(root) / relative_path
    ).as_posix()
    
    session_asset = Asset(
        id=f"asset_{uuid4()}",
        kind=AssetKind.PROJECT,
        purpose=AssetPurpose.ALBUM_SESSION,
        title=title,
        location=AssetLocation(
            storage_id=load_storage_manifest(root).id,
            path=storage_relative_path,
        ),
    )

    manifest.assets.append(session_asset)
    for entry_id in entry_ids:
        entries_by_id[entry_id].album_asset_id = session_asset.id

    manifest.updated_at = datetime.now().astimezone()

    validated_manifest = AlbumManifest.model_validate(
        manifest.model_dump(mode="python")
    )

    write_album_manifest(album_root, validated_manifest)

    return validated_manifest

def add_album_entry(
    root: Path,
    album_id: str,
    song_id: str,
    sequence_id: str | None = None,
    position: int | None = None
) -> AlbumManifest:
    albums_root = root / "albums"
    manifest: AlbumManifest | None = None
    album_root: Path | None = None

    # verify song id
    songs_root = root / "songs"
    for entry in songs_root.iterdir():
        if not entry.is_dir():
            continue

        md = entry / ".metadata.json"
        if not md.exists():
            continue

        candidate = load_song_manifest(entry)
        if candidate.id == song_id:
            # we found it!
            break

    else:
        raise FileNotFoundError(f"Song not found: {song_id}")


    # get album manifest
    for entry in albums_root.iterdir():
        if not entry.is_dir():
            continue

        md = entry / ".metadata.json"
        if not md.exists():
            continue

        candidate = load_album_manifest(entry)
        if candidate.id == album_id:
            album_root = entry
            manifest = candidate
            break


    # connect song to album manifest
    if manifest is None:
        raise FileNotFoundError(f"Album not found: {album_id}")

    new_entry = Entry(
        id=f"entry_{uuid4()}",
        song_id=song_id
    )

    target_sequence_id = sequence_id or manifest.primary_sequence_id

    target_sequence = next(
        (
            sequence
            for sequence in manifest.sequences
            if sequence.id == target_sequence_id
        ),
        None
    )

    if target_sequence is None:
        raise FileNotFoundError(f"Sequence not found: {target_sequence_id}")

    if position is None:
        target_sequence.entries.append(new_entry)
    else:
        if position < 0 or position > len(target_sequence.entries):
            raise ValueError(f"Position out of range: {position}")
        target_sequence.entries.insert(position, new_entry)

    manifest.updated_at = datetime.now().astimezone()

    validated_manifest = AlbumManifest.model_validate(
        manifest.model_dump(mode="python")
    )

    if album_root is None:
        raise ValueError("Album root not found")

    _ = write_album_manifest(album_root, validated_manifest)

    return validated_manifest

def reorder_album_entry(
    root: Path,
    album_id: str,
    entry_id: str,
    position: int,
    sequence_id: str | None = None,
    ) -> AlbumManifest:

    albums_root = root / "albums"
    album_root: Path | None = None
    manifest: AlbumManifest | None = None

    for album in albums_root.iterdir():
        if not album.is_dir():
            continue

        md = album / ".metadata.json"
        if not md.exists():
            continue

        candidate = load_album_manifest(album)
        if candidate is None:
            continue

        if candidate.id == album_id:
            album_root = album
            manifest = candidate
            break

    if manifest is None:
        raise FileNotFoundError(f"Album not found: {album_id}")

    if sequence_id is None:
       sequence_id = manifest.primary_sequence_id

    target_sequence = next(
        (
            sequence
            for sequence in manifest.sequences
            if sequence.id == sequence_id
        ),
        None
    )

    if target_sequence is None:
        raise ValueError(f"Sequence not found: {sequence_id}")

    target_entry: Entry | None = next(
        (
            entry
            for entry in target_sequence.entries
            if entry.id == entry_id
        ),
        None
    )

    if target_entry is None:
        raise FileNotFoundError(f"Entry not found: {entry_id}")

    if position < 0 or position >= len(target_sequence.entries):
        raise ValueError(f"Invalid position: {position}")

    # move target entry in sequence array
    target_sequence.entries.remove(target_entry)
    target_sequence.entries.insert(position, target_entry)

    manifest.updated_at = datetime.now().astimezone()

    validated_manifest = AlbumManifest.model_validate(
        manifest.model_dump(mode="python")
    )

    if album_root is None:
        raise FileNotFoundError("Album root not found")

    _ = write_album_manifest(album_root, validated_manifest)

    return validated_manifest

def remove_album_entry(
    root: Path,
    album_id: str,
    entry_id: str,
    sequence_id: str | None = None,
    ) -> AlbumManifest:

    albums_root = root / "albums"
    album_root: Path | None = None
    manifest: AlbumManifest | None = None

    for album in albums_root.iterdir():
        if not album.is_dir():
            continue

        md = album / ".metadata.json"
        if not md.exists():
            continue

        candidate = load_album_manifest(album)
        if candidate is None:
            continue

        if candidate.id == album_id:
            album_root = album
            manifest = candidate
            break

    if manifest is None:
        raise FileNotFoundError(f"Album not found: {album_id}")

    if sequence_id is None:
       sequence_id = manifest.primary_sequence_id

    target_sequence = next(
        (
            sequence
            for sequence in manifest.sequences
            if sequence.id == sequence_id
        ),
        None
    )

    if target_sequence is None:
        raise ValueError(f"Sequence not found: {sequence_id}")

    target_entry: Entry | None = next(
        (
            entry
            for entry in target_sequence.entries
            if entry.id == entry_id
        ),
        None
    )

    if target_entry is None:
        raise FileNotFoundError(f"Entry not found: {entry_id}")

    # remove target entry in sequence array
    target_sequence.entries.remove(target_entry)

    manifest.updated_at = datetime.now().astimezone()

    validated_manifest = AlbumManifest.model_validate(
        manifest.model_dump(mode="python")
    )

    if album_root is None:
        raise FileNotFoundError("Album root not found")

    _ = write_album_manifest(album_root, validated_manifest)

    return validated_manifest
