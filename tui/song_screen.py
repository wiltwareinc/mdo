# wiltware 2026
# seperate file just for the song screen
# note: partially tranfered by chatgpt codex
import os
from pathlib import Path
import subprocess
from textual.containers import VerticalScroll, Horizontal, Vertical
from textual.events import Click
from textual.reactive import Reactive
from textual.widget import Widget
from textual.widgets import Button, Label, Static

from tui.api_client import get_songs
from tui.list_screen_base import BaseListScreen
from tui.utils import _find_reaper, _open_file


class SongBox(Static):
    """Information for a song based on information."""

    def __init__(self, song: dict, **kwargs) -> None:
        super().__init__(**kwargs)
        self.song = song

    def compose(self):
        lyrics = self.song["lyrics"]
        projects = self.song["projects"]
        renders = self.song["renders"]
        with Vertical(classes="box-base"):
            with Horizontal(classes="song-row"):
                with Vertical(classes="song-meta"):
                    yield Label(self.song["title"])
                    yield Label(f"Created:  {self.song['created_at'][:10]}")
                    yield Label(f"Modified: {self.song['modified_at'][:10]}")
                with Vertical(classes="song-btns"):
                    yield Button("Open Default", id="open_project", flat=True)
                    yield Button("Open Renders", id="open_renders", flat=True)
                    yield Button("Open Lyrics", id="open_lyrics", flat=True)
                    yield Button("Edit", id="edit", flat=True)
            yield Label(f"Lyrics: {len(lyrics)}, Projects: {len(projects)}, Renders: {len(renders)}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        music_root = Path(os.getenv("MDO_ROOT", "./music")).resolve()
        sroot: Path = music_root / "songs" / self.song["slug"]

        if event.button.id == "open_project":
            default = self.song["default_project"]
            project = sroot / default if default is not None else sroot
            project = _find_reaper(project)
            if project:
                self.notify(f"open {project}")
                _open_file(project)
            else:
                self.notify("No default project!")

        if event.button.id == "open_renders":
            self.notify(f"open renders folder {sroot / 'renders'}")
            _open_file(sroot / "renders")

        if event.button.id == "open_lyrics":
            lyrics = self.song.get("lyrics", [])
            lyric = lyrics[-1]["path"] if lyrics else None
            if lyric:
                self.notify(f"open lyrics {sroot / lyric}")
                _open_file(sroot / lyric)
            else:
                self.notify("No lyrics found!")

        if event.button.id == "edit":
            self.notify("edit")


class SongScreen(BaseListScreen):
    async def on_mount(self) -> None:
        self.songs = get_songs()
        self.boxes = [SongBox(song) for song in self.songs]
        song_list = self.query_one(f"#{self.LIST_ID}", VerticalScroll)
        for box in self.boxes:
            await song_list.mount(box)

    def _get_data(self, box):
        return box.song


