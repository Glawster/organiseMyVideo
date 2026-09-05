# 010: SQLite media catalogue

## Status

Completed

## Outcome

As a media-library operator, I need movies, TV episodes, and camera-card
snapshots stored in one SQLite catalogue that scans update so that the UI can
query a record instead of walking disks or reading the JSON lookup cache.

## Context

Camera inventory already writes SQLite. Movies and TV still live in storage
folders plus `metadataLibrary.json`, which is a move-time cache rather than a
browsable catalogue. The operator chose SQL as the UI record, refreshed when a
scan runs.

The catalogue path and table split are recorded in
[ADR-008](../../adr/008-sqliteMediaCatalogue.md).

## Scope

- Persist movies, TV series, TV episodes, and camera-card snapshots in
  `mediaCatalogue.sqlite` under the application local-state directory.
- Refresh movie and TV tables when library rescan or a storage metadata rebuild
  runs, recording known MCM / metadata-library identity rather than
  re-identifying from filenames.
- Keep card snapshots on confirmed `camera inventory` as today.
- Expose importable Python services that replace and read catalogue rows
  without argparse or Qt.
- Keep camelCase SQLite identifiers.
- Leave `metadataLibrary.json` as the organiser lookup cache.

## Out of scope

- Implementing the Qt widgets (REQ-002).
- Deleting or rewriting MCM `movie.xml` / episode XML as part of catalogue
  refresh.
- Merging physical SD-card files into movie or TV rows.
- Indexing home-video items, which is tracked by REQ-014.
- Inventorying non-camera USB volumes, which is tracked by REQ-015.

## Acceptance criteria

1. Given movie folders in a storage root, when a library scan refreshes the
   catalogue, then each `Title (Year)` folder is stored as a `movieItem` with
   path, title, year, and XML identity when present.
2. Given TV episode files under a TV storage root, when a library scan
   refreshes the catalogue, then series and episode rows are stored with the
   show, season, episode, title, and provider IDs already known from MCM XML
   or the metadata library (`tvSeries.tvdbId`/`tmdbId`/`imdbId`,
   `tvEpisode.tvdbEpisodeId`/`tmdbEpisodeId`/`imdbId`), falling back to the
   organiser filename parser and then folder names; missing IDs stay null
   and the catalogue does not scrape or re-parse identity on its own.
3. Given a second scan of the same libraries, when it completes, then movie and
   TV tables match current storage and do not keep rows for removed folders.
4. Given `camera inventory --confirm`, when it writes a snapshot, then card
   tables live in the same catalogue file as movie and TV tables.
5. Given the catalogue service is used directly, when it replaces or lists
   rows, then it does not depend on Qt or argparse.
6. Given dry-run library rescan, when it indexes storage, then the catalogue
   movie/TV tables are still updated because that is application state, while
   media files are not renamed.

## Dependencies and decisions

- [ADR-008: SQLite media catalogue as the UI record](../../adr/008-sqliteMediaCatalogue.md)
- [REQ-002: Qt media-library browser](002-qtMediaLibraryBrowser.md)
- [REQ-009: Camera card inventory](009-cameraCardInventory.md)
- [REQ-014: Home video catalogue](014-homeVideoCatalogue.md) — future extension
  of this catalogue.
- [REQ-015: USB volume inventory](015-usbVolumeInventory.md) — future extension
  of the removable-volume tables.

## Verification

- Unit tests with temporary movie and TV trees.
- Camera inventory still persists into the shared file.
- `pytest`
- `git diff --check`

## Traceability

- Implementation: `organiseMyVideo/mediaCatalogue.py`
- Tests: `tests/test_mediaCatalogue.py`
- Documentation: `documentation/mediaCatalogue.md`
- Pull request: pending
- Agent runs: None

## Change history

- 2026-09-04: created — operator chose SQLite as the UI record, updated on scan.
- 2026-09-04: completed — library rescan writes movie/TV rows; camera snapshots
  share `mediaCatalogue.sqlite`.
- 2026-09-04: clarified — delivered scope covers movie, TV, and camera-card
  rows; home video and USB extensions remain separately tracked by REQ-014 and
  REQ-015.
- 2026-09-04: changed — catalogue refresh consumes MCM and metadata-library
  records first; filename and folder names are fallbacks only.
- 2026-09-04: changed — TV series and episode tables keep TVDB, TMDB, and
  IMDb IDs so identified programmes stay identified.
