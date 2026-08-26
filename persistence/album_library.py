# wiltware 2026
# filesystem layer for albnum library

from datetime import datetime
from pathlib import Path
import shutil

from domain.manifests import AlbumManifest, SongManifest
from persistence.manifests import create_album_manifest, load_album_manifest, write_album_manifest


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
    