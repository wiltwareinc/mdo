# wiltware
# essentially the backend with filesystems
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from typing_extensions import Any, Dict, List


class FileManager:
    def __init__(self, droot: Path) -> None:
        if not droot:
            logging.error("No root provided. Unable to continue.")
            sys.exit(1)
        self.droot = droot
        # array of albums (slug, title, tracklist (in slugs), created, modified)
        self.albums = self.read_albums()
        # array of songs (in terms of (slug, name, # of lyrics, # of projects, # of renders, creation date, modified date)
        self.songs = self.read_songs()
        self.albums.sort(key=lambda x: x["slug"])
        self.songs.sort(key=lambda x: x["slug"])

    # READING

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
            metadata = {}
            try:
                with open(sd / ".metadata.json", "r") as item:
                    metadata = json.load(item)
            except FileNotFoundError:
                logging.warning(f"Missing metadata for {sd}.")
                # make metadata file...
                self.create_metadata("song", sd)
                # for now we just quit LOL
                continue
            except json.JSONDecodeError as e:
                logging.warning(f"Bad metadata for {sd}: {e}")
                # will need to be fixed in the future, for now just skip
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

            songs.append(metadata)

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
            songscheck = sd / "songs"
            if not songscheck.exists():
                songscheck.mkdir()
            try:
                with open(sd / ".metadata.json", "r") as item:
                    metadata = json.load(item)
            except FileNotFoundError:
                logging.warning(f"Missing metadata for {sd}.")
                # make metadata file...
                # for now we just quit LOL
                continue
            except json.JSONDecodeError as e:
                logging.warning(f"Bad metadata for {sd}: {e}")
                continue
            # now we want the tracklist
            # ? is this needed?
            albums.append(metadata)

        return albums

    ### CREATION
    # both are tempo, will be added to a utilities folder soon
    def iso_to_timestamp(self, iso, tz: ZoneInfo):
        if len(iso) == 8 and iso.isdigit():
            y = int(iso[0:4])
            m = int(iso[4:6])
            d = int(iso[6:8])
            return datetime(y, m, d, 0, 0, 0, tzinfo=tz).isoformat()
        return

    def create_metadata(self, kind: str, slug: Path):
        metadata: Dict = {}
        # All metadata should have a slug and title
        metadata["slug"] = f"{slug.name}"
        # Automatically generate title based on file
        parts = slug.name.split("-", 1)
        metadata["title"] = parts[1] if len(parts) > 1 else slug.name
        # for now, we are setting the timezone to newyork. EST supremacy
        timezone = ZoneInfo("America/New_York")
        metadata["timezone"] = str(timezone)

        if kind == "song":
            # songs contain: lyrics, projects, default project, and renders
            try:
                lyrics = slug / "lyrics"
                metadata["lyrics"] = [
                    {"path": str(p.relative_to(slug))}
                    for p in sorted(lyrics.iterdir())
                    if p.is_file()
                ]
                projects = slug / "projects"
                metadata["projects"] = [
                    {"path": str(p.relative_to(slug))}
                    for p in sorted(projects.iterdir())
                    if p.is_dir()
                ]
                # just grab the newest project as the default
                metadata["default_project"] = (
                    metadata["projects"][-1]["path"] if metadata["projects"] else None
                )
                renders = slug / "renders"
                metadata["renders"] = [
                    {"path": str(p.relative_to(slug))}
                    for p in sorted(renders.iterdir())
                    if p.is_file()
                ]
            except Exception:
                # fill out more
                logging.error("Error")

        elif kind == "album":
            # detect if there are any symlinks
            songs = slug / "songs"
            tracklist = []
            track_number = 0
            for sub in sorted(songs.iterdir()):
                if sub.is_symlink():
                    track_number += 1
                    tracklist.append({"slug": sub.name, "number": track_number})
            metadata["tracklist"] = tracklist
        else:
            logging.error(f"Calling a metadata creation can't process {kind}.")
            return

        # Getting back to what every metadata file has:
        current_time = datetime.fromtimestamp(time.time(), timezone).isoformat()
        metadata["created_at"] = (
            self.iso_to_timestamp(parts[0], timezone)
            if len(parts) > 1
            else current_time
        )
        metadata["modified_at"] = current_time
        return


# testing
if __name__ == "__main__":
    sroot: Path = Path("../music")
    fm: FileManager = FileManager(sroot)
    print("\n".join(str(s) for s in fm.songs))
    print(len(fm.songs))
