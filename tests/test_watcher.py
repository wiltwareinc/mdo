# This test was written by ChatGPT Codex 5 on 2026-02-19
from __future__ import annotations

import shutil
import sys
import tempfile
import time
from pathlib import Path

from watchdog.events import FileSystemEvent

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from models.watcher import Debouncer, MdoEventHandler, normalize_event_path


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def make_temp_root() -> Path:
    temp_root = ROOT / "extra" / "tmp-test"
    temp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="mdo-watcher-", dir=temp_root))
    root = temp_dir / "music"
    (root / "songs").mkdir(parents=True)
    (root / "albums").mkdir(parents=True)
    return root


def test_normalize_event_path(root: Path) -> None:
    song_slug = root / "songs" / "20260219-test-song"
    song_file = song_slug / "lyrics" / "a.txt"
    song_file.parent.mkdir(parents=True)
    song_file.touch()

    album_slug = root / "albums" / "20260219-test-album"
    album_file = album_slug / "songs" / "20260219-test-song"
    album_file.parent.mkdir(parents=True)
    album_file.touch()

    song_out = normalize_event_path(root, song_file)
    assert_true(song_out == ("song", song_slug), "song path should normalize to song slug")

    album_out = normalize_event_path(root, album_file)
    assert_true(
        album_out == ("album", album_slug),
        "album path should normalize to album slug",
    )


def test_debouncer(root: Path) -> None:
    results: list[tuple[str, Path]] = []

    def _callback(kind: str, path: Path) -> None:
        results.append((kind, path))

    debouncer = Debouncer(window_s=0.0)
    path = root / "songs" / "20260219-test-song"
    debouncer.push("song", path)
    debouncer.flush(_callback)
    assert_true(results == [("song", path)], "debouncer should flush queued items")


def test_event_handler(root: Path) -> None:
    results: list[tuple[str, Path]] = []

    def _callback(kind: str, path: Path) -> None:
        results.append((kind, path))

    debouncer = Debouncer(window_s=0.0)
    handler = MdoEventHandler(root, _callback, debouncer)
    song_path = root / "songs" / "20260219-test-song" / "lyrics" / "a.txt"
    song_path.parent.mkdir(parents=True, exist_ok=True)
    song_path.touch()

    handler.on_any_event(FileSystemEvent(str(song_path)))
    debouncer.flush(_callback)
    assert_true(
        results == [("song", root / "songs" / "20260219-test-song")],
        "event handler should push normalized song slug",
    )


def main() -> None:
    root = make_temp_root()
    try:
        test_normalize_event_path(root)
        test_debouncer(root)
        test_event_handler(root)
        print("watcher tests: OK")
    finally:
        shutil.rmtree(root.parent)


if __name__ == "__main__":
    main()
