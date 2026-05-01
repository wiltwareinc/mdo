# wiltware 2026, some help/teaching from ChatGPT EDU Codex 5.3
import logging
import os
from app.config import get_config
from pathlib import Path
from typing import Dict
from fastapi.responses import FileResponse
from typing_extensions import List
from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Query, status

from app.deps import get_file_manager
from app.schemas import (
    AlbumCreate,
    AlbumOut,
    AlbumUpdate,
    LyricCreate,
    ProjectCreate,
    SongCreate,
    SongOut,
    SongUpdate,
)
from models.file_manager import FileManager
router = APIRouter()


logging.basicConfig(
    filename="api.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

### SONGS ###
@router.get("/songs", response_model=List[SongOut])
def list_songs(fm: FileManager = Depends(get_file_manager)) -> List[Dict]:
    fm.refresh_songs()
    return fm.songs
    
@router.get("/songs/{slug}", response_model=SongOut)
def get_song(slug: str, fm: FileManager = Depends(get_file_manager)) -> Dict:
    fm.refresh_songs() # is this needed if it's cached'
    for song in fm.songs: # this also feels inefficient
        if song["slug"] == slug:
            return song
    # uh oh!
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Song not found")
    
@router.post("/songs", response_model=SongOut, status_code=status.HTTP_201_CREATED)
def create_song(payload: SongCreate, fm: FileManager = Depends(get_file_manager)) -> dict:
    created = fm.create_song(payload.title, payload.args)
    if created is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Song already exists or could not be created")
        # ^ possible a better detail
    fm.refresh_songs()
    for song in fm.songs: #? can't re just return the slug that create_song makes?
        if song["slug"] == created.name:
            return song
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Song created but not found")
    
@router.patch("/songs/{slug}", response_model=SongOut)
def update_song(slug: str, payload: SongUpdate, fm: FileManager = Depends(get_file_manager)) -> dict:
    logging.debug("starting to update song now")
    target = fm.droot / "songs" / slug
    updated = fm.edit_song(target, payload.title, payload.default_project)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Song not found or invalid update")
    fm.refresh_songs()
    for song in fm.songs: #? can't re just return the slug that create_song makes?
        if song["slug"] == updated.name:
            return song
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Song updated but not found")
    
@router.post("/songs/{slug}/lyrics", response_model=SongOut)
def add_lyric(slug: str, payload: LyricCreate, fm : FileManager = Depends(get_file_manager)) ->dict:
    target = fm.droot / "songs" / slug
    created = fm.create_lyrics(target, payload.title)
    if created is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lyrics not added")
    # rebuild metadata so new lyric appears in API output
    if fm.edit_song(target, None, None) is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Lyric created but metadata update failed")
    fm.refresh_songs()
    for song in fm.songs: #? can't re just return the slug that create_song makes?
        if song["slug"] == slug:
            return song
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Lyric created but not found")
    
 
@router.post("/songs/{slug}/projects", response_model=SongOut)
def add_project(slug: str, payload: ProjectCreate, fm : FileManager = Depends(get_file_manager)) ->dict:
    target = fm.droot / "songs" / slug
    created = fm.create_project(target, payload.title, payload.type)
    if created is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not added")
    # rebuild metadata so new project/default is reflected in API output
    if fm.edit_song(target, None, None) is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Project created but metadata update failed")
    fm.refresh_songs()
    for song in fm.songs: #? can't re just return the slug that create_song makes?
        if song["slug"] == slug:
            return song
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Project created but not found")
        
    
### ALBUMS ###
    
@router.get("/albums", response_model=List[AlbumOut])
def list_albums(fm: FileManager = Depends(get_file_manager)) -> List[dict]:
    fm.refresh_albums()
    return fm.albums 

@router.get("/albums/{slug}", response_model=AlbumOut)
def get_album(slug: str, fm: FileManager = Depends(get_file_manager)) -> dict:
    fm.refresh_albums()
    for album in fm.albums:
        if album["slug"] == slug:
            return album
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Album not found")
    
@router.post("/albums", response_model=AlbumOut, status_code=status.HTTP_201_CREATED)
def create_album(payload: AlbumCreate, fm: FileManager = Depends(get_file_manager)) -> dict:
    created = fm.create_album(payload.title, payload.tracklist if payload.tracklist is not None else [])
    if created is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Album already title or could not be created")
        # ^ possible a better detail
    fm.refresh_albums()
    for album in fm.albums: #? can't re just return the slug that create_album makes?
        if album["slug"] == created.name:
            return album
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Album created but not found")
    
@router.patch("/albums/{slug}", response_model=AlbumOut)
def update_album(slug: str, payload: AlbumUpdate, fm: FileManager = Depends(get_file_manager)) -> dict:
    target = fm.droot / "albums" / slug
    updated = fm.edit_album(target, payload.title, payload.tracklist)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Album not found or invalid update")
    fm.refresh_albums()
    for album in fm.albums: #? can't re just return the slug that create_album makes?
        if album["slug"] == updated.name:
            return album
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Album updated but not found")
    
### Scary!
@router.get("/files/{path:path}")
def get_file(path: str = PathParam(...), mode: str = Query("text")):
    target: Path = resolve_path(path)
    if mode == "raw":
        # raw binaries, for ex Reaper files
        return FileResponse(target)
    if mode == "text":
        return {
            "path": path,
            "content": target.read_text(encoding="utf-8")
        }
    raise HTTPException(status_code=400, detail="Invalid mode")

def resolve_path(rel_path: str) -> Path:
    """Check to see if the path is valid"""
    root = get_config().root
    target = (root /rel_path).resolve()
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if root not in target.parents and target != root:
        raise HTTPException(status_code=404, detail="File not found")
    if target.is_dir():
        raise HTTPException(status_code=400, detail="Path is a directory")
    return target
