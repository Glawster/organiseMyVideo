# 034: Catalogue location reconciliation

## Status

Completed

## Outcome

As a media-library operator, I need an authoritative scan of the configured
roots to reconcile physical movie and TV locations with the catalogue, so that
a folder which is gone is not treated as a current location and a disk that
was not scanned is not treated as empty.

## Context

`movieItem`, `tvSeries`, and `tvEpisode` used to be replaced wholesale. A
second scan deleted every row and inserted only the folders it had just
listed. A root that was unmounted, missing, or unlistable was skipped before
that replacement, so its catalogue rows disappeared together with folders that
had really been removed.

`media locate` printed every matching `tvSeries.folderPath` and did not check
that the folder still existed. `media organise --merge` discovered duplicates
from the live filesystem, then updated the persistent catalogue only after a
confirmed run that merged at least one group. A dry-run, or a confirmed run
that found one physical copy of a show, left the older path in the catalogue.
Locate then reported both.

The Lanterns library is the acceptance case: the catalogue recorded
`/mnt/video1/TV/Lanterns` and `/mnt/video2/TV/Lanterns`, while only the video2
folder remained. After reconciliation only the live folder is current.

REQ-010 acceptance criterion 3 required removed folders to disappear from the
tables. This requirement supersedes that deletion rule. The criterion text is
unchanged; the narrowing is recorded in REQ-010's change history.

## Scope

- Store `locationState` on `movieItem`, `tvSeries`, and `tvEpisode` as
  `current`, `stale`, or `unverified`. Opening an older catalogue adds the
  column with default `unverified`.
- Record each reconciled root in `catalogueScanRoot` with outcome
  `authoritative`, `unavailable`, or `error`.
- Treat a root as authoritative only when this scan was meant to cover that
  whole root, the root is a directory, and listing its children succeeds. An
  empty successful listing is authoritative for the folders directly inside
  the root.
- Upsert folders and files found under an authoritative root as `current`.
  Mark a previously stored show or movie folder that the root listing no
  longer contains as `stale`. Keep the row and its provider IDs. Do not
  delete it.
- When reading a directory inside a TV show fails, leave existing episode
  rows under that directory unchanged. A successful listing of another
  directory in the same show, or of the root's own children, still reconciles
  those paths.
- Leave paths unchanged when their root was not passed to the scan, is not a
  directory, or raises an error while listing. Record `unavailable` or
  `error` for a root that was passed but could not be listed.
- `library rescan`, legacy `--rescan`, and `media scan --all` reconcile every
  root they successfully list. `media scan` without `--all`, and any scan
  limited with `--show`, do not reconcile other locations. `--refresh`
  rebuilds `metadataLibrary.json` only.
- Default movie, series, and episode lists return `current` and `unverified`
  rows. Stale rows remain queryable when requested.
- `media locate` accepts optional `--show`. With a name it lists matching
  shows and exits 1 when none match. Without a name it lists every catalogued
  show and exits 0 when the catalogue is empty. Locate does not write the
  database. It prints `current` only when the stored state is current and the
  folder is present, `stale` when the stored state is stale and the folder is
  absent, and `unverified` otherwise.
- When organiseMyVideo itself confirms a show-folder, movie-folder, season, or
  merge move, retarget the catalogue row: the destination becomes current and
  receives provider IDs the destination does not already have; the old path
  stays as stale. Dry-run does not retarget. A missing catalogue file is left
  uncreated.
- After `media organise --merge`, reconcile location state from the storage
  roots that scan discovered, including a dry-run and a run that merges
  nothing. Dry-run still does not move media.
- Movies use the same location states as TV shows. There is no separate movie
  locate command.

## Out of scope

- Physically deleting or purging long-stale rows.
- `media organise --merge --show`. Optional show scoping for merge remains the
  REQ-017 obligation and is not restated here.
- Carrying provider IDs across a rename performed outside organiseMyVideo.
- Home-video scanning, TVDB removal, or rewriting embedded media metadata.
- Pretending that `--refresh` reconciles the SQLite catalogue.

## Acceptance criteria

1. Given Lanterns catalogued under two TV roots, when one physical folder is
   removed and both roots are scanned authoritatively, then the remaining
   folder is `current`, the removed folder is `stale` and still stored, and
   the default series list contains only the live folder.
2. Given that reconciled catalogue, when `media locate --show Lanterns` runs,
   then it prints the live folder as `current` and the removed folder as
   `stale`.
3. Given a catalogue row still marked `current` whose folder is already
   missing, when locate runs before an authoritative scan of that root, then
   the path is printed as `unverified`.
4. Given one live Lanterns folder and a stale catalogue row for a folder that
   is not a directory, when duplicate-show discovery runs, then that missing
   path does not form a duplicate group.
5. Given catalogue rows under a root that is then unmounted, renamed away, or
   unlistable, when a scan is asked to cover that root or omits it entirely,
   then those rows are not deleted and are not marked `stale`.
6. Given an empty root list passed to catalogue replacement, when it returns,
   then previously stored movie and TV rows remain.
7. Given the same two-root removal for a movie folder, when both movie roots
   are scanned authoritatively, then the live movie is `current`, the removed
   movie is `stale`, and the default movie list contains only the live movie.
8. Given a confirmed rename of `The Lanterns` to `Lanterns, The`, when the
   catalogue is read, then the new folder and its episode are `current` with
   the previous provider IDs, and the old paths are `stale` with those IDs.
9. Given a confirmed merge that moves an episode file, when the catalogue is
   read, then the destination file is `current` with the source episode ID and
   the old file path is `stale`.
10. Given `media locate` with no `--show` and an empty catalogue, when it runs,
    then it prints nothing and exits 0.
11. Given two or more catalogued shows, when `media locate` runs without
    `--show`, then it prints every show and each stored folder.
12. Given a catalogued episode inside a TV directory that cannot be listed,
    when that show's root is scanned, then the episode keeps its previous
    location state. A show folder absent from the same root listing is still
    marked `stale`, and an episode in a directory that was listed is still
    reconciled.

## Dependencies and decisions

- [ADR-008: SQLite media catalogue as the UI record](../../adr/008-sqliteMediaCatalogue.md)
- [REQ-010: SQLite media catalogue](010-sqliteMediaCatalogue.md) — narrowed by
  this requirement for unseen movie and TV rows.
- [REQ-017: Merge duplicate TV and movie folders](017-mergeDuplicateTvFolders.md)
  — merge now reconciles location state even when it moves nothing.
- [REQ-019: Catalogue metadata resolution](019-catalogueMetadataResolution.md)
  — provider IDs move with a path only when organiseMyVideo moves it.

No new architecture decision. Marking a location stale, rather than deleting
it, is the behaviour required here.

## Verification

- `tests/test_catalogueLocationReconciliation.py` covers the Lanterns cases,
  including an unavailable root, an empty discovery, a movie folder, a
  confirmed show rename, a confirmed episode move, locate with and without
  `--show`, a catalogue that contains more than one show, an unread show
  subtree, and a merge that merges nothing.
- `tests/test_mediaCatalogue.py` expects a removed movie folder to remain
  queryable as stale.
- Verified on 2026-09-30 in the `mediaStudio` environment: `pytest` 770 passed
  after the show-subtree tightening, `runLinter` reported no findings,
  `runLinter --markup` reported no remaining issues, and `git diff --check`
  produced no output. Black was applied to the changed Python files.

## Traceability

- Implementation: `organiseMyVideo/mediaCatalogue.py`,
  `organiseMyVideo/mediaLocate.py`, `organiseMyVideo/mainLegacy.py`,
  `organiseMyVideo/cli.py`, `organiseMyVideo/showFolders.py`,
  `organiseMyVideo/seasonFolders.py`, `organiseMyVideo/mediaMerge.py`
- Tests: `tests/test_catalogueLocationReconciliation.py`,
  `tests/test_mediaCatalogue.py`
- Documentation: `documentation/mediaCatalogue.md`,
  `documentation/commandLineInterface.md`, `README.md`
- Pull request: pending
- Agent runs: None

## Change history

- 2026-09-30: created — locate reported a Lanterns folder that no longer
  existed after merge had seen only one physical copy.
- 2026-09-30: completed — authoritative scans mark absent locations stale,
  unscanned roots are left unchanged, and the full test suite passed.
- 2026-09-30: tightened — an error while reading a directory inside a TV show
  does not mark the episodes under that directory stale. `media locate`
  without `--show` is covered for a catalogue that contains shows.
