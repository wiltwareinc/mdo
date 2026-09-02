# wiltware 2026
# updated api for new metadata system


from typing import Literal, cast

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.config import get_config
from domain.manifests import AlbumManifest, SongManifest, StorageManifest
from persistence.album_library import (
    AlbumMetadataChanges,
    add_album_entry,
    create_album,
    create_album_sequence,
    delete_album_sequence,
    list_albums,
    register_album_session,
    remove_album_entry,
    reorder_album_entry,
    update_album_metadata,
    update_album_sequence,
)
from persistence.album_library import (
    get_album as get_album_from_library,
)
from persistence.song_library import (
    SongMetaDataChanges,
    assign_album_session_to_song,
    create_song,
    create_song_project_from_template,
    list_songs,
    register_song_project,
    update_song_metadata,
)
from persistence.song_library import get_song as get_song_from_library
from persistence.storage import initialize_storage, load_storage_manifest

router = APIRouter(prefix="/v2")


class SongCreateV2(BaseModel):
    title: str


class SongUpdateV2(BaseModel):
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    default_project_id: str | None = None


class ProjectCreateV2(BaseModel):
    title: str
    relative_path: str
    parent_song: str | None = None
    make_default: bool = True


class ProjectFromTemplateCreateV2(BaseModel):
    template_name: str
    title: str | None = None
    make_default: bool = True


class AlbumSessionAssignmentV2(BaseModel):
    asset_id: str
    make_default: bool = True


class AlbumSequenceCreateV2(BaseModel):
    title: str
    description: str = ""


class AlbumSequenceUpdateV2(BaseModel):
    title: str | None = None
    description: str | None = None


class AlbumCreateV2(BaseModel):
    title: str
    song_ids: list[str]


class AlbumSessionCreateV2(BaseModel):
    title: str
    relative_path: str
    entry_ids: list[str] | None = None


class AlbumUpdateV2(BaseModel):
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None


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
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e


@router.post(
    "/songs/{song_id}/projects",
    response_model=SongManifest,
    status_code=status.HTTP_201_CREATED,
)
def post_song_project(song_id: str, payload: ProjectCreateV2) -> SongManifest:
    try:
        return register_song_project(
            root=get_config().root,
            song_id=song_id,
            title=payload.title,
            relative_path=payload.relative_path,
            parent_song=payload.parent_song,
            make_default=payload.make_default,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except FileExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e


@router.post(
    "/songs/{song_id}/album-sessions",
    response_model=SongManifest,
    status_code=status.HTTP_201_CREATED,
)
def post_song_album_session(
    song_id: str,
    payload: AlbumSessionAssignmentV2,
) -> SongManifest:
    try:
        return assign_album_session_to_song(
            root=get_config().root,
            song_id=song_id,
            asset_id=payload.asset_id,
            make_default=payload.make_default,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e


@router.get(
    "/songs/{song_id}",
    response_model=SongManifest,
)
def get_song(song_id: str) -> SongManifest:
    try:
        return get_song_from_library(get_config().root, song_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/albums", response_model=list[AlbumManifest])
def get_albums() -> list[AlbumManifest]:
    return list_albums(get_config().root)


@router.get("/albums/{album_id}", response_model=AlbumManifest)
def get_album(album_id: str) -> AlbumManifest:
    try:
        return get_album_from_library(get_config().root, album_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post(
    "/albums",
    response_model=AlbumManifest,
    status_code=status.HTTP_201_CREATED,
)
def post_album(payload: AlbumCreateV2) -> AlbumManifest:
    try:
        return create_album(get_config().root, payload.title, payload.song_ids)
    except FileExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e


@router.post(
    "/albums/{album_id}/sessions",
    response_model=AlbumManifest,
    status_code=status.HTTP_201_CREATED,
)
def post_album_session(album_id: str, payload: AlbumSessionCreateV2) -> AlbumManifest:
    try:
        return register_album_session(
            root=get_config().root,
            album_id=album_id,
            title=payload.title,
            relative_path=payload.relative_path,
            entry_ids=payload.entry_ids,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e


@router.post(
    "/albums/{album_id}/entries",
    response_model=AlbumManifest,
    status_code=status.HTTP_201_CREATED,
)
def post_album_entry(album_id: str, payload: AlbumEntryCreateV2) -> AlbumManifest:
    try:
        return add_album_entry(
            root=get_config().root,
            album_id=album_id,
            song_id=payload.song_id,
            sequence_id=payload.sequence_id,
            position=payload.position,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e


@router.patch("/albums/{album_id}/entries/{entry_id}", response_model=AlbumManifest)
def patch_album_entry_position(
    album_id: str, entry_id: str, payload: AlbumEntryReorderV2
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
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
            sequence_id=sequence_id,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


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


@router.get("/storage", response_model=StorageManifest)
def get_storage() -> StorageManifest:
    try:
        return load_storage_manifest(get_config().root)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Storage not initialized"
        ) from e


@router.patch(
    "/songs/{song_id}",
    response_model=SongManifest,
)
def patch_song_metadata(song_id: str, payload: SongUpdateV2) -> SongManifest:
    try:
        changes = cast(
            SongMetaDataChanges, cast(object, payload.model_dump(exclude_unset=True))
        )
        return update_song_metadata(
            root=get_config().root, song_id=song_id, changes=changes
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e


@router.patch("/albums/{album_id}", response_model=AlbumManifest)
def patch_album(
    album_id: str,
    payload: AlbumUpdateV2,
) -> AlbumManifest:
    try:
        changes = cast(
            AlbumMetadataChanges, cast(object, payload.model_dump(exclude_unset=True))
        )
        return update_album_metadata(
            root=get_config().root, album_id=album_id, changes=changes
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


class ProjectTemplateV2(BaseModel):
    name: str
    extension: str
    layout: Literal["single_file", "nested_folder"]


@router.get("/project-templates", response_model=list[ProjectTemplateV2])
def get_project_templates() -> list[ProjectTemplateV2]:
    templates = get_config().templates
    return [
        ProjectTemplateV2(
            name=name,
            extension=template.root.suffix,
            layout="nested_folder" if template.folder else "single_file",
        )
        for name, template in templates.items()
        if template.root.is_file() and template.root.suffix
    ]


@router.post(
    "/songs/{song_id}/projects/from-template",
    response_model=SongManifest,
    status_code=status.HTTP_201_CREATED,
)
def post_song_project_from_template(
    song_id: str, payload: ProjectFromTemplateCreateV2
) -> SongManifest:
    config = get_config()
    template = config.templates.get(payload.template_name)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{payload.template_name}' not found",
        )

    try:
        return create_song_project_from_template(
            root=config.root,
            song_id=song_id,
            template_path=template.root,
            nested_folder=template.folder,
            title=payload.title,
            make_default=payload.make_default,
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except FileExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/albums/{album_id}/sequences",
    response_model=AlbumManifest,
    status_code=status.HTTP_201_CREATED,
)
def post_album_sequence(album_id: str, payload: AlbumSequenceCreateV2) -> AlbumManifest:
    try:
        return create_album_sequence(
            root=get_config().root,
            album_id=album_id,
            title=payload.title,
            description=payload.description,
        )
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.patch(
    "/albums/{album_id}/sequences/{sequence_id}",
    response_model=AlbumManifest,
    status_code=status.HTTP_200_OK,
)
def patch_album_sequence(
    album_id: str, sequence_id: str, payload: AlbumSequenceUpdateV2
) -> AlbumManifest:
    try:
        return update_album_sequence(
            root=get_config().root,
            album_id=album_id,
            sequence_id=sequence_id,
            title=payload.title,
            description=payload.description,
        )
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.delete(
    "/albums/{album_id}/sequences/{sequence_id}",
    response_model=AlbumManifest,
)
def delete_album_sequence_route(
    album_id: str,
    sequence_id: str,
) -> AlbumManifest:
    try:
        return delete_album_sequence(
            root=get_config().root,
            album_id=album_id,
            sequence_id=sequence_id,
        )
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
