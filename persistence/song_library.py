# wiltware 2026
# new song creation/edit file management

from datetime import datetime
from pathlib import Path
import shutil

from domain.manifests import SongManifest
from persistence.manifests import create_song_manifest, load_song_manifest, write_song_manifest


def create_song(root: Path, title: str) -> SongManifest:
    date = datetime.now().strftime("%Y%m%d")
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
        shutil.rmtree(path) # clean up!
        raise
    
    return manifest

def list_songs(root: Path) -> list[SongManifest]:
    path = root / "songs"
    songs = []
    for song in path.iterdir():
        if not song.is_dir():
            continue
        
        md = song / ".metadata.json"
        if not md.exists():
            continue
        
        songs.append(load_song_manifest(song))


    return songs
    