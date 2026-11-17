# 044: Replace an existing movie file

## Status

ToDo

## Outcome

As a media-library operator, I need `media organise` to replace a movie's
existing feature file with a newly downloaded copy when I ask it to, so that a
better or complete copy can be filed without manual moves and without risk of
losing either file.

## Context

On 2026-11-17 a confirmed `media organise` run found a 24.3 GB 4K copy of
`28 Days Later (2002)` in staging. The library already held a 3.6 GB copy at
`/mnt/raid/Movies/28 Days Later (2002)/28 Days Later (2002).mkv`. The run
correctly reported a possible duplicate feature file and left both files in
place, as [REQ-035](035-movieIdentityConflictDetection.md) requires, but there
was no way to say that the new copy should win.

The same run filed a full redownload of `Insidious The Last Key (2018)` into a
new folder, `/mnt/raid/Movies/Insidious The Last Key (2018)`, instead of
colliding with the 36-minute copy in
`/mnt/movies/Movies/Insidious - The Last Key (2018)`. `findExistingMovieDir`
matches a folder only when its name is equal apart from case, so a title that
differs only by punctuation creates a duplicate folder. Several short copies
found on 2026-11-16 are being redownloaded, so this will recur.

Both cases were fixed by hand on 2026-11-17.

## Scope

### Existing folder matching

- When filing a movie, find an existing folder by title identity and year, as
  [REQ-035](035-movieIdentityConflictDetection.md) compares identity: ignore
  case, punctuation, spacing, filesystem-safe substitutions and supported
  article placement.
- Search every configured movie store, not only the store chosen for new
  folders.
- When more than one folder matches, file nothing for that movie and report the
  folders for review.

### Replacement

- Add `media organise --replace`. Without it, a collision behaves as it does
  now.
- Replace only when the existing folder matched by title and year, there is no
  identity conflict, and the collision is classified as a possible duplicate
  feature file. Never replace ancillary media, an unresolved collision or a file
  in an identity conflict.
- Default to a dry run that lists each planned replacement with both files'
  paths, sizes, durations and resolutions. Change files only with `--confirm`.
- Probe the new file before replacing. Refuse the replacement when the new file
  cannot be probed, or when it is materially shorter than the existing file,
  using the same thresholds as the REQ-035 short-feature check.
- Perform the replacement through the filesystem safety boundary in
  [filesystemSafety.md](../../../documentation/filesystemSafety.md): copy the new
  file, verify it by checksum, publish it at the canonical name, and move the
  old file into quarantine rather than deleting it. Record the source,
  destination, quarantined path and checksums in the journal so that the
  replacement can be reversed.
- Keep the existing `movie.xml`, artwork and subtitles. Report subtitles that
  belonged to the old file, because they may not match the new release.
- Update the catalogue entry for the movie to the new file.
- Report each replacement, refusal and failure in the run summary. Exit non-zero
  if any confirmed replacement failed.

## Out of scope

- Choosing between copies automatically by size, resolution or codec.
  Replacement happens only when `--replace` is given.
- Emptying the quarantine.
- Replacing TV episodes, pending the decision below.
- Replacing files during a library scan or `library organise`.
- Renaming or merging the duplicate folders that already exist.

## Acceptance criteria

1. Given a staged `Insidious The Last Key (2018)` and an existing folder
   `Insidious - The Last Key (2018)` in any configured movie store, when the
   movie is filed, then the existing folder is used and no new folder is
   created.
2. Given a staged movie whose title and year match two existing folders, when it
   is filed, then nothing is moved and both folders are reported for review.
3. Given a possible duplicate feature file and no `--replace`, when
   `media organise --confirm` runs, then neither file changes and the collision
   is reported as now.
4. Given a possible duplicate feature file, when `media organise --replace` runs
   without `--confirm`, then the planned replacement is listed with both files'
   paths, sizes, durations and resolutions, and no file changes.
5. Given the `28 Days Later (2002)` case, when `media organise --replace
   --confirm` runs, then the 4K file is at the canonical path, the old file is in
   quarantine, the journal records both paths and checksums, and `movie.xml` and
   artwork are unchanged.
6. Given a new file that cannot be probed, or that is materially shorter than the
   existing file, when `--replace --confirm` runs, then the replacement is
   refused, both files stay where they were, and the refusal is reported.
7. Given an identity conflict, ancillary media or an unresolved collision, when
   `--replace --confirm` runs, then nothing is replaced.
8. Given a copy or checksum failure during a replacement, when it is reported,
   then the existing file is still at the canonical path, no temporary file
   remains, and the command exits non-zero.
9. Given a completed replacement, when the journal is read, then it is enough to
   restore the old file to the canonical path.
10. Given subtitles named after the replaced file, when it is replaced, then the
    subtitles are kept and reported as possibly out of sync.

## Dependencies and decisions

- [REQ-035](035-movieIdentityConflictDetection.md): identity comparison,
  collision classification and the short-feature thresholds.
- [REQ-007](007-filesystemSafety.md) and
  [ADR-003](../../adr/003-filesystemSafetyBoundary.md): copy, verify, quarantine
  and journal.
- [REQ-036](036-incomingMediaPreparation.md): `media organise` files staged
  media.
- [REQ-043](043-catalogueStaleLocationRemoval.md): catalogue location state.
- Pending decision: whether `--replace` also covers TV episodes, for example a
  better-quality copy of an episode already in the library.
- Pending decision: whether an interactive run without `--auto` should ask
  "replace existing? [y/N]" for each collision instead of requiring the flag.

## Verification

- Unit tests for title-identity folder matching, including punctuation, article
  placement and more than one match.
- Tests with temporary trees and a stubbed probe for each replacement rule,
  refusal and failure.
- A public CLI test comparing a `--replace` dry run with a confirmed run.
- A manual dry run against a real staging folder, following
  [testingProcess.md](../../../documentation/testingProcess.md).

## Traceability

- Implementation: pending
- Tests: pending
- Documentation: pending
- Pull request: pending
- Agent runs: None

## Change history

- 2026-11-17: created — a confirmed `media organise` run could not replace an
  existing `28 Days Later (2002)` file with a 4K copy, and filed a redownloaded
  `Insidious The Last Key (2018)` into a duplicate folder.
