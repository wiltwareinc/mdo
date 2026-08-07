# wiltware 2026
"""
Core domain models and rules for MDO.

METADATA RESPONSIBILITIES
-------------------------
Portable JSON manifests contain defined, authoritative information:

- Stable identity
- User-authored titles, descriptions, tags, and notes
- User selections, such as the default project
- Album membership, ordering, and relationships
- Creation and update timestamps

SQLite contains computed, observed, or cached information:

- Files and directories discovered during scanning
- Storage locations and resolved absolute paths
- Availability and last-seen state
- Counts, search data, and scan status

SQLite may copy manifest fields for fast queries, but the JSON manifest remains
authoritative. Deleting SQLite must not permanently destroy user-owned data.

IDENTIFIERS
-----------
Every durable domain entity uses a prefixed UUIDv4:

- song_<uuid>
- album_<uuid>
- asset_<uuid>
- sequence_<uuid>
- track_<uuid>
- collection_<uuid>
- collection_entry_<uuid>
- storage_<uuid>

A song or album uses the field "id", not "storage_id". A storage ID identifies
a storage root, not the creative work stored on it.

SONG MANIFEST
-------------
A version-2 song manifest contains:

- schema_version
- id
- title
- description
- tags
- assets
- default_project_id
- created_at
- updated_at

The assets list is not a complete inventory of the song directory. Ordinary
lyrics, projects, and renders may be discovered from the filesystem without
receiving IDs or being written into the manifest.

An item becomes a registered asset only when MDO must preserve a durable fact
about it. Examples include selecting it as the default project, referencing it
from another entity, or attaching user-authored metadata to it.

Registered assets live inside the owning song or album manifest. They do not
need individual sidecar metadata files.

ASSETS
------
An asset initially contains:

- id
- kind
- purpose
- title
- optional description
- path

The path is relative to the owning song or album directory. It must never be
absolute and must not escape the owner through "..".

"kind" describes what an asset is:

- project
- audio
- document
- image
- other

"purpose" describes why the asset is registered. Possible purposes include:

- song_session
- album_session
- lyrics
- mix
- master
- stem
- artwork
- notes
- reference

Only purposes required by real workflows should be implemented initially.
The first required registered asset is likely a project selected through
default_project_id.

ALBUM MANIFEST
--------------
A version-2 album manifest contains:

- schema_version
- id
- title
- description
- tags
- primary_sequence_id
- sequences
- collections
- assets
- created_at
- updated_at

A sequence is one ordered version of an album, such as the main release,
deluxe edition, vinyl order, or alternate running order.

Each sequence contains track entries. Array position is the authoritative
track order. A track entry has its own stable ID and references a song ID,
allowing the same song to appear more than once with different notes or an
album-specific title.

For now, track entries do not select a master asset. Add that relationship only
if the real workflow needs albums to remember an exact song render.

A collection groups related material that is not necessarily part of a release
sequence, such as bonus candidates, outtakes, or demos.

REPLICAS AND BACKUPS
--------------------
Replica information is observed and indexed rather than listed in song or
album manifests.

If the same stable song ID is found in several locations, SQLite records one
logical song with several observed copies. The most recently updated manifest
acts as the current working copy. Older copies remain available as backups and
must not be automatically overwritten, synchronized, or deleted.

The runtime view may combine location and availability information, but it
must not merge conflicting JSON fields. Older manifest contents should remain
available for an explicit restore.

VALIDATION
----------
- Tags are normalized to lowercase and deduplicated.
- Timestamps must be timezone-aware ISO 8601 values.
- Unknown fields in a recognized schema version are rejected.
- Invalid or unsupported manifests are reported and left untouched.
- Scanning must not modify manifests merely because new files were discovered.

Full JSON examples live under tests/fixtures/.
"""
