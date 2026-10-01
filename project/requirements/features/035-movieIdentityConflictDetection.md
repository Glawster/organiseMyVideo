# 035: Movie identity conflict detection

## Status

In progress

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
- Preserve title-style capitalisation when the existing and resolved title
  differ only by case.
- Produce a filesystem-safe canonical movie folder and filename before rename
  planning. Unsupported filename characters from metadata should be ignored/
  removed rather than passed through to `rename()`.
- Apply the same filesystem-safe naming rule to both movie folders and movie
  files while preserving an unambiguous movie identity.
- Ignore known non-feature media such as `Sample.mkv` during canonical feature
  filename reconciliation; these files must not be renamed to the feature's
  canonical movie filename.
- When a canonical file or folder target already exists, classify the condition
  rather than reporting only a generic rename error. Distinguish at least:
  - ignored ancillary media such as samples;
  - same-identity folder collision / merge candidate;
  - possible duplicate feature file; and
  - unresolved collision requiring review.
- A same-identity folder collision must not overwrite or delete either side.
  Treat it as a reconciliation candidate and establish whether content is
  identical, complementary, or distinct before any later merge operation.
- Do not lower-case words in an already capitalised movie title solely to match
  metadata. In particular, `Anyone But You` must not be changed to
  `Anyone but You`.
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
   identifies the current movie identity, the conflicting proposed identity,
   and the evidence source responsible for the disagreement.
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
12. Given a movie folder containing a canonical feature file and `Sample.mkv`,
   when scanned, then the sample is ignored for feature-name reconciliation and
   is not proposed as another copy of the movie.
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
- Regression test proving `Sample.mkv` is ignored during canonical feature-file
  reconciliation.
- Regression fixture for `Inside Out 2 (2024)_` plus `Inside Out 2 (2024)`,
  proving the collision is classified as a same-identity merge candidate.
- Tests covering an existing canonical target file, distinguishing ancillary
  media from possible duplicate feature content.
- Tests proving conflict output identifies the relevant evidence source.
- Tests proving dry-run and confirmed workflows both block an unresolved
  identity-changing rename.
- Full existing movie scan, catalogue and CLI regression suites.
- Verified on 2026-10-01 in the `mediaStudio` environment: `pytest` 795 passed,
  `runLinter` reported no findings, `runLinter --markup` reported no remaining
  issues, `manageProject --check` reported zero failures and zero warnings,
  and `git diff --check` produced no output. Black was applied to the changed
  Python files.

## Traceability

- Implementation: `organiseMyVideo/movieIdentity.py`,
  `organiseMyVideo/video.py`, `organiseMyVideo/videoRescan.py`,
  `organiseMyVideo/videoMove.py`
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
