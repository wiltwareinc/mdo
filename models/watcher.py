# wiltware 2026, with help/tutoring from ChatGPT EDU Codex 5.3
from app.config import get_config
from dataclasses import dataclass, field
from pathlib import Path
import time
from typing import Callable, Dict, Optional, Tuple
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

# call back signature (what is this?)
OnChange = Callable[[str, Path], None]

@dataclass
class Debouncer: # prevents duplicate triggers so we can make sure it doesn't constantly update at once
    window_s: float = 0.5
    pending: Dict[Tuple[str, Path], float] = field(default_factory=dict)
    
    def push(self, kind: str, path: Path) -> None:
        self.pending[(kind, path)] = time.time()
    
    def flush(self,callback: OnChange) -> None:
        now = time.time()
        ready = [(kind, path) for (kind, path), t in self.pending.items() if now - t >= self.window_s]
        for key in ready:
            kind, path = key
            self.pending.pop(key, None)
            callback(kind, path)
            
class MdoEventHandler(FileSystemEventHandler): # pushes changes into debounce
    def __init__(self, root: Path, on_change: OnChange, debouncer: Debouncer) -> None:
        self.root = root
        self.on_change = on_change
        self.debouncer = debouncer
        
    def on_any_event(self, event: FileSystemEvent) -> None:
        # return super().on_any_event(event)
        # skip anything that's not created or moved
        if event.event_type not in ("created", "moved"):
            # this may be too strict, we might want modified
            return
        raw = event.src_path
        src_path = raw.decode() if isinstance(raw, bytes) else raw # type checker for string
        print(f"\tsrc_path: {src_path}\n\tevent_type: {event.event_type}")
        if str(src_path).endswith(".metadata.json"):
            # TEMP: skip over metadata rewrites so it doesn't get caught in a loop
            return
        kind_path = normalize_event_path(self.root, Path(src_path))
        if kind_path is None:
            return
        kind, path = kind_path
        self.debouncer.push(kind, path)
        
def normalize_event_path(root: Path, src: Path) -> Optional[Tuple[str, Path]]:
    """
    gives a path anywhere under root, return a slug_path based on the song or album
    """
    try:
        rel = src.resolve().relative_to(root.resolve())
    except ValueError:
        return None
        
    parts = rel.parts #?
    if len(parts) < 2:
        return None
    
    group = parts[0]
    slug = parts[1]
    if group == "songs":
        return ("song", root / "songs" / slug)
    if group == "albums":
        return ("album", root / "albums" / slug)
    return None
        
def run_watcher(root: Path, on_change: OnChange, window_s: float = 0.5) -> None:
    """
    Wires everything together, runs a loop that periodically flushes debounced events
    """
    debouncer = Debouncer(window_s=window_s)
    handler = MdoEventHandler(root, on_change, debouncer)
    
    observer = Observer()
    observer.schedule(handler, str(root), recursive=True)
    observer.start()
    
    try:
        while True:
            time.sleep(0.1)
            debouncer.flush(on_change)
    finally:
        observer.stop()
        observer.join()
        
if __name__ == "__main__":
    def _print_change(kind: str, path: Path) -> None:
        print(f"change: {kind} -> {path}")
    
    root_path = get_config().root
    run_watcher(root_path, _print_change)