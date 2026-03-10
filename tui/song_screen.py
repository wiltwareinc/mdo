# wiltware 2026
# seperate file just for the song screen
# note: partially tranfered by chatgpt codex
import os
from pathlib import Path
import subprocess
from typing import Any
from textual.binding import Binding
from textual.containers import VerticalScroll, Horizontal, Vertical
from textual.content import Content
from textual.events import Click
from textual.reactive import Reactive
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Checkbox, Header, Input, Label, Select, Static

from tui.api_client import create_lyric, create_project, get_songs, edit_song
from tui.list_screen_base import BaseListScreen
from tui.utils import _find_reaper, _open_file


class SongBox(Static):
    """Information for a song based on information."""
    # default_project = Reactive(0)
    song: Reactive[dict[str, Any] | None] = Reactive(None)

    def __init__(self, song: dict, **kwargs) -> None:
        super().__init__(**kwargs)
        self.song = song
        self.default_project = self.song["default_project"] or "None"

    def compose(self):
        if self.song is None:
            return
        lyrics = self.song["lyrics"]
        projects = self.song["projects"]
        renders = self.song["renders"]
        with Vertical(classes="box-base"):
            with Horizontal(classes="song-row"):
                with Vertical(classes="song-meta"):
                    self.title = Label(self.song["title"])
                    yield self.title
                    yield Label(f"Created:  {self.song['created_at'][:10]}")
                    yield Label(f"Modified: {self.song['modified_at'][:10]}")
                with Vertical(classes="song-btns"):
                    yield Button("Open Default", id="open_project", flat=True)
                    yield Button("Open Renders", id="open_renders", flat=True)
                    yield Button("Open Lyrics", id="open_lyrics", flat=True)
                    # yield Button("Edit", id="edit", flat=True)
                    yield Select(
                        options = [
                            ("Change name", "change_name"),
                            ("Change default project", "change_proj"),
                            ("Create project", "create_project"),
                            ("Create lyric", "create_lyric"),
                        ]
                    )
            self.meta_label = Label(f"Lyrics: {len(lyrics)}, Projects: {len(projects)} (default {self.default_project}), Renders: {len(renders)}")
            yield self.meta_label # split so i can update it later
    
    def watch_song(self, value: dict) -> None:
        # self.notify("updated!")
        lyrics = value["lyrics"]
        projects = value["projects"]
        renders = value["renders"]
        default = value["default_project"] or "None"
        try:
            self.meta_label.update(
                f"Lyrics: {len(lyrics)}, Projects: {len(projects)}"
                f"(default {default}), Renders: {len(renders)}"
            )
            self.title.update(value["title"])
        except: # crummy code LOL
            pass
        
    
    async def on_select_changed(self, event: Select.Changed) -> None:
        if self.song is None:
            return
        action = event.value
        event.select.clear()
        if action == "change_name":
            self.app.push_screen(NameScreen(self.song, self))
        if action == "change_proj":
            self.app.push_screen(DefaultProjScreen(self.song, self))
        if action == "create_project":
            self.app.push_screen(CreateAssetScreen(self.song, self, "project"))
        if action == "create_lyric":
            self.app.push_screen(CreateAssetScreen(self.song, self, "lyric"))
            

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if self.song is None:
            return
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
            # self.app.push_screen(EditScreen(self.song))
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


class NameScreen(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("Q", "app.exit", "Quit"),
    ]
    def __init__(self, song: dict, box: SongBox, **kwargs) -> None:
        super().__init__(**kwargs)
        self.song = song
        self.box = box

    def compose(self):
        with Vertical(id="tracklist_panel"):
            with Horizontal(id="tracklist_header"):
                yield Label("Change name", id="tracklist_title")
                yield Button("x", id="close_window", flat=True)
            with Horizontal():
                yield Label("Enter new name:")
                yield Input(placeholder="New name", id="input_box")

    def on_input_submitted(self, event: Input.Submitted) -> None: #?
        new_name = event.value.strip()
        self.notify(new_name)
        if not new_name:
            self.notify("Name cannot be empty")
            return
        try:
            updated = edit_song(self.song["slug"], {"title": new_name})
            self.notify(updated["title"])
            self.box.song = updated
        except RuntimeError as exc:
            self.notify(str(exc))
        self.dismiss()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close_window":
            self.dismiss()

class DefaultProjScreen(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("Q", "app.exit", "Quit"),
    ]
    def __init__(self, song: dict, box: SongBox, **kwargs) -> None:
        super().__init__(**kwargs)
        self.song = song
        self.box = box

    def compose(self):
        with Vertical(id="tracklist_panel"):
            with Horizontal(id="tracklist_header"):
                yield Label("Change default project", id="tracklist_title")
                yield Button("x", id="close_window", flat=True)
            with Horizontal():
                # intergers
                options = [
                    (f"{i}. {Path(p['path']).name}", str(i))
                    for i, p in enumerate(self.song.get("projects", []), start=1) # 1 indexed
                ]
                # yield Select((proj["path"], proj["path"]) for proj in self.song["projects"])
                yield Select(options, id="default_project_select")
    
    async def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "default_project_select":
            return
        value = event.value
        if value is Select.BLANK:
            return
        if not isinstance(value, str):
            return
        index = int(value)
        updated = edit_song(self.song["slug"], {"default_project": index})
        # update it (probably can be cleaner)
        self.box.song = updated
        self.box.default_project = updated["default_project"] or "None"
        # self.box.refresh()
        self.dismiss()


    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close_window":
            self.dismiss()

class CreateAssetScreen(ModalScreen):
    """Creates an album/project. Both are similar, so I decided to combine both"""
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("Q", "app.exit", "Quit"),
    ]
    def __init__(self, song: dict, box: SongBox, type: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.song = song
        self.box = box
        self.type = type

    def compose(self):
        with Vertical(id="tracklist_panel"):
            with Horizontal(id="tracklist_header"):
                yield Label(f"Change {self.type}", id="tracklist_title")
                yield Button("x", id="close_window", flat=True)
            # with Horizontal():
            #     yield Label("Enter name:")
            #     yield Input(placeholder="Enter name...", id="input_box")
            with Horizontal():
                yield Checkbox("Open after creation?")
                yield Button("Enter", id="enter_asset")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close_window":
            self.dismiss()
        if event.button.id == "enter_asset":
            # name = self.query_one("#input_box", Input).value.strip()
            # if not name:
            #     self.notify("Name must not be empty")
            #     return
            name = self.song["title"] #? should we allow the user to change the name
            if self.type == "lyric":
                try:
                    updated = create_lyric(self.song["slug"], {"title": name})
                    self.box.song = updated
                except RuntimeError as exc:
                    self.notify(str(exc))
                self.dismiss()
                return
            if self.type == "project":
                try:
                    updated = create_project(self.song["slug"], {"title": name})
                    self.box.song = updated
                except RuntimeError as exc:
                    self.notify(str(exc))
                self.dismiss()
                return
            self.notify("Not a valid option!")
            self.dismiss()
