# wiltware 2026
# updated api for new metadata system


from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.config import get_config
from domain.manifests import AlbumManifest, SongManifest, StorageManifest
from persistence.album_library import add_album_entry, create_album, list_albums, register_album_session, remove_album_entry, reorder_album_entry
from persistence.song_library import create_song, list_songs
from persistence.storage import initialize_storage, load_storage_manifest

router = APIRouter(prefix="/v2")

class SongCreateV2(BaseModel):
    title: str

class AlbumCreateV2(BaseModel):
    title: str
    song_ids: list[str]

class AlbumSessionCreateV2(BaseModel):
    title: str
    relative_path: str
    entry_ids: list[str]

class AlbumEntryCreateV2(BaseModel):
    song_id: str
    sequence_id: str | None = None
    position: int | None = None

class AlbumEntryReorderV2(BaseModel):
    position: int
    sequence_id: str | None = None

class StorageInitializeV2(BaseModel):
    name: str

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

@router.post(
    "/albums/{album_id}/sessions",
    response_model=AlbumManifest,
    status_code=status.HTTP_201_CREATED
)
def post_album_session(
    album_id: str,
    payload: AlbumSessionCreateV2
) -> AlbumManifest:
    try:
        return register_album_session(
            root=get_config().root,
            album_id=album_id,
            title=payload.title,
            relative_path=payload.relative_path,
            entry_ids=payload.entry_ids
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e

@router.post(
    "/albums/{album_id}/entries",
    response_model=AlbumManifest,
    status_code=status.HTTP_201_CREATED,
)
def post_album_entry(
    album_id: str,
    payload: AlbumEntryCreateV2
) -> AlbumManifest:
    try:
        return add_album_entry(
            root=get_config().root,
            album_id=album_id,
            song_id=payload.song_id,
            sequence_id=payload.sequence_id,
            position=payload.position
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e

@router.patch(
    "/albums/{album_id}/entries/{entry_id}",
    response_model=AlbumManifest
)
def patch_album_entry_position(
    album_id: str,
    entry_id: str,
    payload: AlbumEntryReorderV2
) -> AlbumManifest:
    try:
        return reorder_album_entry(
            root=get_config().root,
            album_id=album_id,
            entry_id=entry_id,
            position=payload.position,
            sequence_id=payload.sequence_id,
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e

@router.delete(
    "/albums/{album_id}/entries/{entry_id}",
    response_model=AlbumManifest,
)
def delete_album_entry(
    album_id: str,
    entry_id: str,
    sequence_id: str | None = None,
) -> AlbumManifest:
    try:
        return remove_album_entry(
            root=get_config().root,
            album_id=album_id,
            entry_id=entry_id,
            sequence_id=sequence_id
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        ) from e

@router.post(
    "/storage",
    response_model=StorageManifest,
    status_code=status.HTTP_201_CREATED,
)
def post_storage(payload: StorageInitializeV2) -> StorageManifest:
    try:
        return initialize_storage(
            root=get_config().root,
            name=payload.name,
        )
    except FileExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e

@router.get(
    "/storage",
    response_model=StorageManifest
)
def get_storage() -> StorageManifest:
    try:
        return load_storage_manifest(get_config().root)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Storage not initialized"
        ) from e
