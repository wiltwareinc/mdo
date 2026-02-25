# wiltware
# barebones TUI to use this without a frontend using Textual
import os
from pathlib import Path
import socket
import subprocess
import time
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.command import Command, Provider
from textual.containers import VerticalScroll, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Static, Button, Label, Input
from textual.widget import Widget

from tui.api_client import get_songs, get_song

class SongBox(Static):
    """
    Information for a song based on information
    """
    def __init__(self, song: dict, **kwargs) -> None:
        super().__init__(**kwargs)
        self.song = song
    
    def compose(self):
        # yield Label(f"{self.song['title']}")
        # yield Horizontal(
        #     Button("Open", id="open"),
        #     Button("Edit", id="edit"),
        # )
        lyrics = self.song["lyrics"]
        projects = self.song["projects"]
        renders = self.song["renders"]
        with Vertical(classes="box-base"):
            with Horizontal(classes="song-row"):
                with Vertical(classes="song-meta"):
                    yield Label(self.song["title"])
                    yield Label(f"Created:  {self.song["created_at"][:10]}")
                    yield Label(f"Modified: {self.song["modified_at"][:10]}")
                with Vertical(classes="song-btns"):
                    yield Button("Open Default", id="open_project", flat=True)
                    yield Button("Open Renders", id="open_renders", flat=True)
                    yield Button("Open Lyrics", id="open_lyrics", flat=True)
                    # yield Button("Open", id="open", flat=True)
                    yield Button("Edit", id="edit", flat=True)
            yield Label(f"Lyrics: {len(lyrics)}, Projects: {len(projects)}, Renders: {len(renders)}")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        sroot = Path(self.song["slug"])
        if event.button.id == "open_project":
            project = self.song["default_project"]
            if project:
                self.notify(f"open {sroot / project}")
            else:
                self.notify("No default project!")
        if event.button.id == "open_renders":
            self.notify(f"open renders folder {sroot / "renders"}")
        if event.button.id == "open_lyrics":
            lyric = self.song['lyrics'][-1]
            if lyric:
                self.notify(f"open lyrics {sroot / lyric}")
        if event.button.id == "item":
            self.notify("item")
    # def render(self) -> str:
    #     return f"title: {self.song['title']}\nslug: {self.song['slug']}"

class MdoApp(App):
    """entrypoint"""
    CSS_PATH = "bare_tui.tcss"
    BINDINGS = [
              Binding("n", "sort_name", "Sort by name", show=True),
              Binding("c", "sort_created", "Sort by created", show=True),
              Binding("m", "sort_modified", "Sort by modified", show=True),
          ]

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Input(placeholder="Search by title...", id="search")
        yield VerticalScroll(id="song_list")
        yield Footer()
        
    async def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "search":
            return
        query = event.value.strip().lower()
        self.filter_boxes(query=query)
    
    async def on_mount(self) -> None:
        self.songs = get_songs()
        self.boxes = [SongBox(song) for song in self.songs]
        song_list = self.query_one("#song_list", VerticalScroll)
        for box in self.boxes:
            await song_list.mount(box)
        
    def filter_boxes(self, query:str) -> None:
        q = query.lower().strip()
        for box in self.boxes:
            title = box.song.get("title", "").lower()
            box.display = q in title if q else True #???
            
    async def sort_boxes(self, key: str) -> None:
        song_list = self.query_one("#song_list", VerticalScroll)
        boxes = sorted(self.boxes, key=lambda b: b.song.get(key, "").lower())
        with self.batch_update():
            last = None
            for box in boxes:
                if last is None:
                    song_list.move_child(box, before=0, after=None)
                else:
                    song_list.move_child(box, after=last)
                last = box
        song_list.scroll_home(animate=False)
        
    def get_system_commands(self, screen: Screen):
        yield from super().get_system_commands(screen)
        yield SystemCommand(
            "Sort by Name",
            "sort songs alphabetically",
            self.action_sort_name,  # this is your action
        )
        yield SystemCommand(
            "Sort by created",
            "sort songs by creation date",
            self.action_sort_created,  # this is your action
        )
        yield SystemCommand(
            "Sort by Modified",
            "Sort songs by modified date",
            self.action_sort_modified,  # this is your action
        )
    
    async def action_sort_name(self) -> None:
        await self.sort_boxes(key="title")
    
    async def action_sort_created(self) -> None:
        await self.sort_boxes(key="created_at")
    
    async def action_sort_modified(self) -> None:
        await self.sort_boxes(key="modified_at")


# API INFORMATION
def wait_for_port(host: str, port: int, timeout_s: float = 5.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        # within the window, get the socket, try to connect, and it if fails, wait (unless time is up)
        with socket.socket() as sock:
            sock.settimeout(0.5)
            try:
                sock.connect((host, port))
                return True
            except OSError:
                time.sleep(0.1)
    return False

def start_api() -> subprocess.Popen:
    # make a subprocess to start uvicorn
    env = os.environ.copy()
    env.setdefault("MDO_API_URL", "http://127.0.0.1:8000") # default address
    cmd = ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"]
    return subprocess.Popen(cmd, env=env)
        


# ENTRY POINT

if __name__ == "__main__":
    # also starting the backend. yum!
    api_proc = start_api()
    try:
        if not wait_for_port("127.0.0.1", 8000):
            raise RuntimeError("API did not start in time")
        
        app = MdoApp()
        app.run()
    finally:
        api_proc.terminate()
        api_proc.wait(timeout=5)
