# wiltware
# essentially the backend with filesystems
import json
import logging
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
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
        self.songs_set = [s["slug"] for s in self.songs]

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
            try:
                with open(sd / ".metadata.json", "r") as item:
                    metadata = json.load(item)
            except FileNotFoundError:
                logging.warning(f"Missing metadata for {sd}.")
                # make metadata file...
                metadata = self.create_metadata("song", sd)
                with open(sd / ".metadata.json", "w") as item:
                    json.dump(metadata, item, indent=2)
                continue
            except json.JSONDecodeError as e:
                logging.warning(f"Bad metadata for {sd}: {e}")
                # will need to be fixed in the future, for now just skip

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
    # both are temp, will be added to a utilities folder soon
    def iso_to_timestamp(self, iso, tz: ZoneInfo):
        if len(iso) == 8 and iso.isdigit():
            y = int(iso[0:4])
            m = int(iso[4:6])
            d = int(iso[6:8])
            return datetime(y, m, d, 0, 0, 0, tzinfo=tz).isoformat()
        return

    def create_metadata(self, kind: str, slug: Path, tracklist: Optional[list[str]] = None):
        metadata = {}
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
            if tracklist:
                tracklist_out = []
                track_number = 0
                for item in tracklist:
                    if item not in self.songs_set:
                        logging.warning(f"{item} is not in song list. Skipping")
                        continue
                    track_number += 1
                    tracklist_out.append({"slug": item, "number": track_number})
                metadata["tracklist"] = tracklist_out
                
            else:
            # detect if there are any symlinks
                songs = slug / "songs"
                tracklist_out = []
                track_number = 0
                for sub in sorted(songs.iterdir()):
                    if sub.is_symlink():
                        track_number += 1
                        tracklist_out.append({"slug": sub.name, "number": track_number})
                metadata["tracklist"] = tracklist_out
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
        return metadata

    def create_album(self, title, tracklist: list[str]) -> Optional[Path]:
        """
        Creates an album.

        Args:
            title: The name of the album
            tracklist: The tracklist, an array in order.

        Returns:
            The slug of the album's root folder, as a Path, or None if it fails
        """
        # verify that the location is valid (item with same name was not made on same day)
        date = datetime.now().strftime("%Y%m%d")  # YYYYMMDD
        slug = f"{date}-{title}"

        # verify it doesn't already exist
        albums_path = self.droot / "albums"  # ? should these be self. variables?
        for sd in albums_path.iterdir():
            if sd.name == slug:
                logging.error(f"{sd} is a duplicate. Not making")
                return None

        # Begin creating folders
        proot = albums_path / slug
        proot.mkdir()
        songs = proot / "songs"
        other = proot / "other"
        songs.mkdir()
        other.mkdir()

        # now we need to check and see if the songs exist
        for item in tracklist:
            if item not in self.songs_set:
                logging.warning(f"{item} is not in list of songs. Skipping")
                continue
            (songs / item).symlink_to(self.droot / "songs" / item)

        metadata = self.create_metadata("album", proot, tracklist)
        if metadata is not None:
            with open(proot / ".metadata.json", "w") as f:
                json.dump(metadata, f, indent=2)
        else:
            logging.warning(f"Metadata for {proot} not created.")

        return proot

    def create_song(self, title, args: list[str]) -> Optional[Path]:
        """
        Creates a song and the appropriate folders.

        Args:
            title: the name of the song
            args: A list of arguments. "lyric" means create a lyric, "session" means create a session.

        Returns:
            The slug of the song's root folder as a Path, or None if it fails.
        """
        date = datetime.now().strftime("%Y%m%d")  # YYYYMMDD
        slug = f"{date}-{title}"

        # verify it doesn't already exist
        songs_path = self.droot / "songs"  # ? should these be self. variables?
        for sd in songs_path.iterdir():
            if sd.name == slug:
                logging.error(f"{sd} is a duplicate. Not making")
                return None

        sroot = songs_path / slug
        lyrics = sroot / "lyrics"
        renders = sroot / "renders"
        projects = sroot / "projects"
        sroot.mkdir()
        lyrics.mkdir()
        renders.mkdir()
        projects.mkdir()

        # check args
        if "lyrics" in args:
            self.create_lyrics(sroot, title)
        if "project" in args:
            self.create_project(sroot, title)

        # build metadata
        self.create_metadata("song", sroot)
        return sroot

    def create_lyrics(self, root: Path, title) -> Optional[Path]:
        """
        Creates a lyric.

        Args:
            root: Root of song to create a lyric in
        Returns:
            Path of the lyrics file

        Note: this can fail if the lyrics/ dir does not exist in the directory.
        """
        # verify that the lyrics dir exists
        lyricsd: Path = root / "lyrics"
        if not lyricsd.exists():
            logging.error(f"{root} does not have a lyrics folder")
            return None

        date = datetime.now().strftime("%Y%m%d")  # YYYYMMDD
        slug = f"{date}-{title}"
        # we can be more lenient, let's do a check
        lyricsf = lyricsd / slug
        candidate = lyricsf.with_suffix(".txt")
        counter = 1

        if candidate.exists():
            while (lyricsd / f"{slug}-{counter}.txt").exists():
                counter += 1
            candidate = lyricsd / f"{slug}-{counter}.txt"
        candidate.touch()

        return candidate

    def create_project(self, root: Path, title) -> Optional[Path]:
        """
        Creates a project.

        Args:
            root: Root of song to create a project in
        Returns:
            Path of the project specific file (ex. a .RPP file for Reaper)

        Note: this can fail if the projects/ dir does not exist in the directory.
        """
        projectd: Path = root / "projects"
        if not projectd.exists():
            logging.error(f"{root} does not have a projects folder")
            return None

        date = datetime.now().strftime("%Y%m%d")  # YYYYMMDD
        slug = f"{date}-{title}"
        # we can be more lenient
        projectf = projectd / slug

        candidate = projectf
        counter = 1
        
        if candidate.exists():
            while (projectd / f"{slug}-{counter}").exists():
                counter += 1
            candidate = (projectd / f"{slug}-{counter}")
        candidate.mkdir()

        # for now we are just grabbing the reaper default, will be extensible in the future
        reaper_default = (
            Path("~/.config/REAPER/ProjectTemplates/default.RPP").expanduser()
        )
        dest = candidate / f"{title}.RPP"
        shutil.copy2(reaper_default, dest)

        return dest


# testing
if __name__ == "__main__":
    sroot: Path = Path("../music")
    fm: FileManager = FileManager(sroot)
    print("\n".join(str(s) for s in fm.songs))
    print(len(fm.songs))
