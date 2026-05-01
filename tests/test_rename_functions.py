# Tests for rename behavior across project layouts.
from __future__ import annotations

import json
import os
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


def make_temp_config(temp_dir: Path, temp_music: Path) -> Path:
    template_dir = temp_dir / "templates"
    ableton_dir = template_dir / "ableton"
    ableton_dir.mkdir(parents=True)
    (ableton_dir / "Samples").mkdir()
    (ableton_dir / "Ableton Project Info").mkdir()

    reaper_template = template_dir / "default.RPP"
    ableton_template = ableton_dir / "default.als"
    reaper_template.write_text("dummy reaper template", encoding="utf-8")
    ableton_template.write_text("dummy ableton template", encoding="utf-8")

    config_path = temp_dir / ".config.json"
    config_path.write_text(
        json.dumps(
            {
                "root": str(temp_music),
                "templates": {
                    "Reaper": {
                        "path": str(reaper_template),
                        "folder": False,
                    },
                    "Ableton": {
                        "path": str(ableton_template),
                        "folder": True,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return config_path


def test_rename_song_updates_flat_and_nested_project_files() -> None:
    temp_root = ROOT / "extra" / "tmp-test"
    temp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="mdo-rename-", dir=temp_root))
    temp_music = temp_dir / "music"
    old_config = os.environ.get("MDO_CONFIG")

    try:
        os.environ["MDO_CONFIG"] = str(make_temp_config(temp_dir, temp_music))

        fm = FileManager(temp_music)
        song = fm.create_song("rename-test", [])
        assert_true(song is not None, "create_song should return a path")

        reaper_project = fm.create_project(song, "rename-test", "Reaper")
        ableton_project = fm.create_project(song, "rename-test", "Ableton")
        assert_true(reaper_project is not None, "Reaper project should be created")
        assert_true(ableton_project is not None, "Ableton project should be created")

        renamed = fm.edit_song(song, "rename-test-new", None)
        assert_true(renamed is not None, "edit_song should return renamed song path")

        project_files = [
            p for p in (renamed / "projects").rglob("*") if p.is_file()
        ]
        project_file_names = {p.name for p in project_files}
        support_folders = list((renamed / "projects").glob("*/**/Samples"))

        assert_true(
            "rename-test-new.RPP" in project_file_names,
            "Reaper project file should be renamed",
        )
        assert_true(
            "rename-test-new.als" in project_file_names,
            "Ableton project file should be renamed",
        )
        assert_true(
            "rename-test.RPP" not in project_file_names,
            "old Reaper project file name should not remain",
        )
        assert_true(
            "rename-test.als" not in project_file_names,
            "old Ableton project file name should not remain",
        )
        assert_true(
            bool(support_folders), "Ableton support folders should remain after rename"
        )
    finally:
        if old_config is None:
            os.environ.pop("MDO_CONFIG", None)
        else:
            os.environ["MDO_CONFIG"] = old_config
        shutil.rmtree(temp_dir)


def main() -> None:
    test_rename_song_updates_flat_and_nested_project_files()
    print("rename function tests: OK")


if __name__ == "__main__":
    main()
