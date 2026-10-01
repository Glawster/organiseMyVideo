# 035: Movie identity conflict detection

## Status

Completed

## Outcome

As a media-library operator, I need movie scan and organise to tell a real
title or release-year change from a safe filename tidy-up, so that one film is
not renamed as if it were another and the library's capitalised titles stay as
they are.

## Context

Movie reset and movie move build a destination from resolved metadata. Local
`movie.xml` replaces the title and year taken from the folder or filename, and
there is no comparison before the rename. A sidecar for a different film, or a
different release year, is then applied as an ordinary rename.

These library cases must not be renamed:

- `13 minutes (2021)` to `One Second Forever (2021)`, because the existing
  `movie.xml` names a different film
- `Call of the Wild, The (1972)` to `Call of the Wild, The (1975)`
- `Carry On Matron (1972)` to `Carry On Matron (2007)`
- `Boss Level (2021)` to `Boss Level (2020)`
- `Chernobyl - Abyss (2021)` to `Chernobyl - Abyss (2022)`
- `Anyone But You` to `Anyone but You`

Punctuation, spacing, and filesystem-safe substitutions must still be applied
when the title identity and release year agree. `The Title (Year)` may still
become `Title, The (Year)`. An all-lowercase on-disk title may still gain
capitals, as with `inception (2010)` becoming `Inception (2010)`.

## Scope

- Compare each parsed movie folder name and filename with the title and year
  about to be used for a rename, before `movie.xml` is rewritten and before a
  folder or file is renamed.
- Treat the title identity as the same when the only differences are case,
  apostrophes, other punctuation, spacing, filesystem separators (`\`, `/`,
  `:`), or a leading or trailing `The`. Keep an internal `The`.
- Treat any release year that is present on both sides and not equal as an
  identity conflict. A missing year on one side is not a conflict.
- Treat a different title identity as an identity conflict.
- When an unresolved conflict exists, do not rename the folder or file, do not
  rewrite `movie.xml`, and do not fetch online metadata to decide which film
  is correct. Report the current title and year, the proposed title and year,
  the evidence source, provider IDs already known, and runtime or duration
  text already stored.
- When metadata differs only by case and would replace an uppercase letter
  with a lowercase letter, keep the existing capitalised title for the folder
  and file name.
- Apply the same refusal on a dry-run and on a confirmed run. Confirmed
  mutations that remain allowed stay on the existing filesystem-safety
  boundary.
- Apply the guard to movie metadata reset and to moving a movie whose folder
  or filename already has a conflicting identity.

## Out of scope

- Making `media scan` observational. REQ-029 still owns that split. Safe
  punctuation and article renames stay where they are today.
- Choosing a winner by searching TMDB, OMDb, or any other online source.
- Rewriting embedded media timestamps or creating a new metadata provider.
- Treating provider-ID disagreement, by itself, as an identity conflict when
  the title identity and release year agree.
- Equating words that are not the same after punctuation is ignored, including
  an internal article or `&` versus `and`.
- An operator action that accepts a conflicting identity and then renames.

## Acceptance criteria

1. Given folder and file `13 minutes (2021)` and a `movie.xml` for
   `One Second Forever (2021)`, when movie scan or a movie move runs, then
   nothing is renamed, `movie.xml` is unchanged, online metadata is not
   fetched, and the report shows both titles and years, evidence `movie.xml`,
   and any IMDb id, TMDB id, and runtime already in that file.
2. Given the same title and a different release year, including the four
   year pairs in Context, when movie scan runs, then the change is reported
   as an identity conflict and the folder and file stay in place.
3. Given an on-disk title `Anyone But You` and metadata `Anyone but You` for
   the same year, when movie scan runs, then the folder and file keep
   `Anyone But You`.
4. Given a title and year that agree apart from punctuation or a filesystem
   separator, when a confirmed movie scan runs, then the filesystem-safe name
   is still applied. Given `The Title (Year)` for the same film and year, the
   folder may still become `Title, The (Year)`. An all-lowercase folder may
   still gain the metadata capitals.
5. Given an unresolved identity conflict, when the run is a dry-run or a
   confirmed run, then neither path renames the movie or rewrites `movie.xml`.

## Dependencies and decisions

- [ADR-003](../../adr/003-filesystemSafetyBoundary.md) remains the boundary
  for any confirmed rename that is still allowed.
- REQ-029 remains the separate obligation to stop `media scan` mutating media.
- No new architecture decision. The comparison is a guard on the existing
  movie rename paths.

## Verification

- `tests/test_movieIdentityConflict.py` covers the classifier and the scan and
  move paths named in the acceptance criteria, including dry-run and confirmed
  refusal.
- Existing movie reset tests cover an allowed capitalisation repair, colon
  substitution, and a destination collision for a filename that has no
  established title.
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

- 2026-10-01: created — movie scan treated a different title or release year
  in existing metadata as a routine rename.
- 2026-10-01: completed — unresolved title and year changes are reported and
  not renamed, and the full test suite passed.
