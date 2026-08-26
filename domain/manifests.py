# wiltware 2026
# outline and validation for JSON manifests

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic.config import ConfigDict

from uuid import UUID

def validate_prefixed_uuid(value: str, prefix: str) -> str:
    """helper function to verify a uuid with a prefix"""
    expected_prefix = f"{prefix}_"

    if not value.startswith(expected_prefix):
        raise ValueError(f"expected {prefix} UUID, got {value}")

    uuid_text = value.removeprefix(expected_prefix)

    try:
        parsed = UUID(uuid_text)
    except ValueError as error:
        raise ValueError("ID must contain a valid UUID") from error

    if parsed.version != 4:
        raise ValueError("ID must contain a UUIDv4")

    if str(parsed) != uuid_text:
        raise ValueError("UUID must use a canonical lowercase formatting")
    
    return value


class DomainModel(BaseModel):
    """shared validation behavious for domain models"""

    model_config = ConfigDict(extra="forbid") # reject incorrect JSON values

class AssetKind(StrEnum):
    PROJECT = "project"
    AUDIO = "audio"
    DOCUMENT = "document" # or lyric?
    IMAGE = "image"
    OTHER = "other" # generic bin

class AssetPurpose(StrEnum):
    SONG_SESSION = "song_session"
    ALBUM_SESSION = "album_session"
    

class Asset(DomainModel):
    id: str
    kind: AssetKind
    purpose: AssetPurpose
    title: str
    description: str | None = None
    path: str # or Path?

    @field_validator("id")
    def validate_id(cls, value: str) -> str:
        return validate_prefixed_uuid(value, "asset")

class SongManifest(DomainModel):
    schema_version: Literal[2]

    id: str
    title: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    
    assets: list[Asset] = Field(default_factory=list)
    default_project_id: str | None = None

    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_default_project(self):
        if self.default_project_id is None:
            return self # why not None?

        matching_assets = [
            asset
            for asset in self.assets
            if asset.id == self.default_project_id
        ]

        if not matching_assets:
            raise ValueError(
                "default_project_id must reference an asset in this song"
            )

        if matching_assets[0].kind != AssetKind.PROJECT:
            raise ValueError(
                "default_project_id must reference a project asset"
            )

        return self

    @field_validator("id")
    def validate_id(cls, value: str) -> str:
        return validate_prefixed_uuid(value, "song")

class Entry(DomainModel):
    id: str
    song_id: str
    album_asset_id: str | None = None
    title_override: str | None = None
    notes: str = ""

    @field_validator("id")
    def validate_id(cls, value: str) -> str:
        return validate_prefixed_uuid(value, "entry")

    @field_validator("song_id")
    def validate_song_id(cls, value: str) -> str:
        return validate_prefixed_uuid(value, "song")

    @field_validator("album_asset_id")
    def validate_album_asset_id(cls, value: str | None) -> str | None:
        # TODO
        if value is not None:
            return validate_prefixed_uuid(value, "asset")
        return None


class Group(DomainModel):
    id: str
    title:str
    description: str = ""
    entries: list[Entry] = Field(default_factory=list)

class Sequence(Group):
    """order is preserved"""

    @field_validator("id")
    def validate_id(cls, value: str) -> str:
        return validate_prefixed_uuid(value, "sequence")

class Collection(Group):
    """order is unnecessary"""

    @field_validator("id")
    def validate_id(cls, value: str) -> str:
        return validate_prefixed_uuid(value, "collection")

class AlbumManifest(DomainModel):
    schema_version: Literal[2]

    id: str
    title: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)

    primary_sequence_id: str # out of possibly multiple sequences, which one is the main one

    @model_validator(mode='after')
    def validate_primary_sequence_id(self):
        if self.primary_sequence_id not in [s.id for s in self.sequences]:
            raise ValueError("primary_sequence_id must reference a sequence in this manifest")
        return self

    @model_validator(mode='after')
    def validate_album_asset_references(self):
        assets_by_id = {
            asset.id : asset
            for asset in self.assets
        }

        groups = [*self.sequences, *self.collections]

        for group in groups:
            for entry in group.entries:
                if entry.album_asset_id is None:
                    continue

                asset = assets_by_id.get(entry.album_asset_id)

                if asset is None:
                    raise ValueError("album_asset_id must reference an asset in this album")

                if asset.kind != AssetKind.PROJECT:
                    raise ValueError("album_asset_id must reference a project asset")

                if asset.purpose != AssetPurpose.ALBUM_SESSION:
                    raise ValueError("album_asset_id must reference an album session")
        return self
    
    sequences: list[Sequence] = Field(default_factory=list)
    collections: list[Collection] = Field(default_factory=list) #?
    
    assets: list[Asset] = Field(default_factory=list)

    created_at: datetime
    updated_at: datetime

    @field_validator("id")
    def validate_id(cls, value: str) -> str:
        return validate_prefixed_uuid(value, "album")