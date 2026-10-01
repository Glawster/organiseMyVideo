# Current increment

## Objective and status

REQ-034 catalogue location reconciliation is complete. An authoritative listing
of a movie or TV root marks folders that are present as current and folders
that are absent as stale. A directory inside a TV show that cannot be read
does not retire the episodes beneath it. A root that is missing, unmounted,
or unlistable keeps the catalogue rows it already had. The requirement and
the requirements index both record REQ-034 as Completed.

## Accepted scope

- `locationState` on movie, series, and episode rows, plus `catalogueScanRoot`.
- Reconcile instead of deleting unseen rows. Default lists hide stale rows.
- Locate output for current, stale, and unverified paths, with optional
  `--show`.
- Retarget catalogue rows on confirmed show, movie, season, and merge moves.
- Reconcile after every `media organise --merge`, including dry-run and a run
  that merges nothing.
- Lanterns regression coverage on temporary roots, including locate of every
  catalogued show and an unread season directory.

## Final verification

Verified in the `mediaStudio` Conda environment:

- Full `pytest` suite: 770 passed.
- `runLinter`: no findings.
- `runLinter --markup`: no remaining issues.
- `manageProject --check`: zero failures and zero warnings.
- Black was applied to the changed Python files, and `git diff --check` passed.

## Remaining work and immediate next action

REQ-034 verification and documentation are complete. No implementation or
verification work remains for this increment. Select the next increment through
the requirements index when further work is requested.
