# Current increment

## Requirement

[REQ-018: TV show folder leading articles](requirements/features/018-tvShowFolderArticles.md)

## Objective

Keep titles as `The Boys` / `The Godfather`, and store folders as
`Boys, The` / `Godfather, The (1972)` for browsing.

## Status

Completed — TV and movie folder cleanup invert a leading `The` on the
folder only; catalogue titles stay in natural order.

## Verification result

- pytest
- `git diff --check`
