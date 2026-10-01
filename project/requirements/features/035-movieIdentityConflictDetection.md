# 035: Movie identity conflict detection

## Status

ToDo

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
- Tests proving conflict output identifies the relevant evidence source.
- Tests proving dry-run and confirmed workflows both block an unresolved
  identity-changing rename.
- Full existing movie scan, catalogue and CLI regression suites.

## Change history

- 2026-10-01: created — real-library testing exposed incorrect title and year
  rename proposals and an unwanted title-casing downgrade.
