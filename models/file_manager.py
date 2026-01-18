# wiltware
# essentially the backend with filesystems
import json
import logging
import re
import sys
from pathlib import Path

from typing_extensions import Any, Dict, List, Optional


class FileManager:
    def __init__(self, droot: Path) -> None:
        if not droot:
            logging.error("No root provided. Unable to continue.")
            sys.exit(1)
        self.droot = droot
        # array of albums (slug, title, tracklist (in slugs), created, modified)
        self.albums = []
        # array of songs (in terms of (slug, name, # of lyrics, # of projects, # of renders, creation date, modified date)
        self.songs = self.read_songs()

    def read_songs(self) -> List[Dict[str, Any]]:
        # should be in root/songs
        songs_path: Path = self.droot / "songs"
        songs: List[Dict[str, Any]] = []
        if not songs_path.exists():
            # ? should it auto create?
            logging.error("No songs path found in root. Unable to provide songs.")
            return songs
        for sd in songs_path.iterdir():
            if not sd.is_dir():
                logging.warning(
                    f"Item {sd} in songs folder is not a directory. Skipping"
                )
                continue
            metadata = self.read_metadata(sd / ".metadata.json")
            if not metadata:
                logging.warning(f"Error with metadata for {sd}.")
                # make metadata file...
                # for now we just quit LOL
                continue
            title = metadata.get("title")
            create = metadata.get("created_at")
            modify = metadata.get("modified_at")
            # determine # of lyrics and projects and renders
            dlyric: Path = sd / "lyrics"
            drender: Path = sd / "renders"
            dprojects: Path = sd / "projects"
            # create paths if they dont exist
            if not dlyric.exists():
                dlyric.mkdir()
            if not drender.exists():
                drender.mkdir()
            if not dprojects.exists():
                dprojects.mkdir()
            len_lyrics = len([_ for _ in dlyric.iterdir()])
            len_renders = len([_ for _ in drender.iterdir()])
            len_projects = len([_ for _ in dprojects.iterdir()])

            songs.append(
                {
                    "slug": sd.name,
                    "path": sd,
                    "title": title,
                    "lyrics_count": len_lyrics,
                    "projects_count": len_projects,
                    "renders_count": len_renders,
                    "created_at": create,
                    "modified_at": modify,
                }
            )

        return songs

    def read_albums(self) -> List[Dict[str, Any]]:
        # root/albums
        albums_path: Path = self.droot / "albums"
        albums: List[Dict[str, Any]] = []
        if not albums_path.exists():
            logging.error("No albums path found in root. Unable to provide albums")
            return albums
        for sd in albums_path.iterdir():
            if not sd.is_dir():
                # not a folder, not an album
                logging.warning(f"{sd} is not a directory. Skipping")
                continue
            metadata = self.read_metadata(sd / ".metadata.json")
            if not metadata:
                logging.warning(f"Error with metadata for {sd}.")
                # same as above, just keep going
                continue
            title = metadata.get(
                "name"
            )  #! fix this to make it more consistent with songs! or vice versa
            create = metadata.get("created_at")
            modify = metadata.get("modified_at")
            # now we want the tracklist
            tracklist = metadata.get("tracklist", [])
            slugs = [t.get("slug") for t in tracklist if isinstance(t, dict)]

            albums.append(
                {
                    "slug": sd.name,
                    "path": sd,
                    "name": title,
                    "tracklist": slugs,
                    "created_at": create,
                    "modified_at": modify,
                }
            )

        return albums

    # temp
    def read_metadata(self, file: Path) -> Optional[Dict[str, Any]]:
        if not file.exists():
            logging.error(f"File {file} does not exist. Not reading metadata.")
            return None
        # maybe temp
        json_name = re.compile(r".*\.json")
        if not json_name.match(file.name):
            logging.error(f"File {file} is not a JSON. Not reading metadata.")
            return None
        with open(file, "r") as item:
            data = json.load(item)
        return data


# testing
if __name__ == "__main__":
    sroot: Path = Path("../music")
    fm: FileManager = FileManager(sroot)
    print("\n".join(str(s) for s in fm.songs))
    print(len(fm.songs))
