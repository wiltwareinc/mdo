# wiltware
# shared list screen helpers
# note: authored by ChatGPT Codex 5.3
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header


class BaseListScreen(Screen):
    LIST_ID = "item_list"

    def compose(self):
        self.boxes = [] # this seems like a hack but
        yield Header()
        yield VerticalScroll(id=self.LIST_ID)
        yield Footer()

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
        boxes = sorted(self.boxes, key=lambda b: self._get_data(b).get(key, "").lower())
        with self.app.batch_update():
            last = None
            for box in boxes:
                if last is None:
                    item_list.move_child(box, before=0, after=None)
                else:
                    item_list.move_child(box, after=last)
                last = box
        item_list.scroll_home(animate=False)
