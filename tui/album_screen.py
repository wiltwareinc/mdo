# wiltware 2026
# seperate file just for the album screen
from textual.app import RenderResult
from textual.binding import Binding
from textual.containers import VerticalScroll, Horizontal, Vertical
from textual.events import Click
from textual.reactive import Reactive
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Header, Label, Static
from pathlib import Path
import os
from tui.api_client import get_albums, get_song
from tui.list_screen_base import BaseListScreen
from tui.song_screen import SongBox
from tui.utils import _open_file

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
            await track_list.mount(SongBox(song))
    
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
        music_root = Path(os.getenv("MDO_ROOT", "./music")).resolve()
        aroot: Path = music_root / "albums" / self.album["slug"]
        
        if event.button.id == "open_tracklist":
            # open a modal box with only the tracklist, in order
            self.app.push_screen(TracklistScreen(self.album))
        
        if event.button.id == "open_folder":
            _open_file(aroot)
        
class AlbumScreen(BaseListScreen):
    async def on_mount(self) -> None:
        self.albums = get_albums()
        self.boxes = [AlbumBox(album) for album in self.albums]
        album_list = self.query_one(f"#{self.LIST_ID}", VerticalScroll)
        for box in self.boxes:
            await album_list.mount(box)

    def _get_data(self, box):
        return box.album
