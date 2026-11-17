# 043: Catalogue stale location removal

## Status

Completed

## Outcome

As a media-library operator, I need locations that no longer exist to leave the
catalogue, so that `media locate` shows where my media is now and not where it
used to be.

## Context

[REQ-034](034-catalogueLocationReconciliation.md) marks an absent location
`stale` and keeps it indefinitely. It also leaves rows unchanged when their root
is not part of the scan, so that an unplugged disk does not look like deleted
media.

On 2026-11-08 the catalogue still held 547 rows under `/mnt/movie2` and 991
under `/mnt/movie1`. Both disks had been moved to the RAID and dropped from the
configured storage lists, so no scan could reconcile those rows, and `media
locate` kept reporting them.

## Scope

- A scan removes a movie, series or episode row that was already `stale` when
  the scan began and that the scan did not find again. A location therefore
  stays `stale` for one scan and is removed by the next.
- Removal applies to rows under a root the scan could list, and under a dropped
  root. A row is kept when it is inside a directory the scan could not read.
- A root is dropped when all of these hold:
  - the catalogue has recorded it for that kind (movie or TV);
  - the scan did not cover it;
  - the configuration states that kind's storage list; and
  - at least one root of that kind could be listed in this scan.
- A dropped root that no longer exists is retired. Every row under it becomes
  `stale`, and is removed by the next scan under the rule above. A retired root
  that has no rows left is forgotten.
- A dropped root that still exists keeps its rows that are not `stale`, because
  its media may still be there.
- A root found by `/mnt` discovery is never retired, because a disk missing from
  discovery may only be unmounted. A configured root that is missing is still
  covered by the scan and is not retired.
- `media locate` leaves out `stale` locations. `--all` includes them.

## Out of scope

- Moving, deleting or checking media. This requirement changes catalogue rows
  only.
- Carrying provider IDs across a move made outside organiseMyVideo.
- Keeping a history of removed locations.
- Home-video rows and card inventory.

## Acceptance criteria

1. Given a catalogued folder removed from a listed root, when a scan runs, then
   its row is `stale`; when another scan runs, then its row is gone.
2. Given a `stale` location that has come back, when a scan runs, then its row
   is `current` and is kept.
3. Given a `stale` episode inside a directory the scan could not read, when a
   scan runs, then its row is kept.
4. Given a configured kind and a recorded root that was dropped from the list
   and no longer exists, when a scan runs, then its rows are `stale`; when
   another scan runs, then they are gone and the root is no longer recorded.
5. Given a recorded root that disappears from `/mnt` discovery with no configured
   list, when scans run, then its rows are unchanged.
6. Given a configured root that is unavailable, when scans run, then its rows
   are unchanged.
7. Given a configured kind where no root could be listed, when a scan runs, then
   no root is retired.
8. Given a scan retiring movie roots, when TV roots are recorded and not
   configured, then TV rows are unchanged.
9. Given a `stale` location, when `media locate` runs, then it is not printed;
   when `media locate --all` runs, then it is printed as `stale`.
10. Given a dropped root that still exists, when a scan runs, then its `stale`
    rows are gone and its other rows are unchanged.

## Dependencies and decisions

- [REQ-034](034-catalogueLocationReconciliation.md): this requirement replaces
  its rule that stale rows are kept, and its acceptance criterion 2 for
  `media locate` without `--all`.
- [ADR-008: SQLite media catalogue as the UI record](../../adr/008-sqliteMediaCatalogue.md)

No new architecture decision.

## Verification

- `tests/test_catalogueStaleRemoval.py` covers criteria 1 to 8 and 10, and how
  the configured kinds are derived.
- `tests/test_catalogueLocationReconciliation.py` covers criterion 9.
- A rehearsal on a copy of the real catalogue, scanning the real stores twice.
- Verified on 2026-11-17 against the real catalogue after library scans on
  2026-11-16: no rows remain under `/mnt/movie1` or `/mnt/movie2`, and the
  catalogue holds 1,843 current and 1 stale movie rows, 287 current series and
  14,473 current episodes.

## Traceability

- Implementation: `organiseMyVideo/mediaCatalogue.py`,
  `organiseMyVideo/mediaLocate.py`, `organiseMyVideo/cli.py`,
  `organiseMyVideo/mainLegacy.py`, `organiseMyVideo/video.py`,
  `organiseMyVideo/videoRescan.py`
- Tests: `tests/test_catalogueStaleRemoval.py`,
  `tests/test_catalogueLocationReconciliation.py`
- Documentation: `documentation/mediaCatalogue.md`,
  `documentation/commandLineInterface.md`, `README.md`
- Pull request: none; merged directly to `main`
- Agent runs: None

## Change history

- 2026-11-08: created — `media locate` kept reporting `/mnt/movie2` after the
  disk had moved to the RAID, and the owner asked for stale locations to be
  removed on a subsequent scan.
- 2026-11-17: completed — real-catalogue scans removed every `/mnt/movie1`
  and `/mnt/movie2` row.
