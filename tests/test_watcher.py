"""Test watcher path normalization, debouncing, and event filtering.

These are unit tests for watcher decisions only; they do not start operating
system observers or wait for real filesystem notifications.

Authored by OpenAI Codex on 2026-08-07.
"""

from __future__ import annotations

from pathlib import Path

from watchdog.events import FileCreatedEvent, FileModifiedEvent

from models.watcher import Debouncer, MdoEventHandler, normalize_event_path


def test_normalize_event_path_identifies_song_and_album(music_root: Path) -> None:
    song_path = music_root / "songs" / "song-one" / "lyrics" / "a.txt"
    album_path = music_root / "albums" / "album-one" / "songs" / "song-one"

    assert normalize_event_path(music_root, song_path) == (
        "song",
        music_root / "songs" / "song-one",
    )
    assert normalize_event_path(music_root, album_path) == (
        "album",
        music_root / "albums" / "album-one",
    )


def test_normalize_event_path_rejects_outside_path(
    music_root: Path,
    tmp_path: Path,
) -> None:
    assert normalize_event_path(music_root, tmp_path / "outside.txt") is None


def test_debouncer_flushes_ready_item(music_root: Path) -> None:
    results: list[tuple[str, Path]] = []
    path = music_root / "songs" / "song-one"
    debouncer = Debouncer(window_s=0.0)

    debouncer.push("song", path)
    debouncer.flush(lambda kind, changed_path: results.append((kind, changed_path)))

    assert results == [("song", path)]
    assert debouncer.pending == {}


def test_event_handler_queues_created_song_event(music_root: Path) -> None:
    results: list[tuple[str, Path]] = []
    debouncer = Debouncer(window_s=0.0)
    handler = MdoEventHandler(music_root, lambda *_: None, debouncer)
    song_file = music_root / "songs" / "song-one" / "lyrics" / "a.txt"

    handler.on_any_event(FileCreatedEvent(str(song_file)))
    debouncer.flush(lambda kind, changed_path: results.append((kind, changed_path)))

    assert results == [("song", music_root / "songs" / "song-one")]


def test_event_handler_ignores_modified_and_metadata_events(music_root: Path) -> None:
    debouncer = Debouncer(window_s=0.0)
    handler = MdoEventHandler(music_root, lambda *_: None, debouncer)
    song_root = music_root / "songs" / "song-one"

    handler.on_any_event(FileModifiedEvent(str(song_root / "lyrics" / "a.txt")))
    handler.on_any_event(FileCreatedEvent(str(song_root / ".metadata.json")))

    assert debouncer.pending == {}
