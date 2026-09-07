# 017: Merge duplicate TV folders

## Status

In progress

## Outcome

`organiseMyVideo media organise --merge` must safely consolidate multiple TV
folders representing the same series into the most complete existing folder.
`media organise` must also canonicalise numeric season folders as `Season N`,
without leading zeroes.

## Context

A TV series can exist on more than one configured library volume, for example
`H:/TV/Grimm` and `I:/TV/Grimm`. The catalogue then presents two rows although
the folders represent one provider-identified show. Moving new episodes into an
arbitrary volume would cause unnecessary transfers, so the existing folder with
the most complete collection should be retained as the canonical destination.

Existing libraries also contain season-folder variants such as `Season 03`.
The canonical folder form is `Season 3`; this should be repaired safely during
`media organise`, including merge runs.

## Scope

- Add `--merge` to `media organise` while retaining dry-run by default and
  `--confirm` for filesystem changes.
- Detect duplicate TV folders from shared catalogue provider identity, not from
  title text alone.
- Reject a linked group if its non-empty provider IDs contradict one another.
- Select the canonical destination by catalogue episode count, then video-file
  count and video bytes; use a deterministic path tie-break.
- Merge directory trees recursively, including season folders and companion
  artwork/metadata, while never overwriting an existing destination entry.
- Treat the same episode as already present when a provider episode ID matches;
  within an already identified series, season/episode numbers are the fallback.
- Preserve both files and report duplicate/conflict status when the same episode
  or same relative file already exists. Byte-identical files are duplicates;
  differing files are conflicts.
- Treat a source `series.xml` as regenerable when the selected destination
  already has its own `series.xml`: preserve the destination copy and remove the
  source copy through the dry-run-aware filesystem boundary rather than leaving
  it as a merge conflict.
- Remove source directories only after successful moves/removals leave them
  empty.
- Support moves between different filesystems through the existing verified
  `FilesystemOperations.move` boundary.
- Canonicalise numeric season folder names to `Season N`, so `Season 03` becomes
  `Season 3`. If both forms exist, merge their contents using the same
  no-overwrite safety rule and preserve duplicates/conflicts.
- Apply season-folder canonicalisation to ordinary `media organise` runs as well
  as `media organise --merge`, so newly processed libraries converge on the
  unpadded form.
- Refresh the TV catalogue after confirmed season renames or merges that change
  library paths.

## TODO

- Investigate extending duplicate detection and merge handling to movies.
- Reuse the existing clean/reset movie scan as candidate-discovery input where
  practical, while requiring provider identity (for example IMDb/TMDB) before
  any automatic movie merge is allowed.
- Define movie-specific destination ranking and collision handling before moving
  movie-folder merging into this requirement's active scope.

## Out of scope

- Guessing that same-named shows are identical when provider identity is absent.
- Automatically deleting duplicate or conflicting files other than explicitly
  regenerable source metadata such as `series.xml` when a destination copy is
  already present.
- Choosing a destination solely by free disk space.
- Rebalancing complete series between volumes.
- Movie-folder merging in the current implementation; see TODO above.

## Acceptance criteria

1. `media organise --merge` is accepted; without `--confirm` it reports/plans
   changes without altering library files.
2. Two catalogue series rows sharing a provider series ID form a merge group;
   same-name rows with no shared provider ID do not.
3. A group containing contradictory non-empty provider IDs is skipped and
   reported as an identity conflict.
4. The folder with the greatest catalogue episode count wins; video count,
   video bytes, then deterministic path order break ties.
5. Unique files are moved into the canonical tree, including across filesystems,
   without overwriting any existing destination.
6. Matching episode identities with identical bytes are reported as duplicates
   and retained in both locations; differing bytes are conflicts and retained.
7. Same-path metadata/artwork collisions are likewise preserved and classified
   as duplicate or conflict, except that source `series.xml` is discarded when
   the destination already has its own `series.xml`.
8. Empty source directories are removed only after successful confirmed moves
   and regenerable-metadata cleanup; a source containing preserved
   duplicates/conflicts remains.
9. Numeric season folders use unpadded canonical names: `Season 03` becomes
   `Season 3`, while `Season 12` remains `Season 12`.
10. If `Season 03` and `Season 3` both exist, unique contents are merged into
    `Season 3` without overwriting existing entries; duplicates/conflicts are
    preserved and reported.
11. Ordinary `media organise` and merge runs both perform season-folder
    canonicalisation using the standard dry-run/`--confirm` contract.
12. After confirmed season renames or duplicate-show merges, the TV catalogue is
    rebuilt from current configured storage roots.
13. Focused merge/season tests and the existing suite pass.

## Dependencies and decisions

- [REQ-010](010-sqliteMediaCatalogue.md)
- [REQ-016](016-catalogueMediaIdentities.md)
- Existing `FilesystemOperations` verified cross-filesystem move contract.

## Verification

Use temporary TV library roots for canonical selection, recursive merges,
episode identity collision handling, season-folder canonicalisation, dry-run
behaviour, contradictory IDs, regenerable `series.xml` cleanup, and source
cleanup. Run `pytest`, project formatting/lint checks, and `git diff --check`.

## Change history

- 2026-09-06: created — operator requested `media organise --merge` for duplicate
  provider-identified TV folders and selected the most complete folder as the
  canonical destination.
- 2026-09-06: changed — operator selected unpadded canonical season names, e.g.
  `Season 03` -> `Season 3`, for ordinary organise and merge maintenance.
- 2026-09-07: changed — added TODO to investigate provider-verified duplicate
  movie detection/merging, reusing clean/reset movie scanning where practical.
- 2026-09-07: changed — source `series.xml` is now treated as regenerable when
  the destination already has one, allowing obsolete source folders to empty.
