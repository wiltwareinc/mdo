# wiltware 2026
# updated api for new metadata system

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.config import get_config
from domain.manifests import AlbumManifest, SongManifest
from persistence.album_library import create_album, list_albums
from persistence.song_library import create_song, list_songs

router = APIRouter(prefix="/v2")

class SongCreateV2(BaseModel):
    title: str

@router.get("/songs", response_model=list[SongManifest])
def get_songs() -> list[SongManifest]:
    return list_songs(get_config().root)

@router.post(
    "/songs",
    response_model=SongManifest,
    status_code=status.HTTP_201_CREATED,
)
def post_song(payload: SongCreateV2) -> SongManifest:
    try:
        return create_song(get_config().root, payload.title)
    except FileExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        ) from e

class AlbumCreateV2(BaseModel):
    title: str
    song_ids: list[str]

@router.get("/albums", response_model=list[AlbumManifest])
def get_albums() -> list[AlbumManifest]:
    return list_albums(get_config().root)

@router.post(
    "/albums",
    response_model=AlbumManifest,
    status_code=status.HTTP_201_CREATED,
)
def post_album(payload: AlbumCreateV2) -> AlbumManifest:
   try:
       return create_album(get_config().root, payload.title, payload.song_ids)
   except FileExistsError as e: 
       raise HTTPException(
           status_code=status.HTTP_409_CONFLICT,
           detail=str(e)
       ) from e