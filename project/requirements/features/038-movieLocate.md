# 038: Unified media location lookup

## Status

Completed

## Outcome

Find a movie or TV show's recorded library folders through one command:
`media locate SEARCH`.

## Scope

Search catalogue movie titles and TV show names together using one required
case-insensitive exact or partial search term. Movie results include release
years and the year may be included in the search. Exact matches precede partial
matches. Output identifies each result as `Movie` or `TV` and reports current,
unverified and stale locations using the existing catalogue visibility rules.

The canonical locate syntax has no `--movie` or `--show` selector. A search term
is required; omitting it is an argument error rather than a request to dump the
TV catalogue.

## Out of scope

Library rescanning and media changes.

## Acceptance criteria

1. `media locate SEARCH` searches both movie and TV catalogue entries.
2. Matching is case-insensitive, ignores surrounding whitespace and returns exact
   matches before partial matches.
3. Movie results include the movie title, release year, folder path, location
   state and `Movie` type label.
4. TV results include the show name, folder path, location state and `TV` type
   label.
5. A movie release year may participate in the search, for example
   `media locate "Zone 414 (2021)"`.
6. When both movie and TV entries match the search, both result types are shown.
7. Missing matches report a media-not-found error and exit 1.
8. Omitting `SEARCH` reports command usage as an argument error rather than
   listing every TV show.
9. `--movie` and `--show` are not part of the canonical `media locate` syntax.

## Dependencies and decisions

Uses the existing SQLite catalogue and location reconciliation rules (REQ-034).
No new architecture decision is required.

## Verification

Exercise the public CLI against a real temporary mixed movie/TV catalogue,
including exact and partial matches, year selection, missing folders, stale
locations, mixed result types, no matches and a missing search argument. Run
existing CLI and catalogue location reconciliation tests.

## Change history

- 2026-10-04: created from the user's request for a movie locate option.
- 2026-10-05: simplified movie/TV lookup to the unified `media locate SEARCH`
  command and removed the canonical `--movie` / `--show` selectors.
