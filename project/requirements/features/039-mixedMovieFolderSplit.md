# 039: Mixed movie folder split

## Status

ToDo

## Outcome

As a media-library operator, I need OMV to separate distinct movies that have
accidentally been stored in the same movie folder so that each movie ends up in
its own canonical folder without scan-time mutation or accidental metadata loss.

## Context

A real library scan produced:

```text
current: Love And Jane (2024)
proposed: An American in Austen (2024)
evidence: movie.xml
imdb: tt31068337
tmdb: 1221678
runtime: 84
```

In this case the folder genuinely contains two different movies. This is not a
simple metadata identity conflict and not a duplicate. The folder must be
classified as containing multiple feature identities and offered as a split
operation under `media organise`.

## Scope

## Collection-aware classification

Multiple distinct titles in one folder do not always mean an accidental mixed
folder. OMV must distinguish three states before proposing a split:

1. **Recognised MCM collection**
   - `collection.xml` exists in the movie folder.
   - Its presence is explicit operator/MCM evidence that the folder is intended
     to represent a collection/container.
   - The file may contain only a display label/year and may have blank provider
     IDs; presence is still structural collection evidence.
   - `collection.xml` must not be treated as normal `movie.xml` identity
     evidence for every contained feature.
   - Scan reports the collection and its detected member identities, but does
     not add it to split investigation merely because multiple identities exist.

2. **Possible movie collection**
   - No `collection.xml` exists.
   - Multiple distinct feature identities are grouped beneath a clear
     collection-like subfolder (for example a folder containing `Collection`,
     `Boxset`, `Box Set`, `Trilogy`, or `Saga`).
   - Scan reports an operator decision requirement rather than automatically
     classifying it as a split.
   - The unresolved item remains under `Needs further investigation`.

3. **Mixed movie folder / split candidate**
   - Multiple distinct feature identities remain after ancillary, multipart and
     recognised collection evidence is excluded.
   - Scan reports the folder as requiring a split.

Absence of `collection.xml` is not proof that the folder is not a collection.

The operator decision for a possible collection belongs to `media organise`,
not `media scan`. A decision such as `collection`, `split`, or `ignore for
now` should be persisted in application state/catalogue so later scans do not
repeatedly ask the same question. OMV should not create or rewrite MCM
`collection.xml` as part of this requirement.

- Detect a movie folder containing two or more distinct feature identities.
- Use feature-file evidence, trusted metadata/provider IDs, runtime and names to
  distinguish genuinely distinct movies from ancillary/sample/multipart media.
- Classify multiple identities during `media scan` as a recognised MCM collection,
  possible movie collection, or mixed movie folder / split candidate.
- Identify which feature file(s) belong to each resolved movie identity.
- Keep `media scan` strictly non-destructive.
- Provide an explicit `media organise` path that can move the misplaced movie
  into its own canonical folder when confirmed.

## Split behaviour

The split unit is a resolved movie identity, not an arbitrary file.

For a confirmed split:

1. choose the movie identity that is not already correctly represented by the
   current folder;
2. create/choose that movie's canonical destination folder in an eligible movie
   store;
3. move the feature file(s) belonging to that identity through
   `FilesystemOperations`;
4. move only sidecars/artwork/subtitles that can be confidently associated with
   the moved movie;
5. leave ambiguous shared folder-level metadata in place and report it for
   review rather than guessing;
6. verify the destination and remaining source contents;
7. reconcile catalogue locations after the move.

Do not automatically rewrite or reassign ambiguous `movie.xml` data merely
because a split is performed.

## CLI

Detection remains part of:

```bash
organiseMyVideo media scan
```

The corrective operation belongs under:

```bash
organiseMyVideo media organise
```

The implementation may expose the split as part of the normal organise plan or
with a dedicated organise option, but it must remain dry-run by default and
require `--confirm` for filesystem mutation.

## Safety

- Never split during scan.
- Never overwrite an existing destination folder/file.
- Never treat multipart media such as `-part2` as a second movie identity.
- Never treat samples, trailers or obvious ancillary files as a second movie.
- If identity/file association is ambiguous, report for investigation and do
  not move anything.
- All mutation must pass through the central filesystem safety boundary.

## Reporting

A scan finding should identify at least:

```text
- mixed movie folder
  folder: /path/to/current/folder
  movie 1: Love And Jane (2024)
  file: /path/to/.../Love And Jane (2024).mkv
  movie 2: An American in Austen (2024)
  file: /path/to/.../An American in Austen (2024).mkv
  action: split required
```

The item must also appear under `Needs further investigation` until an organise
plan safely resolves it.

## Additional real-library classification case

A folder may contain one main feature, obvious ancillary material, and a separately titled programme:

```text
Michael McIntyre - Showtime (2012).mkv
Michael Mcintyre - Behind The Scenes (2012) ...mkv
Michael Mcintyre - Christmas Roadshow (2012) ...mkv
```

`Behind The Scenes` is ancillary and must not create a split candidate.
`Christmas Roadshow` has a distinct programme-style title and should be surfaced
as a possible secondary identity requiring split investigation rather than being
treated as a duplicate or renamed onto the main feature.

Filename size may support reporting but must not be the rule that decides whether
content is ancillary or a separate programme.

## Acceptance criteria

1. Two distinct feature movies in one folder are classified as a mixed-identity split candidate, not merely a rename conflict.
2. Scan reports both resolved identities and the feature-file paths supporting them.
3. Scan does not move, rename or delete either movie.
4. Samples, trailers, junk files and multipart media do not trigger a false split.
5. A confirmed organise operation can move one resolved movie into its canonical folder.
6. The move includes only files confidently associated with the moved identity.
7. Ambiguous shared metadata/artwork is not guessed or silently reassigned.
8. Existing destination collisions block the split rather than overwrite.
9. Catalogue location state is reconciled after a successful split.
10. Tests include the real-library `Love And Jane (2024)` / `An American in Austen (2024)` case.
11. Tests cover the Michael McIntyre case and prove behind-the-scenes content is ignored while the separately titled programme remains visible for split investigation.
12. Given `collection.xml`, multiple distinct movie identities are reported as a recognised MCM collection rather than a split candidate.
13. Given a collection-like nested folder without `collection.xml`, scan reports a possible movie collection and an operator decision requirement.
14. Absence of `collection.xml` alone never proves that multiple titles are an accidental mixed folder.
15. A future organise-time operator decision can be persisted so subsequent scans reuse it rather than prompting repeatedly.

## Dependencies

- [REQ-029](029-nonDestructiveMediaScan.md)
- [REQ-030](030-operationalRunAudit.md)
- [REQ-035](035-movieIdentityConflictDetection.md)
- [REQ-007](007-filesystemSafety.md)

## Change history

- 2026-10-04: created from real-library scan where two distinct movies were stored in one folder.

- 2026-10-04: added collection-aware classification from the real Halo MCM collection case, including `collection.xml`, possible collection inference and persisted operator decision requirements.
