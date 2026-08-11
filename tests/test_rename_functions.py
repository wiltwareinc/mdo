"""Verify song renaming across flat and directory-based project templates.

The test protects Reaper-style files, Ableton-style project directories, and
their supporting folders using only temporary templates and library data.

Authored by OpenAI Codex on 2026-08-07.
"""

from __future__ import annotations

from models.file_manager import FileManager


def test_rename_song_updates_flat_and_nested_project_files(
    file_manager: FileManager,
) -> None:
    song = file_manager.create_song("rename-test", [])
    assert song is not None

    reaper_project = file_manager.create_project(song, "rename-test", "Reaper")
    ableton_project = file_manager.create_project(song, "rename-test", "Ableton")
    assert reaper_project is not None
    assert ableton_project is not None

    renamed = file_manager.edit_song(song, "rename-test-new", None)
    assert renamed is not None

    project_files = {path.name for path in (renamed / "projects").rglob("*") if path.is_file()}
    assert "rename-test-new.RPP" in project_files
    assert "rename-test-new.als" in project_files
    assert "rename-test.RPP" not in project_files
    assert "rename-test.als" not in project_files
    assert list((renamed / "projects").rglob("Samples"))
