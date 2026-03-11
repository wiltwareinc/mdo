# wiltware
# barebones TUI to use this without a frontend using Textual
import os
import socket
import sys
import threading
import time
from pathlib import Path

import uvicorn
from textual.app import App
from textual.binding import Binding
from textual.screen import ModalScreen, Screen
from textual.widgets import Input

from app.main import app as api_app
from tui.album_screen import AlbumScreen
from tui.song_screen import SongScreen


def resolve_css_path() -> str:
    local_css = Path(__file__).with_name("bare_tui.tcss")
    if local_css.exists():
        return str(local_css)

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled_css = Path(meipass) / "tui" / "bare_tui.tcss"
        if bundled_css.exists():
            return str(bundled_css)
        fallback_css = Path(meipass) / "bare_tui.tcss"
        if fallback_css.exists():
            return str(fallback_css)

    return "bare_tui.tcss"


class SearchScreen(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
    ]
    def compose(self):
        self.previous_focus = self.app.screen.focused
        yield Input(placeholder="Search by title...", id="search")

    def on_mount(self):
        self.query_one(Input).focus()

    async def on_input_changed(self, event: Input.Changed) -> None:
        query = event.value.strip().lower()
        self.app.filter_active_boxes(query)

    async def on_input_submitted(self, _) -> None:
        self.dismiss()


class MdoApp(App):
    """Entry point."""

    COMMAND_PALETTE_BINDING = "colon"
    CSS_PATH = resolve_css_path()
    BINDINGS = [
        Binding("n", "sort_name", "Sort by name", show=True),
        Binding("c", "sort_created", "Sort by created", show=True),
        Binding("m", "sort_modified", "Sort by modified", show=True),
        Binding("/", "search", "Search", show=True),
        Binding("s", "show_songs", "Songs", show=True),
        Binding("a", "show_albums", "Albums", show=True),
        Binding("Q", "quit", "Quit"),
    ]

    async def on_mount(self) -> None:
        await self.push_screen(SongScreen())

    def _active_list_screen(self) -> Screen | None:
        stack = getattr(self, "screen_stack", [])
        for screen in reversed(stack):
            if hasattr(screen, "filter_boxes") and hasattr(screen, "sort_boxes"):
                return screen
        return None

    def filter_active_boxes(self, query: str) -> None:
        screen = self._active_list_screen()
        if screen is not None:
            screen.filter_boxes(query)

    async def action_sort_name(self) -> None:
        screen = self._active_list_screen()
        if screen is not None:
            await screen.sort_boxes(key="title")

    async def action_sort_created(self) -> None:
        screen = self._active_list_screen()
        if screen is not None:
            await screen.sort_boxes(key="created_at")

    async def action_sort_modified(self) -> None:
        screen = self._active_list_screen()
        if screen is not None:
            await screen.sort_boxes(key="modified_at")

    async def action_search(self) -> None:
        await self.push_screen(SearchScreen())

    async def action_show_songs(self) -> None:
        await self.push_screen(SongScreen())

    async def action_show_albums(self) -> None:
        await self.push_screen(AlbumScreen())

    async def action_quit(self) -> None:
        self.exit()


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


def start_api() -> tuple[uvicorn.Server, threading.Thread]:
    # run uvicorn in-process so packaged binaries do not depend on external imports
    os.environ.setdefault("MDO_API_URL", "http://127.0.0.1:8000")
    config = uvicorn.Config(api_app, host="127.0.0.1", port=8000, log_level="info")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return server, thread


# ENTRY POINT
if __name__ == "__main__":
    # also starting the backend. yum!
    api_server, api_thread = start_api()
    try:
        if not wait_for_port("127.0.0.1", 8000):
            raise RuntimeError("API did not start in time")

        app = MdoApp()
        app.run()
    finally:
        api_server.should_exit = True
        api_thread.join(timeout=5)
