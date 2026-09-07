# 017: Merge duplicate TV and movie folders

## Status

Completed

## Outcome

`organiseMyVideo media organise --merge` safely consolidates multiple TV
or movie folders that represent the same provider-identified title into
the most complete existing folder. `media organise` also canonicalises
numeric season folders as `Season N`, without leading zeroes.

## Context

A TV series or movie can exist on more than one configured library volume,
for example `H:/TV/Grimm` and `I:/TV/Grimm`, or two `Inception (2010)`
folders. The catalogue then presents two rows although the folders are
one identified title. Moving new files into an arbitrary volume would
cause unnecessary transfers, so the existing folder with the most complete
collection is retained as the canonical destination.

Existing TV libraries also contain season-folder variants such as
`Season 03`. The canonical form is `Season 3`.

## Scope

- Add `--merge` to `media organise` while retaining dry-run by default and
  `--confirm` for filesystem changes.
- Detect duplicate TV folders from shared catalogue provider identity, not
  from title text alone.
- Detect duplicate movie folders from shared IMDb or TMDB identity, not from
  `Title (Year)` text alone. Live movie discovery reuses the catalogue's
  movie-folder scan (`_moviesCollect` / MCM `movie.xml`).
- Reject a linked group if its non-empty provider IDs contradict one another.
- Select the TV destination by catalogue episode count, then video-file
  count and video bytes; movie destination by presence of `movie.xml`, then
  video count and bytes. Lexicographically earlier paths break ties.
- Merge directory trees recursively, including season folders, extras, and
  companion artwork/metadata, while never overwriting an existing
  destination entry.
- Treat the same TV episode as already present when a provider episode ID
  matches; within an identified series, season/episode numbers are the
  fallback.
- Treat a movie's root video as the feature: if the destination folder
  already has a root video, an incoming root video is a duplicate or
  conflict even when the filenames differ. Videos in subfolders (for
  example `Featurettes`) still merge by relative path.
- Preserve both files and report duplicate/conflict status when the same
  identity or same relative file already exists. Byte-identical files are
  duplicates; differing files are conflicts.
- Treat source `series.xml` / `movie.xml` as regenerable when the selected
  destination already has its own copy: keep the destination file and
  remove the source copy through the dry-run-aware filesystem boundary.
- Remove source directories only after successful moves/removals leave them
  empty.
- Support moves between different filesystems through
  `FilesystemOperations.move`.
- Canonicalise numeric season folder names to `Season N` on ordinary
  `media organise` and merge runs.
- Refresh movie and TV catalogue rows after confirmed merges or season
  renames that change library paths.

## Out of scope

- Guessing that same-named titles are identical when provider identity is
  absent.
- Automatically deleting duplicate or conflicting files other than
  regenerable source `series.xml` / `movie.xml` when a destination copy is
  already present.
- Choosing a destination solely by free disk space.
- Rebalancing complete libraries between volumes.

## Acceptance criteria

1. Given `media organise --merge` without `--confirm`, when it runs, then it
   reports planned TV and movie merges without altering library files.
2. Given two catalogue series rows sharing a provider series ID, when merge
   runs, then they form a group; same-name rows with no shared provider ID
   do not.
3. Given two movie folders sharing an IMDb or TMDB ID, when merge runs,
   then they form a group; same `Title (Year)` folders with no shared
   provider ID do not.
4. Given a group containing contradictory non-empty provider IDs, when
   merge plans, then it is skipped and reported as an identity conflict.
5. Given duplicate TV folders, when a destination is chosen, then the
   folder with the greatest catalogue episode count wins; video count,
   video bytes, then earlier path break ties.
6. Given duplicate movie folders, when a destination is chosen, then a
   folder with `movie.xml` wins over one without; video count, video
   bytes, then earlier path break remaining ties.
7. Given unique files in a source tree, when merge is confirmed, then they
   are moved into the canonical tree, including across filesystems, without
   overwriting any existing destination.
8. Given matching TV episode identities with identical bytes, when merge
   runs, then both files are retained as duplicates; differing bytes are
   conflicts and retained.
9. Given two root videos for the same identified movie, when merge runs,
   then identical bytes are duplicates and differing bytes are conflicts;
   extras in subfolders still merge by relative path.
10. Given same-path metadata/artwork collisions, when merge runs, then they
    are preserved as duplicate or conflict, except that source `series.xml`
    or `movie.xml` is discarded when the destination already has its own.
11. Given empty source directories after confirmed moves and regenerable
    metadata cleanup, when merge completes, then those directories are
    removed; a source containing preserved duplicates/conflicts remains.
12. Given numeric season folders, when organise or merge runs, then
    `Season 03` becomes `Season 3` and `Season 12` remains `Season 12`.
13. Given both `Season 03` and `Season 3`, when normalisation runs, then
    unique contents merge into `Season 3` without overwriting; duplicates
    and conflicts are preserved.
14. Given confirmed season renames or duplicate-title merges, when they
    change library paths, then the movie and TV catalogue tables are
    rebuilt from current configured storage roots.
15. Given focused merge/season tests and the existing suite, when they run,
    then they pass.

## Dependencies and decisions

- [REQ-010](010-sqliteMediaCatalogue.md)
- [REQ-016](016-catalogueMediaIdentities.md)
- Existing `FilesystemOperations` verified cross-filesystem move contract.

## Verification

Use temporary TV and movie library roots for canonical selection, recursive
merges, identity collision handling, season-folder canonicalisation,
dry-run behaviour, contradictory IDs, regenerable metadata cleanup, and
source cleanup. Run `pytest` and `git diff --check`.

## Traceability

- Implementation: `organiseMyVideo/mediaMerge.py`,
  `organiseMyVideo/movieLibraryScan.py`, `organiseMyVideo/tvLibraryScan.py`,
  `organiseMyVideo/seasonFolders.py`, `organiseMyVideo/__main__.py`
- Tests: `tests/test_mediaMerge.py`, `tests/test_movieLibraryScan.py`,
  `tests/test_tvLibraryScan.py`, `tests/test_seasonFolders.py`
- Documentation: [Command-line interface](../../../documentation/commandLineInterface.md)

## Change history

- 2026-09-06: created — operator requested `media organise --merge` for
  duplicate provider-identified TV folders.
- 2026-09-06: changed — unpadded canonical season names for organise and
  merge.
- 2026-09-07: changed — source `series.xml` is regenerable when the
  destination already has one.
- 2026-09-07: completed — movie-folder merging added with IMDb/TMDB
  identity, feature-video collision handling, and regenerable `movie.xml`.
