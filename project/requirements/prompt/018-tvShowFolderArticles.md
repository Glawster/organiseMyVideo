# Requirement: 018 — project/requirements/features/018-tvShowFolderArticles.md

Role: implement and verify

Canonical TV show folders that begin with "The" must be stored as
"Name, The". Scan library roots, rename incorrect folders, and merge into
an existing canonical folder without overwriting. Run from media organise,
merge, and clean. Dry-run default.

Verify with `pytest` and `git diff --check`.
