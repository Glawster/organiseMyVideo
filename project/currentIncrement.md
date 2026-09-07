# Current increment

## Requirement

[REQ-017: Merge duplicate TV and movie folders](requirements/features/017-mergeDuplicateTvFolders.md)

## Objective

Finish `--merge` for TV folders and add the same provider-identity merge
for movie folders.

## Status

Completed — TV merge plus IMDb/TMDB movie merge, regenerable `movie.xml`,
and feature-video collision handling.

## Verification result

- 457 pytest tests passed
- `git diff --check` clean
