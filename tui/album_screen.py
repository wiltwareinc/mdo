# wiltware 2026
# seperate file just for the album screen
from app.config import get_config
from textual.app import RenderResult
from textual.binding import Binding
from textual.containers import VerticalScroll, Horizontal, Vertical
from textual.events import Click
from textual.reactive import Reactive
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Header, Input, Label, Static
from pathlib import Path
import os
from tui.api_client import create_album, get_albums, get_song
from tui.list_screen_base import BaseListScreen
from tui.song_screen import SongBox
from tui.utils import _open_file

class TracklistSongBox(Static):
    def __init__(self, song: dict, track_num: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self.song = song
        self.track_num = track_num

    def compose(self):
        with Horizontal(classes="box-base"):
            with Vertical(classes="tracklist_order"):
                yield Button("^", id="move_track_up", flat=True)
                yield Input(f"{self.track_num}", id="track_number")
                yield Button("v", id="move_track_down", flat=True)
            yield SongBox(self.song)
    

class TracklistScreen(ModalScreen):
    """Popup screen for a given album's tracklist"""
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("Q", "app.exit", "Quit"),
    ]
    def __init__(self, album: dict, **kwargs) -> None:
        super().__init__(**kwargs)
        self.album = album
    
    def compose(self):
        with Vertical(id="tracklist_panel"):
            with Horizontal(id="tracklist_header"):
                yield Label("Tracklist", id="tracklist_title")
                yield Button("x", id="close_window", flat=True)
            yield VerticalScroll(id="track_list")
    
    async def on_mount(self) -> None:
        track_list = self.query_one("#track_list", VerticalScroll)
        tracks = sorted(self.album["tracklist"], key=lambda t: t["number"])
        for track in tracks:
            song = get_song(track["slug"])
            # await track_list.mount(SongBox(song))
            await track_list.mount(TracklistSongBox(song, track["number"]))
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close_window":
            self.dismiss()


class AlbumBox(Static):
    """Information for an album based on API JSON."""

    def __init__(self, album: dict, **kwargs) -> None:
        super().__init__(**kwargs)
        self.album = album

    def compose(self):
        tracklist = self.album["tracklist"]
        with Vertical(classes="box-base"):
            with Horizontal(classes="album-row"):
                with Vertical(classes="album-meta"):
                    yield Label(self.album["title"])
                    yield Label(f"Created:  {self.album['created_at'][:10]}")
                    yield Label(f"Modified: {self.album['modified_at'][:10]}")
                with Vertical(classes="album-btns"):
                    # yield Button("Edit", id="edit", flat=True)
                    yield Button(f"{len(self.album["tracklist"])} Tracks v", id="open_tracklist")
                    yield Button("Open Folder", id="open_folder")
                    yield Button("Edit Album", id="edit_album")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        music_root = get_config().root
        aroot: Path = music_root / "albums" / self.album["slug"]
        
        if event.button.id == "open_tracklist":
            # open a modal box with only the tracklist, in order
            self.app.push_screen(TracklistScreen(self.album))
        
        if event.button.id == "open_folder":
            _open_file(aroot)
        
class AlbumScreen(BaseListScreen):
    def compose(self):
        yield from super().compose()
        
    async def on_mount(self) -> None:
        switcher = self.query_one("#screen_switcher", Horizontal)
        await switcher.mount(Button("New Album", id="new_album"))
        self.albums = get_albums()
        self.boxes = [AlbumBox(album) for album in self.albums]
        album_list = self.query_one(f"#{self.LIST_ID}", VerticalScroll)
        for box in self.boxes:
            await album_list.mount(box)

    def _get_data(self, box):
        return box.album
        
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id =="new_album":
            self.app.push_screen(NewAlbumScreen(on_created=self._add_album))
            return
        await super().on_button_pressed(event)
    
    async def _add_album(self, album: dict):
        box = AlbumBox(album)
        self.boxes.append(box)
        album_list = self.query_one(f"#{self.LIST_ID}", VerticalScroll)
        await album_list.mount(box)
            
            
class NewAlbumScreen(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("Q", "app.exit", "Quit"),
    ]
    def __init__(self, on_created, **kwargs) -> None:
        super().__init__(**kwargs)
        self.on_created = on_created

    def compose(self):
        with Vertical(id="tracklist_panel"):
            with Horizontal(id="tracklist_header"):
                yield Label("Change name", id="tracklist_title")
                yield Button("x", id="close_window", flat=True)
            with Horizontal():
                yield Label("Enter name:")
                yield Input(placeholder="New name", id="input_box")

    async def on_input_submitted(self, event: Input.Submitted) -> None: #?
        new_name = event.value.strip()
        self.notify(new_name)
        if not new_name:
            self.notify("Name cannot be empty")
            return
        try:
            payload = {
                "title": new_name,
                "tracklist": [] # beta: no album make
            }
            created = create_album(new_name, payload)
            await self.on_created(created)
        except RuntimeError as exc:
            self.notify(str(exc))
        self.dismiss()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close_window":
            self.dismiss()


