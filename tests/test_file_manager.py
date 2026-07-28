# This test was written by ChatGPT Codex 5.2 on 2026-02-14
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from models.file_manager import FileManager


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def make_temp_music() -> Path:
    temp_root = ROOT / "extra" / "tmp-test"
    temp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="mdo-file-manager-", dir=temp_root))
    temp_music = temp_dir / "music"
    temp_music.mkdir()
    shutil.copytree(ROOT / "music" / "songs", temp_music / "songs")
    (temp_music / "albums").mkdir()
    return temp_music


def test_create_edit_song(fm: FileManager) -> None:
    created = fm.create_song("unit-test-song", ["lyrics"])
    assert_true(created is not None, "create_song should return a path")
    assert_true(created.exists(), "created song folder should exist")
    assert_true((created / ".metadata.json").exists(), "metadata should be written")
    lyric_files = list((created / "lyrics").glob("*.txt"))
    assert_true(lyric_files, "lyrics file should be created")

    renamed = fm.edit_song(created, "unit-test-song-renamed", None)
    assert_true(renamed is not None, "edit_song should return a path")
    assert_true(renamed.exists(), "renamed song folder should exist")
    assert_true(not created.exists(), "old song folder should be renamed away")
    renamed_lyrics = list((renamed / "lyrics").glob("*-unit-test-song-renamed.txt"))
    assert_true(renamed_lyrics, "lyrics file should be renamed to new title")


def test_create_edit_album(fm: FileManager) -> None:
    assert_true(fm.songs_set, "need at least one song to build an album")
    tracklist = [fm.songs_set[0]]
    created = fm.create_album("unit-test-album", tracklist)
    assert_true(created is not None, "create_album should return a path")
    assert_true(
        (created / ".metadata.json").exists(), "album metadata should be written"
    )
    assert_true(
        (created / "songs" / tracklist[0]).exists(), "album song symlink should exist"
    )

    renamed = fm.edit_album(created, "unit-test-album-renamed", tracklist)
    assert_true(renamed is not None, "edit_album should return a path")
    assert_true(renamed.exists(), "renamed album folder should exist")


def test_rename_song_updates_album_references(fm: FileManager) -> None:
    song = fm.create_song("linked-song", [])
    assert_true(song is not None, "create_song should return a path")
    old_slug = song.name

    album = fm.create_album("linked-album", [old_slug])
    assert_true(album is not None, "create_album should return a path")

    renamed = fm.edit_song(song, "renamed-linked-song", None)
    assert_true(renamed is not None, "edit_song should return a path")
    new_slug = renamed.name

    old_link = album / "songs" / old_slug
    new_link = album / "songs" / new_slug

    assert_true(
        not old_link.is_symlink(),
        "album should no longer contain a symlink with the old song slug",
    )
    assert_true(
        new_link.is_symlink(),
        "album should contain a symlink with the renamed song slug",
    )
    assert_true(
        new_link.resolve() == renamed.resolve(),
        "renamed album symlink should point to the renamed song",
    )

    fm.refresh_albums()
    album_data = next(item for item in fm.albums if item["slug"] == album.name)
    track_slugs = [track["slug"] for track in album_data["tracklist"]]
    assert_true(
        old_slug not in track_slugs,
        "album metadata should not retain the old song slug",
    )
    assert_true(
        new_slug in track_slugs,
        "album metadata should contain the renamed song slug",
    )


def main() -> None:
    temp_music = make_temp_music()
    try:
        fm = FileManager(temp_music)
        test_create_edit_song(fm)
        test_create_edit_album(fm)
        test_rename_song_updates_album_references(fm)
        print("file_manager tests: OK")
    finally:
        shutil.rmtree(temp_music.parent)


if __name__ == "__main__":
    main()
