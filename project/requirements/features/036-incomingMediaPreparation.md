# 036: Incoming media preparation workflow

## Status

ToDo

## Outcome

As a media-library operator, I need incoming/staging media to be cleaned before
classification and scan analysis so that release-site prefixes, empty folders
and sample-only folders do not reduce detection quality, while existing movie
and TV libraries remain outside the scope of `media clean`.

## Context

Real-world MCM download parsing showed that release/site noise such as
`www.UIndex.org - ...` can prevent folder detection even when the contained
feature file is recognisable. OMV already has staged-media cleaning behaviour,
but `media clean` currently also normalises TV show/season folders and refreshes
catalogue state. Those library responsibilities now belong elsewhere in the
workflow.

REQ-029 establishes that `media scan` is non-destructive. Therefore a scan must
not silently perform confirmed cleanup. The operational sequence is:

```text
media clean [SOURCE]        # inspect staged cleanup
media clean [SOURCE] --confirm
media scan                  # non-destructive analysis
media organise              # arrange/rename/move/merge when approved
```

A future orchestration path may reuse the same clean-analysis service before a
scan, but scan itself must not mutate the incoming or library filesystem.

## Scope

### `media clean`

`media clean` operates only inside the configured or explicitly supplied
incoming/staging source tree.

It may:

- normalise top-level staged release/site prefixes and other established
  incoming-name noise;
- inspect nested staged folders when deciding whether they are empty;
- treat sample-only staged folders as empty/cleanable;
- quarantine/remove confirmed-empty or sample-only staged folders when
  `--confirm` is supplied;
- report the planned cleanup in dry-run mode.

It must not:

- walk configured movie or TV library roots for repair work;
- normalise TV show folders;
- normalise season folders;
- rename established movie/TV library media;
- merge library folders;
- perform catalogue-wide location reconciliation merely because clean was run.

The source-tree boundary is authoritative: no clean mutation may escape the
selected incoming source tree.

### `media scan`

`media scan` remains non-destructive under REQ-029.

Before classifying incoming media, scan may reuse the same incoming-name
normalisation logic as an in-memory/read-only view so that classification sees a
cleaned candidate title. It must not rename staged files/folders as part of the
scan.

### Classification input order

For ambiguous incoming items, OMV should prefer evidence in this order where
available:

1. durable provider IDs / trusted existing metadata;
2. feature filename;
3. enclosing cleaned folder name;
4. broader heuristics/fuzzy matching.

Fuzzy matching may produce a review suggestion but must not silently authorize a
movie/TV identity change.

## Acceptance criteria

1. Given `media clean` with no explicit source, only the configured/default
   incoming source tree is inspected.
2. Given `media clean -s PATH`, no path outside `PATH` is modified.
3. `media clean` no longer runs TV show/season-folder normalisation.
4. `media clean` no longer performs library-wide catalogue reconciliation as a
   side effect of staged cleanup.
5. Existing staged name cleanup still removes known release/site noise.
6. Existing empty-folder and sample-only-folder cleanup remains available,
   dry-run by default and mutating only with `--confirm`.
7. `media scan` remains non-destructive and cannot perform confirmed clean
   mutations.
8. Scan/classification may reuse the same cleaner as a pure normalisation
   function so names such as `www.UIndex.org - Avatar ...` are analysed without
   the prefix.
9. Feature filenames take precedence over an undecidable enclosing release
   folder when classifying staged media.
10. Documentation describes the normal operational sequence as clean -> scan ->
    organise.
11. Tests prove clean cannot reach library roots outside the selected incoming
    source.
12. Tests prove scan cannot mutate media while reusing incoming-name
    normalisation.

## Dependencies

- [REQ-006](006-cliArchitecture.md)
- [REQ-007](007-filesystemSafety.md)
- [REQ-019](019-catalogueMetadataResolution.md)
- [REQ-020](020-combinedMediaScan.md)
- [REQ-029](029-nonDestructiveMediaScan.md)
- [REQ-035](035-movieIdentityConflictDetection.md)

## Implementation notes

Refactor the current staged-name cleaner so the parsing/normalisation step can be
used without filesystem mutation. Keep mutation through the existing filesystem
safety boundary.

Remove the current `_normaliseSeasonFolders(...)` call from the `media clean`
execution path. Season/show canonicalisation belongs to organise/library
maintenance workflows.

## Change history

- 2026-10-02: created from real-world MCM download-parser observations and
  workflow review.
