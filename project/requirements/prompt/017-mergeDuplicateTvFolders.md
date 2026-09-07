# Requirement: 017 — project/requirements/features/017-mergeDuplicateTvFolders.md

Role: implement and verify

Read the requirement. Add `media organise --merge` to consolidate
provider-identified duplicate TV and movie folders into the most complete
existing folder. Require IMDb/TMDB (movies) or TVDB/TMDB/IMDb (TV) before
merging; do not guess from titles. Keep dry-run default and `--confirm`
for writes. Canonicalise `Season 03` to `Season 3`. Do not overwrite
destination files.

Verify with `pytest` and `git diff --check`.
