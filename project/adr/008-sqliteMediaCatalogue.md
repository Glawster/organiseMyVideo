# ADR-008: Use one SQLite catalogue as the UI record

## Status

Accepted — 2026-09-04

## Context

Camera-card inventory already persists SQLite snapshots. Movies and TV are
still examined through folders, MCM XML, and a JSON lookup cache. The operator
wants the desktop UI to read a SQL record, with scans updating that record,
rather than walking storage as the primary catalogue.

ADR-007 placed camera snapshots in
`~/.local/state/organiseMyVideo/cameraInventory.sqlite`. A second JSON file
cannot serve the same UI query model.

## Options considered

1. Keep movies and TV on the filesystem and JSON cache; let the UI scan disks.
2. Store every collection in one SQLite catalogue under application local
   state. Card inventory, library rescan, and later UI queries share that file.
   Scans replace or append the relevant tables. JSON remains an organiser
   lookup cache, not the UI source.
3. Give movies, TV, and cards separate SQLite files.

## Decision

Use option 2. The application catalogue file is

```text
$XDG_STATE_HOME/organiseMyVideo/mediaCatalogue.sqlite
```

defaulting to `~/.local/state/organiseMyVideo/mediaCatalogue.sqlite`.

Camera inventory tables stay in this file. Library rescan and metadata rebuilds
from storage refresh `movieItem`, `tvSeries`, and `tvEpisode`. The Qt browser
in REQ-002 reads these tables and does not treat folder walks or
`metadataLibrary.json` as the catalogue of record.

Card inventory still requires `--confirm` before writing snapshots, because
that assigns a numeric card identity. Movie and TV catalogue refresh is
application-state indexing of files already in the archive, so a library scan
updates those tables even when media mutations remain dry-run.

## Rationale

One queryable file gives the UI a stable contract. Scans, not ad-hoc
filesystem crawls, keep it current. Keeping JSON as a move-time lookup avoids
rewriting the organiser in the same increment.

## Consequences

- ADR-007's camera tables remain; their file name becomes the shared
  catalogue path.
- REQ-002 must query SQLite rather than implementing a second library index.
- Catalogue refresh records known MCM and metadata-library identity; it
  must not re-identify titles by parsing filenames independently.
- Dash cam, GoPro, and DJI card snapshots share `cardInventory`.
- Tests inject the catalogue path and must not write the real user-state file.

## Related requirements

- [REQ-002: Qt media-library browser](../requirements/features/002-qtMediaLibraryBrowser.md)
- [REQ-009: Camera card inventory](../requirements/features/009-cameraCardInventory.md)
- [REQ-010: SQLite media catalogue](../requirements/features/010-sqliteMediaCatalogue.md)
- [REQ-011: Dash cam card support](../requirements/features/011-dashcamCardSupport.md)
