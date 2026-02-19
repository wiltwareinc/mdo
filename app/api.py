# wiltware 2026, some help/teaching from ChatGPT EDU Codex 5.3
from typing import Dict
from typing_extensions import List
from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import get_file_manager
from app.schemas import (
    AlbumCreate,
    AlbumOut,
    AlbumUpdate,
    SongCreate,
    SongOut,
    SongUpdate,
)
from models.file_manager import FileManager
router = APIRouter()

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
    target = fm.droot / "songs" / slug
    updated = fm.edit_song(target, payload.name, payload.default_project)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Song not found or invalid update")
    fm.refresh_songs()
    for song in fm.songs: #? can't re just return the slug that create_song makes?
        if song["slug"] == updated.name:
            return song
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Song updated but not found")
    
    
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
    created = fm.create_album(payload.title, payload.tracklist)
    if created is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Album already exists or could not be created")
        # ^ possible a better detail
    fm.refresh_albums()
    for album in fm.albums: #? can't re just return the slug that create_album makes?
        if album["slug"] == created.name:
            return album
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Album created but not found")
    
@router.patch("/albums/{slug}", response_model=AlbumOut)
def update_album(slug: str, payload: AlbumUpdate, fm: FileManager = Depends(get_file_manager)) -> dict:
    target = fm.droot / "albums" / slug
    updated = fm.edit_album(target, payload.name, payload.tracklist)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Album not found or invalid update")
    fm.refresh_albums()
    for album in fm.albums: #? can't re just return the slug that create_album makes?
        if album["slug"] == updated.name:
            return album
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Album updated but not found")
    