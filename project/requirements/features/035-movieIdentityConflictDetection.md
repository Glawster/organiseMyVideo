# 035: Movie identity conflict detection

## Status

Completed

## Outcome

As a media-library operator, I need movie scans to distinguish safe naming
normalisation from a possible identity change so that incorrect metadata cannot
silently cause a movie to be renamed to another title or release year.

## Context

Real-library testing after REQ-034 exposed rename proposals where existing MCM
metadata disagreed with otherwise plausible movie folders and files.

The strongest example was:

```text
13 minutes (2021)
→ One Second Forever (2021)
```

The existing `movie.xml` identifies a different title while the stored media
duration and existing folder name provide conflicting evidence.

The same scan also proposed several release-year changes, for example:

```text
Call of the Wild, The (1972) → Call of the Wild, The (1975)
Carry On Matron (1972)       → Carry On Matron (2007)
Boss Level (2021)            → Boss Level (2020)
Chernobyl - Abyss (2021)     → Chernobyl - Abyss (2022)
```

A title change and a year change are both identity red flags. They must not be
treated as routine filename normalisation.

Movie title casing is also a library convention. Existing title-style
capitalisation must not be degraded merely because a metadata source uses
different casing. For example:

```text
Anyone But You
→ Anyone but You
```

must not be proposed.

A later real-library case exposed another form of unsafe MCM evidence. The
stored movie was a roughly 91-minute feature, while `movie.xml` contained:

```text
LocalTitle:     Q:\Movies\Entangled (2019)
OriginalTitle:  Q:\Movies\Entangled (2019)
ProductionYear: 2019
TMDbId:         641556
RunningTime:    3
```

The path-like title and three-minute metadata runtime materially contradict the
stored feature. This must be treated as suspect identity metadata requiring
review, not as authoritative evidence from which OMV constructs a canonical
rename.

A further production scan found two same-identity folders:

```text
Sonic the Hedgehog 3 (2024)
Sonic the Hedgehog 3 (2024)_
```

Each contained a 20,526,191,454-byte feature file with the same name and timestamp,
but the files had different inode numbers on the same filesystem. OMV therefore
could not conclude that they were the same physical file and legitimately began a
full content comparison. The scan appeared stalled because the comparison read a
20 GB file in 1 MiB chunks without any visible secondary progress.

## Scope

- Classify a proposed movie rename as either:
  - safe naming normalisation; or
  - an identity conflict requiring review.
- Flag a proposed change to the resolved movie title as an identity red flag
  when it is more than punctuation, filesystem-safe character substitution,
  spacing, or an explicitly supported article-placement convention.
- Flag any proposed change to the release year as an identity red flag.
- Do not automatically rename or propose a normal rename when an identity red
  flag is present.
- Report the conflicting evidence clearly enough for the user to understand
  which source supplied the existing and proposed identity.
- Include available evidence such as folder title/year, filename title/year,
  MCM metadata, provider IDs and runtime/duration where useful.
- Treat obviously path-like movie titles from metadata as suspect identity
  evidence rather than canonical movie titles. This includes Windows drive/path
  forms such as `Q:\Movies\Entangled (2019)` and equivalent path-bearing values.
- When metadata runtime/duration materially contradicts the actual feature
  runtime, downgrade that metadata from authoritative identity evidence and
  report the contradiction for investigation rather than silently renaming from
  it.
- A suspect MCM record must remain blocked even when it also contains provider
  IDs. Provider IDs do not override contradictory local evidence automatically.
- Preserve title-style capitalisation when the existing and resolved title
  differ only by case.
- When metadata is obviously ALL CAPS, prefer readable title-style capitalisation
  for canonical output rather than preserving shout-case.
- When an unsupported separator such as `|` separates meaningful title parts,
  preserve readability with ` - ` rather than collapsing the words together;
  e.g. `TAYLOR SWIFT | THE ERAS TOUR` should canonicalise to
  `Taylor Swift - The Eras Tour`.
- Produce a filesystem-safe canonical movie folder and filename before rename
  planning. Unsupported filename characters from metadata should be ignored/
  removed rather than passed through to `rename()`.
- Apply the same filesystem-safe naming rule to both movie folders and movie
  files while preserving an unambiguous movie identity.
- Valid punctuation and its existing spacing must be preserved. In particular,
  sanitisation must not collapse spaces around `&`, apostrophes, or opening
  parentheses merely because other unsupported characters are being removed.
- Ignore known non-feature media such as `Sample.mkv` during canonical feature
  filename reconciliation; these files must not be renamed to the feature's
  canonical movie filename.
- When a canonical file or folder target already exists, classify the condition
  rather than reporting only a generic rename error. Distinguish at least:
  - ignored ancillary media such as samples;
  - obvious junk/release-marker files that are not feature media;
  - multi-part feature media (for example `-part2`);
  - same-identity folder collision / merge candidate;
  - possible duplicate feature file;
  - mixed-identity movie folder / split candidate; and
  - unresolved collision requiring review.
- When one physical movie folder contains two distinct feature movies that resolve
  to different identities, classify it as a mixed-identity folder / split candidate
  rather than reducing the condition to a metadata rename conflict. Report the
  identities and the feature files that support each identity. Do not move either
  movie during scan.
- A same-identity folder collision must not overwrite or delete either side.
  Treat it as a reconciliation candidate and establish whether content is
  identical, complementary, or distinct before any later merge operation.
- Before a potentially expensive full-file duplicate comparison, use cheap and
  conclusive checks first:
  - different file sizes mean the files are different and no content comparison
    is required;
  - the same filesystem device and inode means both paths refer to the same
    physical file and no content comparison is required;
  - matching size, timestamps, link counts, names, or folder identities alone
    are not sufficient to prove two different inodes contain identical content.
- When different-inode files still require content or hash comparison, expose
  visible progress for that comparison, including enough context to show which
  movie/files are being checked and how much data has been processed. The main
  library scan must not appear frozen while many gigabytes are read.
- A trailing underscore in a folder name is evidence of a reconciliation case,
  not permission to delete it automatically. An operator may independently remove
  a known redundant underscore folder after verifying it, but `media scan` must
  remain non-destructive and must not infer safe deletion from the suffix alone.
- Do not lower-case words in an already capitalised movie title solely to match
  metadata. In particular, `Anyone But You` must not be changed to
  `Anyone but You`.
- When multiple meaningful video filenames in one folder resolve to distinct movie
  identities, report a mixed movie folder / split candidate before applying shared
  folder metadata to every file. Obvious ancillary material such as samples,
  trailers, featurettes and behind-the-scenes content must not create a split
  candidate. Multipart media must also remain part of the same movie identity.
- Keep `media scan` non-destructive in accordance with REQ-029.

## Out of scope

- Automatically deciding which conflicting metadata source is correct.
- Fetching new online metadata solely to resolve a conflict.
- Rewriting incorrect `movie.xml` files.
- Automatically correcting provider IDs.
- Changing TV-series identity rules.
- Defining a general English grammar or editorial title-casing engine beyond
  preserving the library's capitalised title convention.

## Acceptance criteria

1. Given a movie folder named `13 minutes (2021)` whose MCM metadata resolves
   to `One Second Forever (2021)`, when the library is scanned, then OMV
   reports an identity conflict and does not propose or execute that title
   rename.
2. Given an existing movie whose resolved metadata proposes a different release
   year, when the scan evaluates the rename, then OMV flags the year change as
   an identity conflict and does not treat it as routine normalisation.
3. Given `Carry On Matron (1972)` and metadata proposing
   `Carry On Matron (2007)`, when scanned, then the proposed year change is
   visibly flagged for review and no rename occurs.
4. Given a title where only punctuation, spacing, filesystem-safe substitution
   or an explicitly supported article convention differs, when identity
   evidence otherwise agrees, then OMV may continue to treat the change as
   safe naming normalisation.
5. Given `Anyone But You (2023)` and metadata containing
   `Anyone but You (2023)`, when scanned, then OMV preserves
   `Anyone But You (2023)` and does not propose a case-only downgrade.
6. Given a detected identity conflict, when it is reported, then the output
   identifies the affected folder path, the current movie identity, the
   conflicting proposed identity, and the evidence source responsible for the
   disagreement.
7. Given runtime or duration evidence that materially conflicts with metadata,
   when available, then it is included in the conflict evidence rather than
   silently ignored.
8. Given an identity conflict during a confirmed workflow, when the operation
   reaches that movie, then the conflicting rename remains blocked unless a
   separately defined explicit review/override workflow authorises it.
9. Given canonical metadata containing filesystem-invalid punctuation, when a
   movie rename is planned, then OMV derives the filesystem-safe folder and
   filename before checking destinations or executing the rename.
10. Given `Nativity 3 - Dude, Where's My Donkey?!`, `TAYLOR SWIFT | THE ERAS TOUR`,
   or `Thunderbolts*`, when canonical naming is applied, then unsupported
   filename characters are ignored/removed before the destination path is
   planned and no invalid-character `EINVAL` rename failure occurs.
11. Given filesystem-safe punctuation normalisation, when identity comparison
   is performed, then ignoring/removing unsupported characters must not make a
   substantive title or year disagreement appear safe.
12. Given a movie folder containing a canonical feature file and ancillary
   media whose filename clearly marks it as a sample (including names such as
   `Sample.mkv`, `sample - includes commentary track.mkv`, or `EVO-sample.mkv`),
   when scanned, then the ancillary file is ignored for feature-name
   reconciliation and is not proposed as another copy of the movie.
13. Given two folders that normalise to the same movie identity, such as
   `Inside Out 2 (2024)_` and `Inside Out 2 (2024)`, when scanned, then OMV
   reports a same-identity folder reconciliation/merge candidate rather than a
   generic `target already exists` error.
14. Given a same-identity folder collision, when one folder contains the movie
   and the other contains metadata/artwork, then neither folder is overwritten
   or deleted automatically; the scan reports enough evidence for a later safe
   merge decision.
15. Given a canonical movie file target that already exists, when the source is
   not recognised ancillary media, then OMV reports a possible duplicate or
   unresolved file collision and does not overwrite either file.
16. Given a file named like `*-part2.*`, when it belongs to the same movie as the
   canonical feature, then OMV classifies it as multi-part feature media rather
   than a duplicate and does not rename it onto part 1.
17. Given a tiny release-marker file such as `RARBG.COM.mp4`, when it is clearly
   not meaningful feature media, then OMV classifies/ignores it as ancillary or
   junk rather than reporting a duplicate feature-file collision.
18. Given valid titles such as `Blood & Chrome`, `Black '47`,
   `The Source (Movie 2007)`, or `Mr. & Mrs. Smith`, when filesystem-safe naming
   is applied, then the valid punctuation and surrounding spacing are preserved
   unchanged.
19. Given `TAYLOR SWIFT | THE ERAS TOUR`, when canonical naming is applied, then
   the readable result is `Taylor Swift - The Eras Tour`, preserving a separator
   while avoiding all-caps output.
20. Given one folder containing distinct feature filenames for `Love And Jane (2024)`
   and `An American in Austen (2024)`, scan reports a mixed movie folder / split
   candidate with both file paths and performs no rename.
21. Given `Michael McIntyre - Showtime (2012)` with a `Behind The Scenes` video
   and a separately titled `Christmas Roadshow (2012)` video, behind-the-scenes
   content is treated as ancillary while the separate programme title is surfaced
   as a possible secondary identity requiring split investigation.
22. Given MCM metadata whose title is path-like, such as
   `Q:\Movies\Entangled (2019)`, when the stored media is scanned, OMV marks the
   metadata identity as suspect and does not use that path-like value to derive
   a canonical movie rename.
23. Given the same `Entangled (2019)` case where `movie.xml` reports a three-minute
   runtime while the actual MKV is roughly 91 minutes, OMV reports the material
   runtime contradiction, keeps the rename blocked, and does not treat the TMDb
   ID alone as sufficient proof that the MCM identity is authoritative.
24. Given one movie folder containing two distinct feature movies, such as
   `Love And Jane (2024)` and `An American in Austen (2024)`, when scan evidence
   resolves both identities, then OMV reports a mixed-identity folder / split
   candidate with the supporting feature-file paths instead of only reporting a
   rename conflict, and scan performs no move.
25. Given `Sonic the Hedgehog 3 (2024)` and `Sonic the Hedgehog 3 (2024)_` each
   containing a 20,526,191,454-byte feature file on the same filesystem but with
   different inodes, OMV does not assume the files are identical from size,
   timestamp, link count or naming alone; if identity must be established it
   performs the required content comparison without modifying either folder.
26. Given a duplicate-content comparison that reads a large feature file, OMV
   visibly reports the comparison target and progress while the read is running
   so the operator can distinguish active I/O from a stalled library scan.
27. Given two candidate files whose device and inode are identical, OMV treats
   them as the same physical file without hashing or reading the complete file.
28. Given an underscore-suffixed reconciliation folder, scan does not delete it
   merely because of the suffix; manual operator cleanup remains separate from
   the non-destructive scan workflow.

## Dependencies and decisions

- [REQ-019: Catalogue metadata resolution](019-catalogueMetadataResolution.md)
  supplies already-known metadata and provider identities.
- [REQ-020: Combined media scan command](020-combinedMediaScan.md) exposes the
  scan workflow where the issue was observed.
- [REQ-029: Non-destructive media scan](029-nonDestructiveMediaScan.md) remains
  authoritative for scan safety.
- REQ-034 real-library verification exposed the problem but catalogue location
  reconciliation is not the cause.
- No new ADR is currently required; implementation should use the existing
  metadata-resolution and filesystem-safety boundaries.

## Verification

- Regression fixture for `13 minutes (2021)` versus
  `One Second Forever (2021)`.
- Parameterised tests for movie year disagreements, including the real-library
  examples captured in this requirement.
- Test proving `Anyone But You` is not changed to `Anyone but You`.
- Tests proving punctuation-only and filesystem-safe normalisation still works.
- Regression tests for unsupported filename characters in canonical movie
  metadata, proving both folder and filename destinations are safe before rename.
- Regression tests proving valid punctuation spacing is preserved for `&`,
  apostrophes, and parentheses while unsupported characters are removed.
- Regression tests proving sample-name variants (`Sample.mkv`, `sample - ...`,
  `EVO-sample.mkv`) are ignored during canonical feature-file reconciliation.
- Regression tests proving `-part2` files are classified as multi-part media,
  not duplicate feature files.
- Regression test proving tiny release-marker files such as `RARBG.COM.mp4` are
  ignored/classified as non-feature media.
- Regression fixture for `Inside Out 2 (2024)_` plus `Inside Out 2 (2024)`,
  proving the collision is classified as a same-identity merge candidate.
- Tests covering an existing canonical target file, distinguishing ancillary
  media from possible duplicate feature content.
- Tests proving conflict output identifies the relevant evidence source.
- Tests proving dry-run and confirmed workflows both block an unresolved
  identity-changing rename.
- Regression fixture for the malformed `Entangled (2019)` MCM record, proving a
  path-like title and material runtime contradiction are reported as suspect
  metadata and cannot drive a canonical rename.
- Regression fixture for the Sonic same-identity folders with equal-sized files
  but different inodes, proving a full comparison is not skipped merely because
  cheap metadata agrees.
- Test proving identical device/inode pairs bypass content hashing.
- Test proving different file sizes bypass content hashing as non-identical.
- Test proving a genuine large-file comparison emits observable progress rather
  than leaving the enclosing library progress apparently frozen.
- Full existing movie scan, catalogue and CLI regression suites.
- Verified on 2026-10-01 in the `mediaStudio` environment: `pytest` 816 passed,
  `runLinter` on the changed Python files reported no findings,
  `runLinter --markup` reported no remaining issues, `manageProject --check`
  reported zero failures and zero warnings, and `git diff --check` produced
  no output. Black was applied to the changed Python files.

## Traceability

- Implementation: `organiseMyVideo/movieIdentity.py`,
  `organiseMyVideo/showFolders.py`, `organiseMyVideo/video.py`,
  `organiseMyVideo/videoRescan.py`, `organiseMyVideo/videoMove.py`
- Tests: `tests/test_movieIdentityConflict.py`,
  `tests/test_organiseMyVideo.py`
- Documentation: `documentation/commandLineInterface.md`, `README.md`
- Pull request: pending
- Agent runs: None

## Change history

- 2026-10-01: created — real-library testing exposed incorrect title and year
  rename proposals and an unwanted title-casing downgrade.
- 2026-10-01: completed initial identity-conflict implementation — a different
  title or release year is reported and left in place on both dry-run and
  confirmed movie scan and move.
- 2026-10-01: reopened/extended — real-library verification exposed canonical
  metadata punctuation (`?`, `|`, `*`) reaching the filesystem unchanged;
  filesystem-safe canonical naming is now part of REQ-035.
- 2026-10-01: extended from production scan findings — ancillary `Sample.mkv`
  files can be mistaken for the feature, and same-identity folder/file targets
  can collide. REQ-035 now requires collision classification and safe merge/
  duplicate-candidate reporting rather than generic rename failures.
- 2026-10-01: corrected sanitizer behaviour after dry-run testing showed valid
  spacing around `&`, apostrophes, and `(` being removed.
- 2026-10-01: completed the filesystem-safe naming and collision classification
  extension — canonical folder and file names drop unsupported characters
  before rename planning, `Sample.mkv` is not treated as the feature, and an
  existing canonical target is classified and left in place.
- 2026-10-02: clarified readable canonical casing/separator behaviour for
  `TAYLOR SWIFT | THE ERAS TOUR` and required folder location in conflict review.
- 2026-10-04: extended after real-library scan found two distinct movies sharing
  one folder; scan must classify this as a mixed-identity split candidate.
- 2026-10-04: extended from real-library mixed-folder findings; scan now distinguishes
  distinct feature identities from ancillary material before shared metadata repair.
- 2026-10-04: extended from the malformed `Entangled (2019)` MCM record; path-like
  metadata titles and material runtime contradictions are suspect identity evidence
  and must not drive canonical renames even when provider IDs are present.
- 2026-10-05: extended from the Sonic same-identity collision; duplicate verification
  now requires cheap inode/size fast paths, visible progress for genuine large-file
  comparisons, and no automatic deletion based only on an underscore folder suffix.
