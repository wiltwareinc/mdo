# wiltware 2026
# extra utilities for backend function
from pathlib import Path

from app.config import get_config

def find_project_file(project: Path) -> Path:
    """Find a project file inside of a project folder"""
    # verify
    if not project.is_dir():
        return project # womp womp

    # get recognized suffixes
    suffixes = []
    config = get_config()
    for t in config.templates.values():
        path = t.root
        if path.suffix:
            suffixes.append(path.suffix)
    
    files = sorted(
        p for p in project.rglob("*") 
        if p.is_file()
        and p.suffix in suffixes # ensure it has the ending
    ) # recursive finding for folders

    for f in files:
        if f.stem == f.parent.name: # nested folder check
            return f

    # non-nested, break away the YYYMMDD- from the beginning of the folder
    project_title = project.name.split("-", 1)[1] if "-" in project.name else project.name
    title_candidates = {project_title}
    base_title, sep, counter = project_title.rpartition("-") # properly seperate digit at end if needed
    if sep and counter.isdigit(): # it is a counter
        title_candidates.add(base_title) # get the right, flat name to check against
    

    for f in files:
        if f.stem in title_candidates:
            return f
    
    return files[0] if files else project
