# Current increment

## Requirement

[REQ-017: Merge duplicate TV folders](requirements/features/017-mergeDuplicateTvFolders.md)

## Objective

Keep the merge progress bar moving while a large source folder is listed,
counted, and copied, instead of sitting at 0% with the source directory name.

## Status

Completed — the live line starts before counting, shows listing, credits
whole-tree moves before the copy, and no longer renders 100% while the
total is still unknown.

## Verification result

- pytest
- `git diff --check`
