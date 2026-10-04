# 038: Movie location lookup

## Status

Completed

## Outcome

Find a movie's recorded library folders through `media locate --movie TITLE`.

## Scope

Search catalogue movie titles case-insensitively with exact and partial matching.
Include release years in results and allow the year in the search. Report current,
unverified and stale locations using the same visibility rules as TV lookup.

## Out of scope

Library rescanning and media changes.

## Acceptance criteria

1. `--movie TITLE` returns matching movie names, years, folder paths and states.
2. Exact titles precede partial matches; surrounding whitespace is ignored.
3. Missing matches report an error and exit 1.
4. `--movie` and `--show` cannot be combined; no selector retains the TV listing.

## Dependencies and decisions

Uses the existing SQLite catalogue and location reconciliation rules (REQ-034).
No new architecture decision is required.

## Verification

Exercise the public CLI against a real temporary movie catalogue, including
partial matches, year selection, missing folders, stale locations and no matches.
Run existing CLI and location reconciliation tests.

## Change history

- 2026-10-04: created from the user's request for a movie locate option.
