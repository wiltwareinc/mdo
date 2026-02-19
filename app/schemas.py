# wiltware 2026
# schemas for FastApi
from typing import List, Optional

from pydantic import BaseModel


class FileRef(BaseModel):
    path: str


class TrackRef(BaseModel):
    slug: str
    number: int


class SongOut(BaseModel):
    slug: str
    title: str
    timezone: str
    lyrics: List[FileRef]
    projects: List[FileRef]
    default_project: Optional[str]
    renders: List[FileRef]
    created_at: str
    modified_at: str
    
class AlbumOut(BaseModel):
    slug: str
    title: str
    timezone: str
    tracklist: List[TrackRef]
    created_at: str
    modified_at: str
    
class SongCreate(BaseModel):
    title: str
    args: List[str] = []

class SongUpdate(BaseModel):
    name: Optional[str] = None
    default_project: Optional[int] = None

class AlbumCreate(BaseModel):
    title:str
    tracklist: List[str]
    
class AlbumUpdate(BaseModel):
    name: Optional[str] = None
    tracklist: Optional[List[str]] = None