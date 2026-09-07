# 017: Catalogue metadata resolution

## Status

Completed

## Outcome

A catalogue rescan faithfully records the best already-known movie, series and
episode identity without fresh provider identification or loss of durable IDs.

## Context

The catalogue consumes organiser metadata evidence; it must not become another
identification engine. Replacing SQLite rows previously discarded catalogue-only
provider identities.

## Scope

- Resolve MCM evidence, persisted known identity, metadataLibrary, canonical
  filename, then folder/path hints using the existing organiser readers.
- Current MCM and metadata-library IDs win over SQLite fallback IDs. Persistence
  fallback applies only to provider identity, never stale descriptive metadata.
- Reconcile movies and series by folderPath and episodes by filePath before
  replacing rows. Preserve missing provider IDs; never derive them from SQLite keys.
- Keep all public catalogue APIs compatible and movie/TV replacement independent.
- Keep catalogueReplaceFromStorage offline, with no provider calls, prompts,
  token refreshes, downloads, scraping or media filesystem mutations.

## Out of scope

Provider search/ranking and new APIs; canonical filename generation; episode
ordering configuration; home-video scanning; removable-volume inventory;
camera import/migration; media moves, renames or deletions; UI changes.

## Acceptance criteria

1. Movie MCM title/year/IDs override filename and folder inference.
2. Movies use metadata-library identity when MCM is absent.
3. Movies fall back safely to canonical filename then folder hints.
4. Series MCM identity wins, including known tvdbId, tmdbId and imdbId.
5. Episode MCM evidence wins, including tvdbEpisodeId, tmdbEpisodeId and imdbId;
   series IMDb IDs must not be mistaken for episode IDs.
6. Known TV metadata-library provider IDs populate the correct records.
7. Catalogue-only provider IDs survive rescans lacking current identity evidence.
8. Current MCM/library IDs replace older stored IDs when supplied.
9. Current source evidence refreshes title/show/season/episode descriptions.
10. A normal rescan performs no network/provider calls or interactive prompts.
11. Existing catalogue migration and REQ-016 regression tests pass.
12. Movies and TV can be rescanned independently without disturbing each other.

## Dependencies and decisions

- [REQ-016](016-catalogueMediaIdentities.md).
- [ADR-008](../../adr/008-sqliteMediaCatalogue.md).
- Reuse local readers; the catalogue does not invoke organiser enrichment.
- Identity conflict resolution across renamed paths, provider provenance and
  ambiguous canonical identification are deferred to
  feature/canonical-media-identification.

## Verification

| Production behaviour | Unit | Integration | Golden | UI | Resolution | Clean-room |
| --- | --- | --- | --- | --- | --- | --- |
| MCM/library/name resolution | Existing reader tests | Temporary XML/JSON to SQLite | Explicit expected identities | N/A | N/A | Fresh database |
| Identity reconciliation | Replacement fallback | Repeated selected scans | Explicit IDs and descriptions | N/A | N/A | Fresh source tree |
| Offline boundary | Provider guards | Real rescan with socket/input guards | N/A | N/A | N/A | Fresh database |

Run pytest, black --check ., ./tests/runLinter.py,
./tests/runLinter.py --markup and git diff --check. Do not fix unrelated
pre-existing lint findings.

## Change history

- 2026-09-05: created from the catalogue metadata resolution implementation request.
