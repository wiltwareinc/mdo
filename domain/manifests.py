# wiltware 2026
# outline and validation for JSON manifests

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from pydantic.config import ConfigDict


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

class Entry(DomainModel):
    id: str
    song_id: str
    title_override: str | None = None
    notes: str = ""

class Group(DomainModel):
    id: str
    title:str
    description: str = ""
    entries: list[Entry] = Field(default_factory=list)

class Sequence(Group):
    """order is preserved"""

class Collection(Group):
    """order is unnecessary"""

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

    sequences: list[Sequence] = Field(default_factory=list)
    collections: list[Collection] = Field(default_factory=list) #?
    
    assets: list[Asset] = Field(default_factory=list)

    created_at: datetime
    updated_at: datetime