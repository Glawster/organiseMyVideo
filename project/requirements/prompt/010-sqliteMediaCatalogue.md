# Requirement: 010 — project/requirements/features/010-sqliteMediaCatalogue.md

Role: implement and verify

Read the requirement, ADR-008, and `documentation/mediaCatalogue.md`. Persist
movies, TV, and camera snapshots in one camelCase SQLite catalogue under
application local state. Refresh movie and TV tables from storage during
library rescan by recording known MCM and metadata-library identity; do not
re-identify from a second filename parser. Keep `metadataLibrary.json` as
the organiser lookup cache. Do not implement Qt.

Verify with `pytest` and `git diff --check`.
