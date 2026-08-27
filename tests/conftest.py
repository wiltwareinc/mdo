"""Shared pytest fixtures for isolated MDO tests.

These fixtures create temporary libraries, project templates, configuration,
and FastAPI clients without reading or modifying the developer's music library.

Authored by OpenAI Codex on 2026-08-07.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.deps import get_file_manager
from app.main import app
from models.file_manager import FileManager
from persistence.storage import initialize_storage


@pytest.fixture
def music_root(tmp_path: Path) -> Path:
    """Return a new, empty MDO library for one test."""
    root = tmp_path / "music"
    (root / "songs").mkdir(parents=True)
    (root / "albums").mkdir()
    initialize_storage(root, "Test Music Library")
    return root


@pytest.fixture
def config_path(tmp_path: Path, music_root: Path) -> Path:
    """Create hermetic Reaper and Ableton templates and an MDO config file."""
    template_root = tmp_path / "templates"
    template_root.mkdir()

    reaper_template = template_root / "default.RPP"
    reaper_template.write_text("dummy reaper template", encoding="utf-8")

    ableton_root = template_root / "ableton"
    ableton_root.mkdir()
    (ableton_root / "Samples").mkdir()
    (ableton_root / "Ableton Project Info").mkdir()
    ableton_template = ableton_root / "default.als"
    ableton_template.write_text("dummy ableton template", encoding="utf-8")

    path = tmp_path / "mdo-config.json"
    path.write_text(
        json.dumps(
            {
                "root": str(music_root),
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
    return path


@pytest.fixture
def configured_environment(
    monkeypatch: pytest.MonkeyPatch,
    music_root: Path,
    config_path: Path,
) -> Iterator[None]:
    """Point MDO at temporary test data and clear its cached FileManager."""
    monkeypatch.setenv("MDO_ROOT", str(music_root))
    monkeypatch.setenv("MDO_CONFIG", str(config_path))
    get_file_manager.cache_clear()
    yield
    get_file_manager.cache_clear()


@pytest.fixture
def file_manager(
    configured_environment: None,
    music_root: Path,
) -> FileManager:
    """Return a FileManager backed only by the temporary library."""
    return FileManager(music_root)


@pytest.fixture
def api_client(configured_environment: None) -> Iterator[TestClient]:
    """Return an in-process FastAPI client using the temporary library."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
def load_manifest() -> Callable[[str], dict]:
    """Return a loader that produces fresh dictionaries from JSON fixtures."""
    fixture_root = Path(__file__).parent / "fixtures" / "manifests"

    def _load(filename: str) -> dict:
        return json.loads((fixture_root / filename).read_text(encoding="utf-8"))

    return _load
