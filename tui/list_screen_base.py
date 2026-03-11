# wiltware
# shared list screen helpers
# note: authored by ChatGPT Codex 5.3
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header


class BaseListScreen(Screen):
    LIST_ID = "item_list"

    def compose(self):
        self.boxes = []  # this seems like a hack but
        yield Header()
        with Horizontal(id="screen_switcher"):
            yield Button("Songs", id="go_songs")
            yield Button("Albums", id="go_albums")
        yield VerticalScroll(id=self.LIST_ID)
        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "go_songs":
            await self.app.run_action("show_songs")
        if event.button.id == "go_albums":
            await self.app.run_action("show_albums")

    def on_resume(self) -> None:
        self.set_focus(self.query_one(f"#{self.LIST_ID}", VerticalScroll))

    def _get_data(self, box):  # pragma: no cover - must be implemented by subclasses
        raise NotImplementedError

    def filter_boxes(self, query: str) -> None:
        q = query.lower().strip()
        for box in self.boxes:
            title = self._get_data(box).get("title", "").lower()
            box.display = q in title if q else True

    async def sort_boxes(self, key: str) -> None:
        item_list = self.query_one(f"#{self.LIST_ID}", VerticalScroll)
        reverse = key in {"modified_at"}
        boxes = sorted(
            self.boxes,
            key=lambda b: self._get_data(b).get(
                key, ""
            ),  # note: lower() removed due to it seeming to by unncessesary
            reverse=reverse,
        )
        with self.app.batch_update():
            last = None
            for box in boxes:
                if last is None:
                    item_list.move_child(box, before=0, after=None)
                else:
                    item_list.move_child(box, after=last)
                last = box
        item_list.scroll_home(animate=False)
