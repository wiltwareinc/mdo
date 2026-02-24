# wiltware
# barebones TUI to use this without a frontend using Textual
import os
import socket
import subprocess
import time
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Footer, Header, Static
from textual.widget import Widget

from tui.api_client import get_songs, get_song

class SongBox(Static):
    """
    Information for a song based on information
    """
    def __init__(self, song: dict, **kwargs) -> None:
        super().__init__(**kwargs)
        self.song = song

    def render(self) -> str:
        return f"title: {self.song['title']}\nslug: {self.song['slug']}"

class MdoApp(App):
    """entrypoint"""
    CSS_PATH = "bare_tui.tcss"

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        # yield SongBox({"slug": "testing", "title": "Test"})
        yield VerticalScroll(id="song_list")
        yield Footer()
    
    async def on_mount(self) -> None:
        songs = get_songs()
        song_list = self.query_one("#song_list", VerticalScroll)
        for song in songs:
            await song_list.mount(SongBox(song))


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
