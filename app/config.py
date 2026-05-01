# wiltware 2026
# configuration layout
# json will look something like:
# {
#     "root:" "~/Projects/music",
#     "templates": {
#         "Reaper": "~/Media/Templates/reaper_default.RPP",
#     }
# }
from __future__ import annotations
from dataclasses import dataclass
import json
import os
from pathlib import Path


@dataclass
class MdoConfig:
    root: Path
    templates: dict[str, ProjectTemplate] # ex "Reaper": ["path":<path_file>, "folder": false]
    # api stuff soon?

@dataclass
class ProjectTemplate:
    root: Path
    folder: bool = False

def default_config_path() -> Path:
    # temporary: inside of the working directory
    return Path.cwd() / ".config.json"

def load_config_file(path: Path) -> dict:
    if not path.exists():
        return {}

    with open(path, "r") as f:
        return json.load(f)

def expand_optional_path(v: str | None, resolve: bool = True) -> Path | None:
    # helper function to ensure we dont try to exdpand None
    if not v:
        return None
    path = Path(v).expanduser()
    return path.resolve() if resolve else path


def get_config() -> MdoConfig:
    config_path = Path(os.getenv("MDO_CONFIG", default_config_path())).expanduser()
    raw = load_config_file(config_path)

    music_root_raw = os.getenv("MDO_ROOT") or raw.get("root") # priority to runtime
    music_root  = expand_optional_path(music_root_raw)
    if music_root is None:
        raise ValueError("music_root is not set")

    raw_templates = raw.get("templates", {})
    templates = {}

    if isinstance(raw_templates, dict): #?
        for name, value in raw_templates.items():
            if isinstance(value, str):
                path = expand_optional_path(value, resolve = False)
                if path is not None:
                    templates[name] = ProjectTemplate(root=path)
            elif isinstance(value, dict): # more info for the project templates
                path = expand_optional_path(value.get("path"), resolve=False)
                folder = bool(value.get("folder", False))
                if path is not None:
                    templates[name] = ProjectTemplate(root=path, folder=folder)

    return MdoConfig(
        root=music_root,
        templates=templates,
    )